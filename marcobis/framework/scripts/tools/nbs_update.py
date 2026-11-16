#!/usr/bin/env python3
"""下载并清洗国家统计局月度 / 季度 / 年度宏观面板（nbs_m / nbs_q / nbs_a）。

用法（在工作区根目录运行）::

    python3 scripts/tools/nbs_update.py --panel nbs_m          # 月度
    python3 scripts/tools/nbs_update.py --panel all            # 三个面板
    python3 scripts/tools/nbs_update.py --panel nbs_q --only gdp,gdp_real
    python3 scripts/tools/nbs_update.py --panel nbs_m --list   # 只列出面板定义，不联网

面板定义在 ``data/<panel>/panel.yaml``。每次运行会重新下载定义中的全部序列（NBS 会修订历史
数据，增量更新容易留下旧值），写出：

=========================  =====================================================
文件                       内容
=========================  =====================================================
``dataset.csv``            清洗后的数据 + 派生序列；``lib.load_dataset("nbs_m")`` 读这个
``raw.csv``                只做了分段拼接、未清洗的原始数据，便于核对
``series_info.csv``        每列的中文名、分组、单位、清洗步骤、建议变换、样本起止
``transform_codes.csv``    FRED-MD 格式的建议变换编码（loader 会读取）
``metadata.yaml``          版本（下载日期）、每个序列的来源目录 / 分段 / 指标键、重叠期冲突、
                           定基指数核对结果、失败的序列
=========================  =====================================================

本脚本只依赖 numpy、pandas、PyYAML，不需要 plotly / statsmodels；网络访问只用标准库。
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import sys
import time
import warnings
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
import yaml

ROOT = Path(__file__).resolve().parents[2]
LIB = ROOT / "scripts" / "lib"
PANELS = ("nbs_m", "nbs_q", "nbs_a")


def _load_module(name: str, path: Path):
    """按文件路径加载模块，避免 ``import lib`` 牵出 plotly 等重依赖。"""
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


nc = _load_module("_nbs_client", LIB / "data" / "nbs_client.py")
china = _load_module("_nbs_china", LIB / "preprocess" / "china.py")

CLEAN_STEPS = ("none", "cumulative_to_period", "fill_january", "index_to_rate")


def load_panel(panel: str) -> dict:
    path = ROOT / "data" / panel / "panel.yaml"
    if not path.is_file():
        raise SystemExit(f"找不到面板定义 {path}")
    spec = yaml.safe_load(path.read_text(encoding="utf-8"))
    ids = [s["id"] for s in spec.get("series", [])] + [d["id"] for d in spec.get("derived", [])]
    dup = {i for i in ids if ids.count(i) > 1}
    if dup:
        raise SystemExit(f"{path}：id 重复 {sorted(dup)}")
    for s in spec.get("series", []):
        if s.get("jan_feb_from") is not None and not isinstance(s.get("jan_feb_from"), str):
            raise SystemExit(f"{path}：序列 {s['id']} 的 jan_feb_from 要加引号")
        if not isinstance(s.get("key"), str):
            raise SystemExit(
                f"{path}：序列 {s['id']} 的 key 被 YAML 读成了 {type(s.get('key')).__name__} {s.get('key')!r}。"
                "请给指标键加引号，例如 key: '6021702000021_1'（YAML 会把带下划线的数字当作整数）。")
        for step in _steps(s.get("clean")):
            if step not in CLEAN_STEPS:
                raise SystemExit(f"{path}：序列 {s['id']} 的 clean={step!r} 不受支持（可用 {CLEAN_STEPS}）")
    return spec


def _steps(clean) -> list[str]:
    if clean is None:
        return ["none"]
    if isinstance(clean, str):
        return [clean]
    return list(clean)


def merge_columns(new: dict[str, pd.Series], existing: pd.DataFrame | None) -> pd.DataFrame:
    """把新下载的列与已有数据合并：日期取两者的并集，已有的其他列完整保留。"""
    df = pd.DataFrame({k: v for k, v in new.items()})
    if len(df):
        df.index = pd.DatetimeIndex(df.index, name="date")
    if existing is not None:
        idx = df.index.union(existing.index) if len(df) else existing.index
        df = df.reindex(idx)
        for col in existing.columns:
            if col not in new:
                df[col] = existing[col].reindex(idx)
    df.index = pd.DatetimeIndex(df.index, name="date")
    return df.sort_index()


def full_calendar(index: pd.DatetimeIndex, freq: str) -> pd.DatetimeIndex:
    f = {"M": "MS", "Q": "QS-MAR", "A": "YS"}[freq]
    return pd.date_range(index.min(), index.max(), freq=f, name="date")


def apply_clean(s: pd.Series, steps: list[str], freq: str, ytd: pd.Series | None = None) -> pd.Series:
    for step in steps:
        if step == "none":
            continue
        if step == "cumulative_to_period":
            if freq == "A":
                raise ValueError("年度数据不能做 cumulative_to_period")
            s = china.cumulative_to_period(s, freq)
        elif step == "fill_january":
            if freq != "M":
                raise ValueError("fill_january 只适用于月度数据")
            s = china.fill_january(s, ytd=ytd)
        elif step == "index_to_rate":
            s = china.index_to_rate(s)
    return s


def compute_derived(d: dict, data: dict[str, pd.Series], freq: str) -> tuple[pd.Series, dict]:
    method = d["method"]
    info: dict = {"method": method}
    if method == "chain_index":
        if freq not in ("M", "Q"):
            raise ValueError("chain_index 只适用于月度 / 季度数据")
        mom = data.get(d.get("mom")) if d.get("mom") else None
        yoy = data.get(d.get("yoy")) if d.get("yoy") else None
        if (d.get("mom") and mom is None) or (d.get("yoy") and yoy is None):
            raise KeyError(f"派生序列 {d['id']} 依赖的序列没有下载成功")
        out = china.chain_index(mom=mom, yoy=yoy, freq=freq, base=d.get("base"),
                                mom_start=d.get("mom_start"))
        info.update({"inputs": [x for x in (d.get("mom"), d.get("yoy")) if x],
                     "chain_method": out.attrs.get("chain_method"),
                     "chain_check": out.attrs.get("chain_check")})
        return out, info
    if method == "index_to_rate":
        src = data.get(d["source"])
        if src is None:
            raise KeyError(f"派生序列 {d['id']} 依赖的 {d['source']} 没有下载成功")
        info["inputs"] = [d["source"]]
        return china.index_to_rate(src), info
    if method == "deflator_yoy":
        nom, real = data.get(d["nominal"]), data.get(d["real_yoy_index"])
        if nom is None or real is None:
            raise KeyError(f"派生序列 {d['id']} 依赖的序列没有下载成功")
        lag = {"M": 12, "Q": 4, "A": 1}[freq]
        nom = china.regularize(nom, freq)
        real = real.reindex(nom.index)
        out = (nom / nom.shift(lag)) / (real / 100.0) * 100.0 - 100.0
        info["inputs"] = [d["nominal"], d["real_yoy_index"]]
        return out, info
    if method == "ratio":
        num, den = data.get(d["numerator"]), data.get(d["denominator"])
        if num is None or den is None:
            raise KeyError(f"派生序列 {d['id']} 依赖的序列没有下载成功")
        out = num / den * float(d.get("scale", 1.0))
        info["inputs"] = [d["numerator"], d["denominator"]]
        return out, info
    raise ValueError(f"未知的派生方法 {method!r}")


def write_transform_codes(path: Path, codes: dict[str, int]) -> None:
    lines = [",0", "sasdate,Transform:"] + [f"{k},{float(v)}" for k, v in codes.items()]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


DERIVED_INPUT_KEYS = ("mom", "yoy", "source", "nominal", "real_yoy_index", "numerator", "denominator")


def derived_inputs(d: dict) -> list[str]:
    """派生序列定义里引用的输入列。"""
    return [d[k] for k in DERIVED_INPUT_KEYS if d.get(k)]


def update_panel(panel: str, *, only: set[str] | None, start: str | None,
                 refresh_catalog: bool, client) -> dict:
    spec = load_panel(panel)
    freq = nc.normalize_freq(spec["freq"])
    out_dir = ROOT / "data" / panel
    t0 = time.time()
    print(f"== {spec['name']}（{panel}，{nc.FREQS[freq]['name']}）", flush=True)
    if refresh_catalog:
        client.catalog(freq, refresh=True, progress=True)

    series_defs = [s for s in spec.get("series", []) if not only or s["id"] in only]
    raw: dict[str, pd.Series] = {}
    clean: dict[str, pd.Series] = {}
    meta_series: dict[str, dict] = {}
    failed: dict[str, str] = {}

    # 合并模式：--only 时保留 dataset.csv 中其他列
    existing = None
    if only and (out_dir / "dataset.csv").exists():
        existing = pd.read_csv(out_dir / "dataset.csv", index_col=0, parse_dates=True)

    for s in series_defs:
        sid = s["id"]
        try:
            with warnings.catch_warnings(record=True) as caught:
                warnings.simplefilter("always")
                s_start = s.get("start") or start
                series, meta = client.fetch_series(s["catalog"], str(s["key"]), freq, start=s_start)
                raw[sid] = series.copy()
                ytd = None
                if s.get("jan_feb_from"):
                    ytd, _ = client.fetch_series(s["catalog"], str(s["jan_feb_from"]), freq, start=s_start)
                cleaned = apply_clean(series, _steps(s.get("clean")), freq, ytd=ytd)
            clean[sid] = cleaned
            meta_series[sid] = {
                "label": s.get("label"), "group": s.get("group"),
                "catalog": s["catalog"], "key": str(s["key"]),
                "nbs_key": meta.get("key"), "nbs_name": meta.get("name"),
                "unit_source": meta.get("unit"), "unit": s.get("unit"),
                "clean": _steps(s.get("clean")),
                "jan_feb_from": s.get("jan_feb_from"),
                "preprocess_applied": list(cleaned.attrs.get("preprocess_applied", [])),
                "filled_january": cleaned.attrs.get("filled_january"),
                "segments": meta.get("segments"),
                "overlap_conflicts": meta.get("overlap_conflicts") or [],
                "warnings": [str(w.message) for w in caught],
                "note": meta.get("note"),
            }
            nn = cleaned.dropna()
            print(f"   ✓ {sid:<22} {len(nn):>4} 期  {nn.index.min().date() if len(nn) else '—'} – "
                  f"{nn.index.max().date() if len(nn) else '—'}  （{len(meta.get('segments') or [])} 段）",
                  flush=True)
        except nc.NBSBlockedError:
            raise
        except Exception as exc:  # noqa: BLE001
            failed[sid] = f"{type(exc).__name__}: {exc}"
            print(f"   ✗ {sid:<22} 失败：{exc}", flush=True)

    for d in spec.get("derived", []):
        if only and d["id"] not in only and not any(x in only for x in derived_inputs(d)):
            continue
        pool = dict(clean)
        if existing is not None:
            for col in existing.columns:
                pool.setdefault(col, existing[col].dropna())
        missing = [x for x in derived_inputs(d) if x not in pool]
        if only and d["id"] not in only and missing:
            # --only 模式下没点名的派生序列：输入不全就跳过，不算失败
            print(f"   · {d['id']:<22} 跳过（缺少输入 {', '.join(missing)}）", flush=True)
            continue
        try:
            series, info = compute_derived(d, pool, freq)
            clean[d["id"]] = series
            meta_series[d["id"]] = {"label": d.get("label"), "group": d.get("group"),
                                    "unit": d.get("unit"), "derived": info}
            print(f"   ✓ {d['id']:<22} 派生（{d['method']}）"
                  + (f"  核对：{info.get('chain_check')}" if info.get("chain_check") else ""), flush=True)
        except Exception as exc:  # noqa: BLE001
            failed[d["id"]] = f"{type(exc).__name__}: {exc}"
            print(f"   ✗ {d['id']:<22} 派生失败：{exc}", flush=True)

    if not clean:
        return {"panel": panel, "ok": False, "failed": failed}

    df = merge_columns(clean, existing)
    df = df.reindex(full_calendar(df.dropna(how="all").index, freq))
    order = [s["id"] for s in spec.get("series", [])] + [d["id"] for d in spec.get("derived", [])]
    df = df[[c for c in order if c in df.columns] + [c for c in df.columns if c not in order]]

    raw_df = merge_columns(raw, None) if raw else pd.DataFrame()

    out_dir.mkdir(parents=True, exist_ok=True)
    df.to_csv(out_dir / "dataset.csv", float_format="%.6g")
    if len(raw_df):
        if existing is not None and (out_dir / "raw.csv").exists():
            old_raw = pd.read_csv(out_dir / "raw.csv", index_col=0, parse_dates=True)
            raw_df = merge_columns({c: raw_df[c] for c in raw_df.columns}, old_raw)
        raw_df.to_csv(out_dir / "raw.csv", float_format="%.6g")

    all_defs = {s["id"]: s for s in spec.get("series", [])}
    all_defs.update({d["id"]: d for d in spec.get("derived", [])})
    rows, codes = [], {}
    for col in df.columns:
        d = all_defs.get(col, {})
        nn = df[col].dropna()
        rows.append({
            "id": col, "label": d.get("label"), "group": d.get("group"), "unit": d.get("unit"),
            "kind": "derived" if "method" in d else "series",
            "clean": ";".join(_steps(d.get("clean"))) if "method" not in d else d.get("method"),
            "tcode": d.get("tcode"), "sa": d.get("sa"),
            "start": str(nn.index.min().date()) if len(nn) else None,
            "end": str(nn.index.max().date()) if len(nn) else None,
            "n_obs": int(len(nn)),
            "internal_gaps": int(df[col].loc[nn.index.min():nn.index.max()].isna().sum()) if len(nn) else 0,
        })
        if d.get("tcode") is not None:
            codes[col] = int(d["tcode"])
    pd.DataFrame(rows).to_csv(out_dir / "series_info.csv", index=False)
    write_transform_codes(out_dir / "transform_codes.csv", codes)

    old_meta = {}
    if existing is not None and (out_dir / "metadata.yaml").exists():
        old_meta = (yaml.safe_load((out_dir / "metadata.yaml").read_text(encoding="utf-8")) or {}).get("series", {})
    old_meta.update(meta_series)
    now = datetime.now(timezone.utc)
    meta = {
        "dataset_id": panel,
        "name": spec["name"],
        "source": spec.get("source"),
        "frequency": nc.FREQS[freq]["label"],
        "vintage": now.strftime("%Y-%m-%d"),
        "fetched_at": now.isoformat(timespec="seconds"),
        "endpoint": nc.BASE_URL,
        "partial_update": sorted(only) if only else None,
        "date_convention": {"M": "当月 1 日", "Q": "季末月份 1 日（与 FRED-QD 一致）",
                            "A": "当年 1 月 1 日"}[freq],
        "sample_start": str(df.index.min().date()),
        "sample_end": str(df.dropna(how="all").index.max().date()),
        "n_series": int(df.shape[1]),
        "failed": failed,
        "series": old_meta,
    }
    (out_dir / "metadata.yaml").write_text(
        yaml.safe_dump(meta, allow_unicode=True, sort_keys=False, width=120), encoding="utf-8")
    print(f"   写出 {out_dir.relative_to(ROOT)}/dataset.csv：{df.shape[1]} 列，"
          f"{meta['sample_start']} – {meta['sample_end']}，用时 {time.time() - t0:.0f} 秒；"
          f"失败 {len(failed)} 个", flush=True)
    return {"panel": panel, "ok": not failed, "n_series": int(df.shape[1]),
            "sample": [meta["sample_start"], meta["sample_end"]], "failed": failed}


def list_panel(panel: str) -> None:
    spec = load_panel(panel)
    print(f"== {spec['name']}（{panel}）")
    for s in spec.get("series", []):
        print(f"   {s['id']:<22} {s.get('group', ''):<4} {s['label']}  [{';'.join(_steps(s.get('clean')))}]")
    for d in spec.get("derived", []):
        print(f"   {d['id']:<22} {d.get('group', ''):<4} {d['label']}  [派生：{d['method']}]")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="下载并清洗国家统计局宏观面板")
    ap.add_argument("--panel", default="all", help="nbs_m | nbs_q | nbs_a | all（默认 all）")
    ap.add_argument("--only", help="只更新这些列（逗号分隔），其他列保留现有数据")
    ap.add_argument("--start", help="起始日期（默认取全部历史）")
    ap.add_argument("--refresh-catalog", action="store_true",
                    help="重新遍历 NBS 目录树（目录有调整、找不到表时使用；耗时几分钟）")
    ap.add_argument("--list", action="store_true", help="只列出面板定义，不联网")
    args = ap.parse_args(argv)

    panels = PANELS if args.panel == "all" else tuple(p.strip() for p in args.panel.split(","))
    bad = [p for p in panels if p not in PANELS]
    if bad:
        ap.error(f"未知面板 {bad}；可用 {PANELS}")
    if args.list:
        for p in panels:
            list_panel(p)
        return 0

    only = {x.strip() for x in args.only.split(",")} if args.only else None
    client = nc.NBSClient(cache_dir=ROOT / "data" / "nbs_catalog")
    results = []
    for p in panels:
        try:
            results.append(update_panel(p, only=only, start=args.start,
                                        refresh_catalog=args.refresh_catalog, client=client))
        except nc.NBSBlockedError as exc:
            print(f"   ✗ 已停止：{exc}", flush=True)
            print("     已下载的面板文件保持不变（被中断的面板不会写出半成品）。", flush=True)
            results.append({"panel": p, "ok": False, "blocked": True, "error": str(exc)})
            break
        except nc.NBSError as exc:
            print(f"   ✗ {p} 失败：{exc}", flush=True)
            results.append({"panel": p, "ok": False, "error": str(exc)})
    print(json.dumps({"results": results}, ensure_ascii=False, indent=1))
    return 0 if all(r.get("ok") for r in results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
