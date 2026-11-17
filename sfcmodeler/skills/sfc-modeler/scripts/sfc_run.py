#!/usr/bin/env python3
"""求解一个用 SFCmodeler 写的存量流量一致（SFC）模型，可施加参数冲击，输出表格、图和核对结果。

模型文件是一个普通的 .py，约定如下：

    from SFCmodeler import *

    def build():                 # 必需：返回一个 SFCmodel（参数和初始值都在这里设好）
        ...
        return SFCmodel([...], redundant_equation=...)

    def checks(model):           # 可选：返回 {名称: 应当恒为 0 的表达式}，每期核对一次
        return {"H: 供给-需求": Hs - Hh}

    PLOTS = [["Y", "C"], ["V"]]  # 可选：默认要画的变量组

用法示例：

    python3 sfc_run.py examples/sim.py --describe
    python3 sfc_run.py examples/sim.py --warmup 300 --periods 40 --shock G=25@5 --plot Y,C --plot H_h

本脚本自带上游 SFCmodeler 源码（../vendor），不需要 pip 安装 SFCmodeler 本身，
只需要它的依赖：numpy、pandas、sympy、scipy、matplotlib、tqdm、tabulate。
"""

from __future__ import annotations

import argparse
import importlib.util
import math
import os
import re
import sys
import warnings
from pathlib import Path

os.environ.setdefault("TQDM_DISABLE", "1")  # 上游每次 solve 都画进度条，命令行下只是噪音
os.environ.setdefault("MPLBACKEND", "Agg")

VENDOR = Path(__file__).resolve().parent.parent / "vendor"
sys.path.insert(0, str(VENDOR))

try:
    import numpy as np
    import pandas as pd
    import sympy as sp
    from SFCmodeler import SFCmodel, Parameter, Variable, Random  # noqa: F401
except ImportError as exc:  # pragma: no cover - 交给 sfc_doctor.py 给出安装命令
    sys.exit(f"缺少依赖：{exc}。先运行 python3 {Path(__file__).with_name('sfc_doctor.py')} 查看安装命令。")

SHOCK_RE = re.compile(r"^\s*(?P<name>[^=+*@]+?)\s*(?P<op>\+=|\*=|=)\s*(?P<value>[^@]+?)\s*(?:@\s*(?P<when>\d+))?\s*$")


class UsageError(Exception):
    """命令行参数或模型文件不符合约定。"""


# ---------------------------------------------------------------- 模型加载

def load_module(path: Path):
    if not path.is_file():
        raise UsageError(f"找不到模型文件：{path}")
    spec = importlib.util.spec_from_file_location(f"sfc_user_model_{abs(hash(path))}", path)
    module = importlib.util.module_from_spec(spec)
    sys.path.insert(0, str(path.parent))
    try:
        spec.loader.exec_module(module)
    finally:
        sys.path.remove(str(path.parent))
    if not callable(getattr(module, "build", None)):
        raise UsageError(f"{path.name} 里没有 build() 函数；模型文件必须定义 build() 并返回 SFCmodel。")
    return module


def build_model(module) -> SFCmodel:
    model = module.build()
    if not isinstance(model, SFCmodel):
        raise UsageError(f"build() 应返回 SFCmodel，实际返回了 {type(model).__name__}。")
    return model


def current_terms(model: SFCmodel) -> dict[str, object]:
    """当期（非滞后）项，按显示名和 base_name 两种写法都能查到。"""
    table: dict[str, object] = {}
    for term in model.terms:
        if getattr(term, "lag", 0) != 0:
            continue
        table[str(term)] = term
        table.setdefault(term.base_name, term)
    return table


def find_term(model: SFCmodel, name: str):
    table = current_terms(model)
    if name in table:
        return table[name]
    loose = {k.replace("{", "").replace("}", "").replace("\\", ""): v for k, v in table.items()}
    key = name.replace("{", "").replace("}", "").replace("\\", "")
    if key in loose:
        return loose[key]
    raise UsageError(f"模型里没有名为 {name!r} 的项。可用的有：{', '.join(sorted(table))}")


# ---------------------------------------------------------------- 参数解析

def parse_assignment(text: str, model: SFCmodel, allow_when: bool):
    m = SHOCK_RE.match(text)
    if not m:
        raise UsageError(f"无法解析 {text!r}；格式是 名称=值、名称+=值 或 名称*=值" + ("，可加 @期数" if allow_when else ""))
    if m["when"] and not allow_when:
        raise UsageError(f"--set 不接受 @期数：{text!r}")
    try:
        value = float(m["value"])
    except ValueError as exc:
        raise UsageError(f"{text!r} 中的值不是数字") from exc
    term = find_term(model, m["name"].strip())
    when = int(m["when"]) if m["when"] else 1
    if allow_when and when < 1:
        raise UsageError(f"冲击期数从 1 开始：{text!r}")
    return term, m["op"], value, when


def apply_value(model: SFCmodel, term, op: str, value: float) -> float:
    old = model[term]
    new = value if op == "=" else old + value if op == "+=" else old * value
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        model[term] = new
    return new


# ---------------------------------------------------------------- 求解

def run(module, sets, shocks, warmup: int, periods: int, steady_rtol: float, notes: list[str]):
    model = build_model(module)
    for term, op, value, _ in [parse_assignment(s, model, False) for s in sets]:
        apply_value(model, term, op, value)

    parsed = [parse_assignment(s, model, True) for s in shocks]
    for term, *_ in parsed:
        if not isinstance(term, Parameter):
            raise UsageError(f"只能冲击参数（Parameter）；{term} 是 {type(term).__name__}，它的值每期由方程求出。")

    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        if warmup:
            model.solve(warmup, steady={"rtol": steady_rtol, "atol": 1e-9, "ignore": []})
            n = len(model.data) - 1
            reached = model.check_steady_state(rtol=steady_rtol, atol=1e-9, ignore=[])
            notes.append(f"预热：求解 {n} 期，" + ("已到达稳态。" if reached else f"在 {warmup} 期内**未**到达稳态（rtol={steady_rtol}）。"))
        start = len(model.data) - 1  # 冲击期的计数起点
        shock_labels: list[str] = []
        for t in range(1, periods + 1):
            for term, op, value, when in parsed:
                if when == t:
                    new = apply_value(model, term, op, value)
                    # 已有多期时赋值会先开出新的一期；只有初始期时，新值从下一期起生效
                    label = model.data.index[-1] if len(model.data) > 1 else model.data.index[-1] + 1
                    notes.append(f"冲击第 {t} 期（{label}）：`{term}` → {new:g}")
                    shock_labels.append(str(label))
            model.solve(1)
    seen: dict[str, list[str]] = {}
    for w in caught:
        msg = str(w.message)
        if "Overriding lagged" in msg:
            continue
        seen.setdefault(re.sub(r" in period .*", "", msg), []).append(msg)
    for kind, msgs in seen.items():  # 同类警告只列第一条和次数，避免刷屏
        notes.append(f"警告：{msgs[0]}" + (f"（同类警告共 {len(msgs)} 条）" if len(msgs) > 1 else ""))
    return model, start, shock_labels


def tidy(model: SFCmodel) -> pd.DataFrame:
    df = model.data.df
    keep = [c for c in df.columns if getattr(c, "lag", 0) == 0]
    out = df[keep].copy()
    out.columns = [str(c) for c in keep]
    out.index = out.index.astype(str)
    out.index.name = "period"
    return out[sorted(out.columns, key=lambda c: (0 if isinstance(find_col(model, c), Variable) else 1, c))]


def find_col(model, name):
    return current_terms(model).get(name)


def evaluate_checks(module, model: SFCmodel) -> pd.DataFrame | None:
    fn = getattr(module, "checks", None)
    if not callable(fn):
        return None
    exprs = fn(model) or {}
    cols = {}
    df = model.data.df
    for label, expr in exprs.items():
        expr = sp.sympify(expr)
        syms = sorted(expr.free_symbols, key=str)
        # 滞后项若不在结果里，用当期列平移得到（与 ModelResults 的取法相同）
        series = [df[s] if s in df.columns else df[s.unlagged].shift(-s.lag) for s in syms]
        values = sp.lambdify(syms, expr, "numpy")(*[x.to_numpy(dtype=float) for x in series])
        cols[label] = np.broadcast_to(np.asarray(values, dtype=float), (len(df),)).copy()
    out = pd.DataFrame(cols, index=model.data.df.index.astype(str))
    out.index.name = "period"
    # 第一行是初始条件，不是求解出来的一期，恒等式在这里不必成立
    out.iloc[0] = np.nan
    return out


# ---------------------------------------------------------------- 输出

def plot_groups(groups, results, baseline, outdir: Path, start_label: str | None, shock_labels=()):
    """每组画一张图（图例用英文，避免缺中文字体）。"""
    import matplotlib.pyplot as plt

    # 第 0 行是初始条件（未求解），不画；有预热时从冲击前 5 期画起
    first = 1
    if start_label is not None and start_label in results.index:
        first = max(1, list(results.index).index(start_label) - 5)
    results = results.iloc[first:]
    baseline = baseline.iloc[first:] if baseline is not None else None
    files = []
    for i, group in enumerate(groups, 1):
        names = [n.strip() for n in group if n.strip()]
        missing = [n for n in names if n not in results.columns]
        if missing:
            raise UsageError(f"--plot 中的 {missing} 不在结果里。可用列：{', '.join(results.columns)}")
        fig, ax = plt.subplots(figsize=(8, 4.5))
        x = range(len(results))
        for n in names:
            line, = ax.plot(x, results[n].to_numpy(), label=n, linewidth=2)
            if baseline is not None:
                ax.plot(x, baseline[n].to_numpy(), linestyle="--", color=line.get_color(), alpha=0.6, label=f"{n} (baseline)")
        ticks = list(range(0, len(results), max(1, len(results) // 10)))
        ax.set_xticks(ticks, [results.index[t] for t in ticks], rotation=45)
        for lbl in dict.fromkeys(shock_labels):  # 竖虚线标出冲击发生的期
            if lbl in results.index:
                ax.axvline(list(results.index).index(lbl), color="grey", linewidth=1, linestyle=":")
        ax.legend()
        ax.grid(alpha=0.3)
        fig.tight_layout()
        path = outdir / f"plot_{i}_{'_'.join(re.sub(r'[^A-Za-z0-9]+', '', n) or 'x' for n in names)}.png"
        fig.savefig(path, dpi=150)
        plt.close(fig)
        files.append(path)
    return files


def fmt(x: float) -> str:
    if x is None or (isinstance(x, float) and math.isnan(x)):
        return "nan"
    return f"{x:.6g}"


def describe(model: SFCmodel) -> str:
    lines = [f"# 模型结构\n", f"方程 {len(model.equations)} 个，内生变量 {len(model.endogenous)} 个，"
             f"参数 {len(model.parameters)} 个，滞后项 {len(model.lags)} 个，随机项 {len(model.random)} 个。\n"]
    lines.append("## 方程\n")
    for eq in model.equations:
        lines.append(f"- `{eq.lhs} = {eq.rhs}`")
    if model.redundant_equation is not None:
        r = model.redundant_equation
        lines.append(f"\n冗余方程（只核对，不参与求解）：`{r.lhs} = {r.rhs}`")
    lines.append("\n## 内生变量\n\n| 名称 | 说明 | 初始值 |\n|---|---|---|")
    for v in sorted(model.endogenous, key=str):
        lines.append(f"| `{v}` | {v.description} | {fmt(model[v])} |")
    lines.append("\n## 参数\n\n| 名称 | 说明 | 值 |\n|---|---|---|")
    for p in sorted(model.parameters, key=str):
        lines.append(f"| `{p}` | {p.description} | {fmt(model[p])} |")
    missing = [str(c) for c in model.data.df.columns if pd.isna(model.data.df[c].iloc[-1])]
    if missing:
        lines.append(f"\n**缺初始值**：{', '.join(missing)}。用 --set 名称=值 补上，或在 build() 里设 Variable.default_value。")
    return "\n".join(lines)


def summary(results, baseline, diff, checks, notes, start_label, tol) -> str:
    out = ["# SFC 模型求解结果\n"]
    out += [f"- {n}" for n in notes] or ["- 无预热、无冲击。"]
    out.append(f"\n共 {len(results)} 期（{results.index[0]} 至 {results.index[-1]}）。\n")
    rows = ["| 名称 | 初始 | " + ("冲击前 | " if start_label else "") + "期末 |" + (" 期末相对基线 |" if diff is not None else ""),
            "|---|---|" + ("---|" if start_label else "") + "---|" + ("---|" if diff is not None else "")]
    for c in results.columns:
        cells = [f"`{c}`", fmt(results[c].iloc[0])]
        if start_label:
            cells.append(fmt(results.loc[start_label, c]))
        cells.append(fmt(results[c].iloc[-1]))
        if diff is not None:
            cells.append(fmt(diff[c].iloc[-1]) if c in diff else "")
        rows.append("| " + " | ".join(cells) + " |")
    out += ["## 各项取值\n"] + rows
    if checks is not None and not checks.empty:
        out.append("\n## 会计恒等式核对（应为 0；不含初始期）\n\n| 恒等式 | 最大绝对残差 | 结论 |\n|---|---|---|")
        for c in checks.columns:
            worst = float(np.nanmax(np.abs(checks[c].to_numpy()))) if checks[c].notna().any() else float("nan")
            scale = max(1.0, float(np.nanmax(np.abs(results.to_numpy()))))
            ok = worst <= tol * scale
            out.append(f"| {c} | {fmt(worst)} | {'通过' if ok else '**不通过**'} |")
    return "\n".join(out) + "\n"


# ---------------------------------------------------------------- 入口

def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="求解 SFCmodeler 模型并施加参数冲击。")
    ap.add_argument("model", type=Path, help="定义了 build() 的模型 .py 文件")
    ap.add_argument("--describe", action="store_true", help="只打印模型结构（方程、变量、参数、缺失的初始值），不求解")
    ap.add_argument("--set", action="append", default=[], metavar="名称=值", help="求解前覆盖参数或初始值，可重复")
    ap.add_argument("--warmup", type=int, default=0, metavar="N", help="先求解最多 N 期直到稳态，冲击从稳态开始")
    ap.add_argument("--steady-rtol", type=float, default=1e-6, help="稳态判定的相对容差（默认 1e-6）")
    ap.add_argument("--periods", type=int, default=20, metavar="N", help="预热之后再求解的期数（默认 20）")
    ap.add_argument("--shock", action="append", default=[], metavar="名称=值@期",
                    help="在预热后第 k 期把参数改为 值（也可用 += 或 *=），可重复；同时会跑一遍无冲击的基线")
    ap.add_argument("--plot", action="append", default=[], metavar="A,B", help="把这些列画在一张图里，可重复")
    ap.add_argument("--out", type=Path, default=None, help="输出目录（默认 ./sfc_output/<模型文件名>）")
    ap.add_argument("--check-tol", type=float, default=1e-6, help="恒等式残差的相对容差（默认 1e-6）")
    args = ap.parse_args(argv)

    try:
        module = load_module(args.model.resolve())
        if args.describe:
            model = build_model(module)
            for term, op, value, _ in [parse_assignment(s, model, False) for s in args.set]:
                apply_value(model, term, op, value)
            print(describe(model))
            return 0
        if args.periods < 1:
            raise UsageError("--periods 至少为 1")

        notes: list[str] = []
        model, start, shock_labels = run(module, args.set, args.shock, args.warmup, args.periods, args.steady_rtol, notes)
        results = tidy(model)
        start_label = results.index[start] if (args.warmup or args.shock) else None

        baseline = diff = None
        if args.shock:
            base_model, _, _ = run(module, args.set, [], args.warmup, args.periods, args.steady_rtol, [])
            baseline = tidy(base_model)
            if list(baseline.index) != list(results.index):
                notes.append("基线和冲击情形的预热期数不同（随机项？），未计算差值。")
                baseline = None
            else:
                endo = [str(v) for v in model.endogenous]
                diff = (results[endo] - baseline[endo])

        checks = evaluate_checks(module, model)

        groups = [g.split(",") for g in args.plot] or [list(g) for g in getattr(module, "PLOTS", [])]
        bad = sorted({n.strip() for g in groups for n in g if n.strip() and n.strip() not in results.columns})
        if bad:  # 写任何文件之前先检查，避免留下半套输出
            raise UsageError(f"--plot 中的 {bad} 不在结果里。可用列：{', '.join(results.columns)}")

        outdir = args.out or Path.cwd() / "sfc_output" / args.model.stem
        outdir.mkdir(parents=True, exist_ok=True)
        results.to_csv(outdir / "results.csv")
        written = [outdir / "results.csv"]
        if baseline is not None:
            baseline.to_csv(outdir / "baseline.csv")
            diff.to_csv(outdir / "diff.csv")
            written += [outdir / "baseline.csv", outdir / "diff.csv"]
        if checks is not None:
            checks.to_csv(outdir / "checks.csv")
            written.append(outdir / "checks.csv")

        written += plot_groups(groups, results, baseline, outdir, start_label, shock_labels)

        text = summary(results, baseline, diff, checks, notes, start_label, args.check_tol)
        (outdir / "summary.md").write_text(text, encoding="utf-8")
        written.append(outdir / "summary.md")
        print(text)
        print("输出文件：")
        for f in written:
            print(f"  {f}")
        return 0
    except UsageError as exc:
        print(f"错误：{exc}", file=sys.stderr)
        return 2
    except ValueError as exc:  # 上游在方程与变量不匹配、缺初始值时抛 ValueError
        print(f"错误：{exc}", file=sys.stderr)
        return 2
    except RuntimeError as exc:
        print(f"求解失败：{exc}\n提示：检查初始值是否让分母为 0、参数是否合理；可先用 --describe 查看缺失的初始值。", file=sys.stderr)
        return 3


if __name__ == "__main__":
    sys.exit(main())
