"""中国官方统计数据的清洗工具（国家统计局口径）。

NBS 公布数据有几个常见特点，直接放进 VAR 之前需要先处理：

1. **只公布累计值。** 固定资产投资、财政收支、工业企业利润等只有"1–N 月累计"；
   季度 GDP 也同时有"当季值"和"累计值"。:func:`cumulative_to_period` 把累计值
   差分成当月 / 当季值。
2. **1–2 月合并公布。** 受春节影响，很多月度指标不单独公布 1 月数据，2 月公布的
   是 1–2 月合计。``jan_feb`` 参数决定怎么处理：平均拆分到 1、2 月（``"split"``，
   默认），1 月记缺失、2 月记合计（``"combined"``），或两个月都记缺失（``"nan"``）。
3. **价格指数只有同比 / 环比。** CPI、PPI 等以"上年同月=100""上月=100"公布，
   没有官方定基序列。:func:`chain_index` 用环比连乘构造定基指数，环比缺失的时段
   用同比向前 / 向后递推补齐，最后按指定基期重新定基。
4. **同比指数转增长率。** :func:`index_to_rate` 把"上年同期=100"转成百分比增长率。

所有函数都是无状态的：输入 Series，返回新的 Series，不修改输入。返回值的
``attrs["preprocess_applied"]`` 记录做过的处理，便于研究日志追溯。
"""

from __future__ import annotations

from typing import Literal

import numpy as np
import pandas as pd

JanFeb = Literal["split", "combined", "nan"]


def _record(s: pd.Series, step: str) -> pd.Series:
    steps = list(s.attrs.get("preprocess_applied", []))
    steps.append(step)
    s.attrs["preprocess_applied"] = steps
    return s


def _check_index(s: pd.Series) -> None:
    if not isinstance(s.index, pd.DatetimeIndex):
        raise TypeError("需要以 DatetimeIndex 为索引的 Series")
    if s.index.has_duplicates:
        raise ValueError("索引中有重复日期")


def regularize(s: pd.Series, freq: str) -> pd.Series:
    """把序列补齐到完整的月度 / 季度 / 年度日历（缺的期记 NaN）。

    日期约定与 :mod:`lib.data.nbs_client` 一致：月度为当月 1 日，季度为季末月份
    1 日，年度为 1 月 1 日。
    """
    _check_index(s)
    s = s.sort_index()
    if s.dropna().empty:
        return s
    f = {"M": "MS", "Q": "QS-MAR", "A": "YS"}[freq]
    full = pd.date_range(s.index.min(), s.index.max(), freq=f)
    return s.reindex(full).rename_axis(s.index.name or "date")


def cumulative_to_period(
    s: pd.Series,
    freq: Literal["M", "Q"] = "M",
    *,
    jan_feb: JanFeb = "split",
) -> pd.Series:
    """把年内累计值（1–N 月 / 1–N 季累计）转成当期值。

    规则：

    * 当期值 = 本期累计 − 上期累计（同一年内）；
    * 每年第一期（1 月 / 一季度）的当期值就是累计值本身；
    * 上一期累计缺失（1 月除外）时，本期当期值记缺失，绝不跨期瞎补；
    * 月度数据 1 月缺失、2 月有值时，2 月的累计就是 1–2 月合计，按 ``jan_feb`` 处理：

      - ``"split"``：1、2 月各记合计的一半（默认，常用做法，春节错月影响被平均掉）；
      - ``"combined"``：1 月记缺失，2 月记 1–2 月合计；
      - ``"nan"``：1、2 月都记缺失。

    Parameters
    ----------
    s : pd.Series
        累计值序列（水平值，如亿元）。**不要**用于累计增长率：增长率不能差分。
    freq : {"M", "Q"}
    jan_feb : {"split", "combined", "nan"}
    """
    _check_index(s)
    if freq not in ("M", "Q"):
        raise ValueError("freq 只能是 'M' 或 'Q'")
    s = regularize(s.astype(float), freq)
    out = pd.Series(np.nan, index=s.index, name=s.name, dtype=float)
    for year, grp in s.groupby(s.index.year):
        prev_val: float | None = 0.0  # 年初累计为 0
        prev_period = 0
        for ts, val in grp.items():
            period = ts.month if freq == "M" else (ts.month // 3)
            if np.isnan(val):
                prev_val, prev_period = None, period
                continue
            jan_missing = (prev_period == 1 and prev_val is None) or prev_period == 0
            if freq == "M" and period == 2 and jan_missing:
                # 1 月缺失、2 月有值：2 月累计 = 1–2 月合计
                if jan_feb == "split":
                    out.loc[pd.Timestamp(year=year, month=1, day=1)] = val / 2.0
                    out.loc[ts] = val / 2.0
                elif jan_feb == "combined":
                    out.loc[ts] = val
                # "nan"：两个月都留空
                prev_val, prev_period = val, period
                continue
            if prev_val is not None and period == prev_period + 1:
                out.loc[ts] = val - prev_val
            elif prev_period == 0 and period == 1:
                out.loc[ts] = val
            prev_val, prev_period = val, period
    out = out.sort_index()
    out.attrs = dict(s.attrs)
    return _record(out, f"cumulative_to_period(freq={freq}, jan_feb={jan_feb})")


def index_to_rate(s: pd.Series, base: float = 100.0) -> pd.Series:
    """把"上年同期=100""上月=100"这类指数转成百分比增长率（指数 − 100）。"""
    out = s.astype(float) - base
    out.attrs = dict(s.attrs)
    return _record(out, f"index_to_rate(base={base})")


def chain_index(
    mom: pd.Series | None = None,
    yoy: pd.Series | None = None,
    *,
    freq: Literal["M", "Q"] = "M",
    base: str | int | None = None,
    mom_start: str | pd.Timestamp | None = None,
) -> pd.Series:
    """用环比（上期=100）和同比（上年同期=100）构造定基指数。

    步骤：

    1. 在环比可用的最长连续区间内连乘：``I_t = I_{t-1} × mom_t / 100``；
    2. 区间以前，用同比向前递推：``I_{t-L} = I_t / (yoy_t / 100)``（月度 L=12，季度 L=4）；
    3. 区间以后，环比缺失但同比有值时向后递推：``I_t = I_{t-L} × yoy_t / 100``；
    4. 没有环比时只用同比递推，以同比序列最后 L 期为锚（各自记为 100），
       这种情况下季节形态无法识别，只适合作同比口径分析，``attrs`` 中会注明；
    5. 若给出 ``base``（如 ``2015`` 或 ``"2015-01"``），把该年平均值 / 该期值重定为 100。

    由于 NBS 公布的同比、环比都只保留一位小数，两种方式递推出的指数会有舍入误差；
    函数在 ``attrs["chain_check"]`` 里给出重叠期"由定基指数算出的同比"与"官方同比"
    的最大绝对偏差，供核对。

    ``mom_start``：只使用这一期及以后的环比。早期官方环比与同比明显不一致时（例如
    全国 CPI 2000–2001 年，12 个月环比连乘与同比最多相差约 4.8 个百分点），用它让早期
    改由同比回推。
    """
    if mom is None and yoy is None:
        raise ValueError("mom 和 yoy 至少要给一个")
    lag = 12 if freq == "M" else 4
    pieces = [x for x in (mom, yoy) if x is not None]
    for x in pieces:
        _check_index(x)
    start = min(x.dropna().index.min() for x in pieces if not x.dropna().empty)
    end = max(x.dropna().index.max() for x in pieces if not x.dropna().empty)
    f = {"M": "MS", "Q": "QS-MAR"}[freq]
    if yoy is not None:
        # 同比可以把水平向前多推一年（第一期同比对应的上年同期），日历相应向前延伸
        start = start - pd.DateOffset(months=12)
    idx = pd.date_range(start, end, freq=f)
    m = mom.reindex(idx).astype(float) if mom is not None else pd.Series(np.nan, index=idx)
    if mom_start is not None:
        m[m.index < pd.Timestamp(mom_start)] = np.nan
    y = yoy.reindex(idx).astype(float) if yoy is not None else pd.Series(np.nan, index=idx)

    level = pd.Series(np.nan, index=idx, dtype=float)
    method: list[str] = []
    valid = m.notna().to_numpy()
    if valid.any():
        # 环比最长连续区间
        best_len, best_start, run_start = 0, 0, None
        for i, ok in enumerate(list(valid) + [False]):
            if ok and run_start is None:
                run_start = i
            elif not ok and run_start is not None:
                if i - run_start > best_len:
                    best_len, best_start = i - run_start, run_start
                run_start = None
        # 区间第一期的环比无法使用（缺上一期水平），把上一期设为锚点 100
        anchor = best_start - 1 if best_start > 0 else best_start
        level.iloc[anchor] = 100.0
        for i in range(anchor + 1, best_start + best_len):
            level.iloc[i] = level.iloc[i - 1] * m.iloc[i] / 100.0
        method.append(f"环比连乘 {idx[anchor].date()}–{idx[best_start + best_len - 1].date()}")
    else:
        last = y.dropna().index.max()
        pos = idx.get_loc(last)
        for i in range(pos - lag + 1, pos + 1):
            if i >= 0:
                level.iloc[i] = 100.0
        method.append(f"仅同比递推（锚：{idx[max(pos - lag + 1, 0)].date()}–{last.date()} 各期=100，季节形态不可识别）")

    # 向前（更早）用同比回推
    back = 0
    for i in range(len(idx) - 1, -1, -1):
        if np.isnan(level.iloc[i]) and i + lag < len(idx):
            nxt, g = level.iloc[i + lag], y.iloc[i + lag]
            if not np.isnan(nxt) and not np.isnan(g) and g != 0:
                level.iloc[i] = nxt / (g / 100.0)
                back += 1
    # 向后（更晚）用同比递推
    fwd = 0
    for i in range(len(idx)):
        if np.isnan(level.iloc[i]) and i - lag >= 0:
            prv, g = level.iloc[i - lag], y.iloc[i]
            if not np.isnan(prv) and not np.isnan(g):
                level.iloc[i] = prv * g / 100.0
                fwd += 1
    if back:
        method.append(f"同比回推 {back} 期")
    if fwd:
        method.append(f"同比外推 {fwd} 期")

    if base is not None:
        b = str(base)
        sel = level.loc[b] if len(b) > 4 else level[level.index.year == int(b)]
        ref = float(np.nanmean(np.atleast_1d(sel)))
        if not np.isfinite(ref) or ref == 0:
            raise ValueError(f"基期 {base!r} 没有可用的指数值")
        level = level / ref * 100.0
        method.append(f"基期 {base}=100")

    # 核对：定基指数算出的同比 vs 官方同比
    check = None
    if yoy is not None:
        implied = level / level.shift(lag) * 100.0
        diff = (implied - y).abs().dropna()
        if len(diff):
            check = {"max_abs_diff_pp": round(float(diff.max()), 4),
                     "mean_abs_diff_pp": round(float(diff.mean()), 4),
                     "n": int(len(diff))}
    level = level.loc[level.first_valid_index():] if level.notna().any() else level
    level.name = (mom.name if mom is not None else yoy.name)
    level.index.name = "date"
    level.attrs = {"chain_method": "；".join(method), "chain_check": check}
    return _record(level, f"chain_index(freq={freq}, base={base})")


def splice_ratio(old: pd.Series, new: pd.Series, *, overlap: int = 12) -> pd.Series:
    """口径变化时的比例衔接：用重叠期均值之比把旧序列调整到新口径，再与新序列拼接。

    适用于基期调整、统计范围变化（如规模以上工业口径调整）这类水平断点。
    重叠期少于 1 期时报错，不做无依据的衔接。
    """
    _check_index(old)
    _check_index(new)
    common = old.dropna().index.intersection(new.dropna().index)
    if len(common) == 0:
        raise ValueError("新旧序列没有重叠期，无法比例衔接")
    common = common.sort_values()[-overlap:]
    ratio = float(new.loc[common].mean() / old.loc[common].mean())
    head = old[old.index < new.dropna().index.min()] * ratio
    out = pd.concat([head, new.dropna()]).sort_index()
    out.name = new.name
    out.attrs = {"splice_ratio": ratio, "splice_overlap": [str(common.min().date()), str(common.max().date())]}
    return _record(out, f"splice_ratio(overlap={len(common)})")


def fill_january(s: pd.Series, ytd: pd.Series | None = None) -> pd.Series:
    """补齐 1 月（及 1–2 月）未单独公布的月度增长率。

    * 只给 ``s``：1 月缺失、同年 2 月有值时，1 月取 2 月的值（2 月公布的是 1–2 月累计同比）。
    * 同时给 ``ytd``（同一指标的"累计增长"序列）：1 月和 / 或 2 月缺失时，都取 ``ytd`` 的 2 月值，
      即 1–2 月累计同比。这对应 NBS 只公布"1–2 月累计增长"、不公布当月同比的年份
      （例如规上工业增加值 2013–2019 年）。

    适用于增长率类月度序列。其他缺失原样保留。填补的日期记录在 ``attrs["filled_january"]``。
    """
    _check_index(s)
    s = regularize(s.astype(float), "M")
    if ytd is not None:
        _check_index(ytd)
        ytd = ytd.astype(float)
    out = s.copy()
    filled = []
    years = sorted(set(s.index.year) | (set(ytd.dropna().index.year) if ytd is not None else set()))
    for year in years:
        jan = pd.Timestamp(year=year, month=1, day=1)
        feb = pd.Timestamp(year=year, month=2, day=1)
        jan_val = out.get(jan, np.nan)
        feb_val = out.get(feb, np.nan)
        ytd_feb = ytd.get(feb, np.nan) if ytd is not None else np.nan
        source = ytd_feb if not np.isnan(ytd_feb) else feb_val
        if np.isnan(source):
            continue
        if np.isnan(jan_val):
            out.loc[jan] = source
            filled.append(str(jan.date()))
        if np.isnan(feb_val) and not np.isnan(ytd_feb):
            out.loc[feb] = ytd_feb
            filled.append(str(feb.date()))
    out = out.sort_index()
    if len(out.dropna()):
        out = out.loc[out.first_valid_index():]
    out.attrs = dict(s.attrs)
    out.attrs["filled_january"] = filled
    return _record(out, f"fill_january(n={len(filled)}, ytd={'yes' if ytd is not None else 'no'})")
