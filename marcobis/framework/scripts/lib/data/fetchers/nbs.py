"""国家统计局（NBS）"国家数据"平台 fetcher：``lib.fetch_data(api="nbs", ...)``。

无需 API key。网络访问、目录缓存和分段表拼接都在 :mod:`lib.data.nbs_client`；
这里只把它接到框架的 cache-on-fetch 流程上（``data/<dataset_id>/dataset.csv`` +
``metadata.yaml`` + 本地注册表）。

序列说明（series spec）有两种写法::

    # 1. 字符串："频率|目录|指标键"
    series = {
        "cpi_yoy": "M|价格指数/居民消费价格分类指数 (上年同月=100)/全国居民消费价格分类指数 (上年同月=100)|6021702000021_1",
        "gdp_q":   "Q|国民经济核算/国内生产总值 (现价)|国内生产总值当季值 (亿元)",
    }

    # 2. 字典：可以额外指定清洗步骤
    series = {
        "fai": {"freq": "M",
                "catalog": "固定资产投资 (不含农户) /固定资产投资额",
                "key": "固定资产投资额累计值 (亿元)",
                "clean": "cumulative_to_period"},
    }

* **频率**：``M`` / ``Q`` / ``A``（也接受"月度""季度""年度"）。
* **目录**：从频率根节点（"月度数据"等）往下的名称路径，用 ``/`` 分隔；或叶子目录的
  32 位 id。分段表（如"…(2016-2020)""…(2021-2025)"）写任意一段或不带时段的基础名
  都可以，会自动找齐所有分段按指标键拼接。
* **指标键**：优先用 ``ek_dp``（跨分段稳定）或指标编码（如 ``6021702000021_1``），
  也可以用显示名。用 ``python scripts/tools/nbs_tool.py indicators <目录>`` 查看。
* **clean**（仅字典写法）：``none``（默认）| ``cumulative_to_period`` |
  ``index_to_rate``。更复杂的清洗（定基指数链接等）用 :mod:`lib.preprocess.china`。

日期约定：月度 = 当月 1 日；季度 = 季末月份 1 日（与 FRED-QD 相同）；年度 = 1 月 1 日。
"""

from __future__ import annotations

import warnings
from pathlib import Path
from typing import Any, Mapping

import pandas as pd

from ..fetcher import BaseFetcher, register_fetcher
from ..nbs_client import BASE_URL, NBSBlockedError, NBSClient, NBSError, normalize_freq


def parse_spec(spec: Any) -> dict[str, Any]:
    """把字符串或字典写法统一成 ``{"freq", "catalog", "key", "clean"}``。"""
    if isinstance(spec, Mapping):
        out = {k: spec.get(k) for k in ("freq", "catalog", "key", "clean")}
    elif isinstance(spec, str):
        parts = [p.strip() for p in spec.split("|")]
        if len(parts) != 3:
            raise ValueError(
                f"nbs 序列说明 {spec!r} 格式不对：应为 '频率|目录|指标键'，"
                "例如 'M|价格指数/…/全国居民消费价格分类指数 (上年同月=100)|6021702000021_1'")
        out = {"freq": parts[0], "catalog": parts[1], "key": parts[2], "clean": None}
    else:
        raise TypeError(f"nbs 序列说明必须是字符串或字典，收到 {type(spec).__name__}")
    missing = [k for k in ("freq", "catalog", "key") if not out.get(k)]
    if missing:
        raise ValueError(f"nbs 序列说明缺少字段 {missing}：{spec!r}")
    out["freq"] = normalize_freq(out["freq"])
    out["clean"] = (out.get("clean") or "none").strip()
    if out["clean"] not in ("none", "cumulative_to_period", "index_to_rate"):
        raise ValueError(f"不支持的 clean={out['clean']!r}")
    return out


def default_cache_dir() -> Path | None:
    """目录树缓存放在 ``<项目>/data/nbs_catalog/``；找不到注册表时不缓存。"""
    try:
        from ..registry import load_registry
        return Path(load_registry()["_project_root"]) / "data" / "nbs_catalog"
    except Exception:  # noqa: BLE001
        return None


class NbsFetcher(BaseFetcher):
    """国家统计局国家数据平台（月度 / 季度 / 年度，全国数据）。"""

    name = "nbs"
    description = "国家统计局 国家数据 data.stats.gov.cn（月度 / 季度 / 年度）"
    endpoint = BASE_URL

    def __init__(self, client: NBSClient | None = None) -> None:
        self._client = client

    @property
    def client(self) -> NBSClient:
        if self._client is None:
            self._client = NBSClient(cache_dir=default_cache_dir())
        return self._client

    def fetch(
        self,
        series: Mapping[str, Any],
        start: str | pd.Timestamp | None = None,
        end: str | pd.Timestamp | None = None,
    ) -> dict[str, pd.Series]:
        from ...preprocess import china

        out: dict[str, pd.Series] = {}
        for alias, raw_spec in series.items():
            try:
                spec = parse_spec(raw_spec)
                s, meta = self.client.fetch_series(
                    spec["catalog"], spec["key"], spec["freq"], start=start, end=end)
            except NBSBlockedError:
                raise
            except (NBSError, ValueError, TypeError) as exc:
                warnings.warn(f"nbs：取 {alias!r} 失败：{exc}", UserWarning, stacklevel=2)
                continue
            if spec["clean"] == "cumulative_to_period":
                if spec["freq"] not in ("M", "Q"):
                    warnings.warn(f"nbs：{alias!r} 是年度数据，忽略 cumulative_to_period",
                                  UserWarning, stacklevel=2)
                else:
                    s = china.cumulative_to_period(s, spec["freq"])
            elif spec["clean"] == "index_to_rate":
                s = china.index_to_rate(s)
            if s.dropna().empty:
                warnings.warn(f"nbs：{alias!r} 没有任何观测值", UserWarning, stacklevel=2)
                continue
            s = s.copy()
            s.name = alias
            s.attrs = {"nbs": meta}
            out[alias] = s
        return out


register_fetcher(NbsFetcher.name, NbsFetcher)
