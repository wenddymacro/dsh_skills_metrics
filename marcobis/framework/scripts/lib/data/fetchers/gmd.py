"""Global Macro Database fetcher：``lib.fetch_data(api="gmd", ...)``。

GMD 是国家 × 年份的年度面板（https://www.globalmacrodata.com/）。网络访问和缓存都在
:mod:`lib.data.gmd_client`；这里把它接到框架的 cache-on-fetch 流程上。

序列说明（series spec）两种写法::

    series = {
        "gdp_chn": "CHN:rGDP",                 # 字符串 "ISO3:变量"
        "cpi_usa": "USA:CPI@2026_09",          # 可以用 @ 固定版本
        "infl_jpn": {"country": "JPN", "variable": "infl",
                     "version": "2026_09", "forecasts": False},
    }

默认取最新版本、去掉预测值（WEO 等来源的预测年份置为缺失）。
日期约定：每年 1 月 1 日（与 ``nbs_a`` 相同）。
"""

from __future__ import annotations

import warnings
from typing import Any, Mapping

import pandas as pd

from ..fetcher import BaseFetcher, register_fetcher
from ..gmd_client import (BASE_URLS, CITATION, GMDClient, GMDError, check_version,
                          default_client)


def parse_spec(spec: Any) -> dict[str, Any]:
    """统一成 ``{"country", "variable", "version", "forecasts"}``。"""
    if isinstance(spec, Mapping):
        out = {"country": spec.get("country") or spec.get("iso3"),
               "variable": spec.get("variable") or spec.get("var"),
               "version": spec.get("version"),
               "forecasts": bool(spec.get("forecasts", False))}
    elif isinstance(spec, str):
        body, _, ver = spec.partition("@")
        country, sep, variable = body.partition(":")
        if not sep:
            raise ValueError(f"gmd 序列说明 {spec!r} 格式不对：应为 'ISO3:变量'，如 'CHN:rGDP'")
        out = {"country": country, "variable": variable,
               "version": ver or None, "forecasts": False}
    else:
        raise TypeError(f"gmd 序列说明必须是字符串或字典，收到 {type(spec).__name__}")
    if not out["country"] or not out["variable"]:
        raise ValueError(f"gmd 序列说明缺少国家或变量：{spec!r}")
    out["country"] = str(out["country"]).strip().upper()
    out["variable"] = str(out["variable"]).strip()
    if out["version"]:
        out["version"] = check_version(str(out["version"]).strip())
    return out


class GmdFetcher(BaseFetcher):
    """Global Macro Database（年度，239 个国家 / 地区，无需 key）。"""

    name = "gmd"
    description = "Global Macro Database globalmacrodata.com（年度国家面板）"
    endpoint = BASE_URLS[0]

    def __init__(self, client: GMDClient | None = None) -> None:
        self._client = client

    @property
    def client(self) -> GMDClient:
        if self._client is None:
            self._client = default_client()
        return self._client

    def fetch(self, series: Mapping[str, Any], start=None, end=None) -> dict[str, pd.Series]:
        out: dict[str, pd.Series] = {}
        for alias, raw_spec in series.items():
            try:
                spec = parse_spec(raw_spec)
                df = self.client.wide([spec["country"]], [spec["variable"]], start, end,
                                      version=spec["version"], forecasts=spec["forecasts"])
            except (GMDError, ValueError, TypeError) as exc:
                warnings.warn(f"gmd：取 {alias!r} 失败：{exc}", UserWarning, stacklevel=2)
                continue
            col = f"{spec['variable']}_{spec['country']}"
            s = df[col].dropna() if col in df.columns else pd.Series(dtype=float)
            if s.empty:
                warnings.warn(f"gmd：{alias!r} 没有任何观测值", UserWarning, stacklevel=2)
                continue
            s = s.copy()
            s.name = alias
            s.attrs = {"gmd": {"version": df.attrs.get("gmd_version"),
                               "country": spec["country"], "variable": spec["variable"],
                               "forecasts": spec["forecasts"], "citation": CITATION}}
            out[alias] = s
        return out


register_fetcher(GmdFetcher.name, GmdFetcher)
