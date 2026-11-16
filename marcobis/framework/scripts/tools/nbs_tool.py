#!/usr/bin/env python3
"""国家统计局"国家数据"查询工具：浏览目录、搜索、查看指标、取单个序列。

在工作区根目录运行::

    python3 scripts/tools/nbs_tool.py browse 月度                      # 列出月度一级目录
    python3 scripts/tools/nbs_tool.py browse 月度 "价格指数/工业生产者出厂价格分类指数"
    python3 scripts/tools/nbs_tool.py search 月度 发电量                # 在目录名称中搜索（首次会遍历整棵树）
    python3 scripts/tools/nbs_tool.py indicators 季度 "国民经济核算/国内生产总值 (现价)"
    python3 scripts/tools/nbs_tool.py fetch 月度 "金融/货币供应量" 37bea7cb68064788b91d4c1aa46bf97a_1
    python3 scripts/tools/nbs_tool.py fetch 月度 "能源/能源主要产品产量/发电量" 124740339522_21 \\
            --clean cumulative_to_period --csv data/staging/electricity.csv

频率写"月度 / 季度 / 年度"或 M / Q / A。加 ``--json`` 输出 JSON。

``fetch`` 只把结果打印出来或写到 ``--csv`` 指定的文件，不改动 ``data/`` 下的注册数据集；
要长期使用，把序列加进 ``data/nbs_*/panel.yaml`` 后运行 ``nbs_update.py``，或在分析脚本里用
``lib.fetch_data(api="nbs", ...)``。
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
LIB = ROOT / "scripts" / "lib"


def _load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


nc = _load_module("_nbs_client", LIB / "data" / "nbs_client.py")
china = _load_module("_nbs_china", LIB / "preprocess" / "china.py")


def _client():
    return nc.NBSClient(cache_dir=ROOT / "data" / "nbs_catalog")


def _emit(obj, as_json: bool, text: str) -> None:
    if as_json:
        print(json.dumps(obj, ensure_ascii=False, indent=1, default=str))
    else:
        print(text)


def cmd_browse(args) -> int:
    c = _client()
    freq = nc.normalize_freq(args.freq)
    parent = c.find_catalog(args.path, freq) if args.path else None
    if parent is not None and parent.is_leaf:
        print(f"{parent.path_str} 是叶子表；用 indicators 查看其中的指标。")
        return 0
    kids = c.child_nodes(parent, freq)
    rows = [{"name": k.name, "id": k.id, "leaf": k.is_leaf, "sdate": k.sdate, "edate": k.edate}
            for k in kids]
    lines = [f"{nc.FREQS[freq]['name']} / {parent.path_str if parent else ''}"]
    for k in kids:
        mark = "·" if k.is_leaf else "▸"
        span = f"  [{k.sdate or ''}–{k.edate or ''}]" if (k.sdate or k.edate) else ""
        lines.append(f"  {mark} {k.name}{span}")
    lines.append("（▸ 目录，· 数据表）")
    _emit(rows, args.json, "\n".join(lines))
    return 0


def cmd_search(args) -> int:
    c = _client()
    freq = nc.normalize_freq(args.freq)
    hits = c.search(args.keywords, freq)
    rows = [{"path": h.path_str, "id": h.id, "sdate": h.sdate, "edate": h.edate} for h in hits]
    text = "\n".join(f"  {h.path_str}" for h in hits[: args.limit]) or "  （没有匹配）"
    if len(hits) > args.limit:
        text += f"\n  …共 {len(hits)} 条，只显示前 {args.limit} 条（--limit 调整）"
    _emit(rows, args.json, text)
    return 0


def cmd_indicators(args) -> int:
    c = _client()
    freq = nc.normalize_freq(args.freq)
    node = c.find_catalog(args.path, freq)
    segs = c.segments(node, freq)
    latest = segs[-1]
    inds = c.indicators(latest.id)
    codes = [i.code for i in inds]
    rows = [{"code": i.code, "ek_dp": i.key, "name": i.name, "unit": i.unit,
             "code_unique": codes.count(i.code) == 1} for i in inds]
    lines = [f"{node.path_str}",
             f"  分段表 {len(segs)} 张：" + "；".join(s.name for s in segs),
             f"  以下为最新一段（{latest.name}）的指标。指标键优先用「编码」，编码不唯一（标 *）时用显示名："]
    for r in rows:
        star = "" if r["code_unique"] else " *"
        lines.append(f"    {r['code']}{star} | {r['name']} | {r['unit'] or ''}")
    _emit({"catalog": node.path_str, "segments": [s.name for s in segs], "indicators": rows},
          args.json, "\n".join(lines))
    return 0


def cmd_fetch(args) -> int:
    c = _client()
    freq = nc.normalize_freq(args.freq)
    s, meta = c.fetch_series(args.path, args.key, freq, start=args.start, end=args.end)
    for step in args.clean or []:
        if step == "cumulative_to_period":
            s = china.cumulative_to_period(s, freq)
        elif step == "fill_january":
            s = china.fill_january(s)
        elif step == "index_to_rate":
            s = china.index_to_rate(s)
    nn = s.dropna()
    if args.csv:
        out = Path(args.csv)
        out.parent.mkdir(parents=True, exist_ok=True)
        s.rename(args.name or meta["code"]).to_frame().to_csv(out, index_label="date")
    summary = {"name": meta["name"], "key": meta["key"], "unit": meta["unit"],
               "n_obs": int(len(nn)),
               "start": str(nn.index.min().date()) if len(nn) else None,
               "end": str(nn.index.max().date()) if len(nn) else None,
               "segments": meta["segments"], "overlap_conflicts": meta["overlap_conflicts"],
               "clean": args.clean or [], "csv": args.csv}
    tail = "\n".join(f"    {d.date()}  {v:,.12g}" for d, v in nn.tail(args.tail).items())
    text = (f"{meta['name']}（{meta['unit'] or '无单位'}）\n"
            f"  指标键 {meta['key']}\n"
            f"  {summary['n_obs']} 期，{summary['start']} – {summary['end']}，"
            f"拼接 {len(meta['segments'])} 段" +
            (f"，重叠期冲突 {len(meta['overlap_conflicts'])} 处" if meta["overlap_conflicts"] else "") +
            (f"\n  已写入 {args.csv}" if args.csv else "") +
            f"\n  最近 {args.tail} 期：\n{tail}")
    _emit(summary, args.json, text)
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="国家统计局国家数据查询工具")
    ap.add_argument("--json", action="store_true", help="输出 JSON")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("browse", help="列出某个目录的子目录 / 数据表")
    p.add_argument("freq")
    p.add_argument("path", nargs="?", default="")
    p.set_defaults(fn=cmd_browse)

    p = sub.add_parser("search", help="在目录名称中搜索数据表")
    p.add_argument("freq")
    p.add_argument("keywords", nargs="+")
    p.add_argument("--limit", type=int, default=40)
    p.set_defaults(fn=cmd_search)

    p = sub.add_parser("indicators", help="列出数据表中的指标及指标键")
    p.add_argument("freq")
    p.add_argument("path")
    p.set_defaults(fn=cmd_indicators)

    p = sub.add_parser("fetch", help="取单个指标（自动拼接分段表）")
    p.add_argument("freq")
    p.add_argument("path")
    p.add_argument("key")
    p.add_argument("--start")
    p.add_argument("--end")
    p.add_argument("--clean", action="append",
                   choices=["cumulative_to_period", "fill_january", "index_to_rate"])
    p.add_argument("--csv", help="把结果写到这个 CSV 文件")
    p.add_argument("--name", help="CSV 中的列名")
    p.add_argument("--tail", type=int, default=6)
    p.set_defaults(fn=cmd_fetch)

    args = ap.parse_args(argv)
    try:
        return args.fn(args)
    except nc.NBSError as exc:
        print(f"错误：{exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
