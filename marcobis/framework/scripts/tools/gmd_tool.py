#!/usr/bin/env python3
"""Global Macro Database（GMD）工具：下载版本、查变量和国家、切取数据。

在工作区根目录运行::

    python3 scripts/tools/gmd_tool.py versions                 # 可用版本（新的在前）
    python3 scripts/tools/gmd_tool.py update                   # 下载最新版本到 data/gmd/cache/（约 30 MB）
    python3 scripts/tools/gmd_tool.py update --version 2026_06 # 下载指定版本
    python3 scripts/tools/gmd_tool.py vars                     # 变量、单位、定义
    python3 scripts/tools/gmd_tool.py vars rate                # 按名称 / 定义搜索
    python3 scripts/tools/gmd_tool.py countries china          # 查 ISO3 代码和样本起止年份
    python3 scripts/tools/gmd_tool.py coverage CHN USA --vars rGDP CPI strate   # 每个序列的起止年份
    python3 scripts/tools/gmd_tool.py extract --countries CHN USA JPN --vars rGDP CPI \\
            --start 1960 --csv data/staging/gmd_g3.csv           # 宽表（rGDP_CHN …）
    python3 scripts/tools/gmd_tool.py extract --countries CHN --vars infl --long --forecasts
    python3 scripts/tools/gmd_tool.py raw CPI --country CHN    # 某变量各来源的原始值与拼接链

加 ``--json`` 输出 JSON。``update`` 写入 ``data/gmd/``（缓存、``metadata.yaml``、``varlist.csv``、
``countries.csv``）；``extract`` 只打印或写到 ``--csv`` 指定的文件。

GMD 学术用途免费，其他用途需要作者书面许可；引用 Müller, Xu, Lehbib & Chen (2025), NBER WP 33714。
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
LIB = ROOT / "scripts" / "lib"
GMD_DIR = ROOT / "data" / "gmd"


def _load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


gc = _load_module("_gmd_client", LIB / "data" / "gmd_client.py")


def _client():
    return gc.GMDClient(cache_dir=GMD_DIR / "cache")


def _emit(obj, as_json: bool, text: str) -> None:
    if as_json:
        print(json.dumps(obj, ensure_ascii=False, indent=1, default=str))
    else:
        print(text)


def _version(c, args) -> str:
    """用户指定的版本；否则本机已下载的最新版本；都没有时提示先 update。"""
    if args.version:
        return gc.check_version(args.version)
    cached = c.cached_versions()
    if cached:
        return cached[0]
    raise SystemExit("本机还没有 GMD 数据：先运行 python3 scripts/tools/gmd_tool.py update")


def cmd_versions(args) -> int:
    c = _client()
    vs = c.versions()
    cached = set(c.cached_versions())
    lines = [f"{v}{'  （已下载）' if v in cached else ''}" for v in vs]
    _emit({"versions": vs, "cached": sorted(cached, reverse=True)}, args.json,
          "GMD 可用版本（新的在前）：\n" + "\n".join("  " + s for s in lines))
    return 0


def cmd_update(args) -> int:
    import yaml

    c = _client()
    ver = c.resolve_version(args.version)
    print(f"下载 GMD {ver}（约 30 MB）…", file=sys.stderr)
    c.download(ver, refresh=args.refresh)
    df = c.panel(ver)
    var = c.varlist(refresh=True)
    GMD_DIR.mkdir(parents=True, exist_ok=True)
    var.to_csv(GMD_DIR / "varlist.csv", index=False)
    countries = c.countries(ver)
    countries.to_csv(GMD_DIR / "countries.csv", index=False)
    variables = c.variables(ver)
    meta = {
        "dataset": "gmd",
        "source": "Global Macro Database",
        "url": gc.HOMEPAGE,
        "license": "学术用途免费；其他用途需作者书面许可（" + gc.LICENSE_URL + "）",
        "citation": gc.CITATION,
        "vintage": ver,
        "downloaded_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "file": f"cache/GMD_{ver}.csv",
        "rows": int(len(df)),
        "countries": int(df["ISO3"].nunique()),
        "year_min": int(df["year"].min()),
        "year_max": int(df["year"].max()),
        "variables": variables,
        "forecast_note": "forecast_<变量> = 1 的年份是预测值；lib.load_gmd 默认把它们置为缺失",
    }
    (GMD_DIR / "metadata.yaml").write_text(
        yaml.safe_dump(meta, allow_unicode=True, sort_keys=False), encoding="utf-8")
    summary = {k: meta[k] for k in ("vintage", "rows", "countries", "year_min", "year_max")}
    summary["n_variables"] = len(variables)
    summary["path"] = str(GMD_DIR)
    _emit(summary, args.json,
          f"✓ GMD {ver}：{summary['countries']} 个国家 / 地区，{summary['n_variables']} 个变量，"
          f"{summary['year_min']}–{summary['year_max']}（含预测年份），写入 {GMD_DIR}")
    return 0


def cmd_vars(args) -> int:
    c = _client()
    df = c.varlist()
    if args.query:
        q = args.query.lower()
        mask = (df["variable"].str.lower().str.contains(q, regex=False)
                | df["definition"].str.lower().str.contains(q, regex=False)
                | df["units"].str.lower().str.contains(q, regex=False))
        df = df[mask]
    rows = df.to_dict("records")
    text = "\n".join(f"{r['variable']:<18} {r['units']:<22} {r['definition'][:90]}" for r in rows)
    _emit(rows, args.json, text or "没有匹配的变量")
    return 0


def cmd_countries(args) -> int:
    c = _client()
    df = c.countries(_version(c, args))
    if args.query:
        q = args.query.lower()
        df = df[df["ISO3"].str.lower().str.contains(q, regex=False)
                | df["countryname"].astype(str).str.lower().str.contains(q, regex=False)]
    rows = df.to_dict("records")
    text = "\n".join(f"{r['ISO3']}  {str(r.get('countryname')):<32} {str(r.get('income_group') or ''):<20} "
                     f"{r['first_year']}–{r['last_year']}" for r in rows)
    _emit(rows, args.json, text or "没有匹配的国家")
    return 0


def cmd_coverage(args) -> int:
    c = _client()
    long = c.extract(args.countries, args.vars, version=_version(c, args), forecasts=False)
    rows = []
    for iso, g in long.groupby("ISO3"):
        for v in args.vars:
            s = g.set_index("year")[v].dropna()
            rows.append({"ISO3": iso, "variable": v, "n_obs": int(s.size),
                         "first_year": int(s.index.min()) if s.size else None,
                         "last_year": int(s.index.max()) if s.size else None,
                         "gaps": int((s.index.max() - s.index.min() + 1 - s.size)) if s.size else None})
    text = "\n".join(f"{r['ISO3']}  {r['variable']:<14} {r['first_year']}–{r['last_year']}  "
                     f"n={r['n_obs']}  缺口={r['gaps']}" for r in rows)
    _emit(rows, args.json, "实际值（不含预测）覆盖：\n" + text)
    return 0


def cmd_extract(args) -> int:
    c = _client()
    ver = _version(c, args)
    if args.long:
        df = c.extract(args.countries, args.vars, args.start, args.end,
                       version=ver, forecasts=args.forecasts)
    else:
        df = c.wide(args.countries, args.vars, args.start, args.end,
                    version=ver, forecasts=args.forecasts)
    if args.csv:
        out = Path(args.csv)
        out.parent.mkdir(parents=True, exist_ok=True)
        df.to_csv(out, index=not args.long)
        print(f"✓ 写入 {out}（GMD {ver}，{len(df)} 行 × {df.shape[1]} 列）")
    elif args.json:
        print(df.reset_index().to_json(orient="records", force_ascii=False, date_format="iso"))
    else:
        print(f"# GMD {ver}{'（含预测值）' if args.forecasts else ''}")
        print(df.to_string(max_rows=args.max_rows))
    return 0


def cmd_raw(args) -> int:
    c = _client()
    ver = _version(c, args)
    df = c.raw_sources(args.variable, ver)
    if args.country:
        df = df[df["ISO3"].isin([x.upper() for x in args.country])]
    df = df.dropna(axis=1, how="all")
    if args.csv:
        df.to_csv(args.csv, index=False)
        print(f"✓ 写入 {args.csv}")
    else:
        print(df.to_string(max_rows=args.max_rows))
    return 0


def main(argv: list[str] | None = None) -> int:
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--json", action="store_true", default=argparse.SUPPRESS, help="输出 JSON")
    ap = argparse.ArgumentParser(description="Global Macro Database 工具", parents=[common])
    sub = ap.add_subparsers(dest="cmd", required=True)
    _add = sub.add_parser
    sub.add_parser = lambda *a, **k: _add(*a, parents=[common], **k)

    sub.add_parser("versions", help="列出可用版本").set_defaults(func=cmd_versions)

    p = sub.add_parser("update", help="下载一个版本到 data/gmd/")
    p.add_argument("--version", help="版本号，如 2026_09（默认最新）")
    p.add_argument("--refresh", action="store_true", help="已下载也重新下载")
    p.set_defaults(func=cmd_update)

    p = sub.add_parser("vars", help="变量表")
    p.add_argument("query", nargs="?")
    p.set_defaults(func=cmd_vars)

    p = sub.add_parser("countries", help="国家 / 地区代码")
    p.add_argument("query", nargs="?")
    p.add_argument("--version")
    p.set_defaults(func=cmd_countries)

    p = sub.add_parser("coverage", help="每个国家-变量的样本起止年份")
    p.add_argument("countries", nargs="+")
    p.add_argument("--vars", nargs="+", required=True)
    p.add_argument("--version")
    p.set_defaults(func=cmd_coverage)

    p = sub.add_parser("extract", help="切取数据")
    p.add_argument("--countries", nargs="+", required=True, help="ISO3 代码")
    p.add_argument("--vars", nargs="+", required=True)
    p.add_argument("--start")
    p.add_argument("--end")
    p.add_argument("--version")
    p.add_argument("--forecasts", action="store_true", help="保留预测值（默认置为缺失）")
    p.add_argument("--long", action="store_true", help="输出长表（ISO3, year, 变量…）")
    p.add_argument("--csv", help="写到文件")
    p.add_argument("--max-rows", type=int, default=60)
    p.set_defaults(func=cmd_extract)

    p = sub.add_parser("raw", help="某变量各来源的原始值与拼接链")
    p.add_argument("variable")
    p.add_argument("--country", nargs="+")
    p.add_argument("--version")
    p.add_argument("--csv")
    p.add_argument("--max-rows", type=int, default=60)
    p.set_defaults(func=cmd_raw)

    args = ap.parse_args(argv)
    args.json = getattr(args, "json", False)
    try:
        return args.func(args)
    except gc.GMDError as exc:
        print(f"✗ {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
