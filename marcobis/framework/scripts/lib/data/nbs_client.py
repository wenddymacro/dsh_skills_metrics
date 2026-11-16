"""国家统计局（NBS）"国家数据"平台的轻量客户端（仅用标准库访问网络）。

数据源：https://data.stats.gov.cn/dg/website/ （2025 年改版后的新平台）。
旧的 ``easyquery.htm`` 接口已被防火墙拦截（HTTP 403），这里只使用新平台
前端实际调用的四个公开接口，无需登录、无需 API key：

=====================================  ====================================
接口                                   作用
=====================================  ====================================
``GET  new/queryIndexTreeAsync``       指标目录树（逐层展开）
``GET  new/queryIndicatorsByCid``      某个目录叶子下的指标列表
``POST stream/esData``                 取数：目录 + 指标 + 地区 + 时间范围
=====================================  ====================================

三种频率对应三棵目录树：

====  ==========  ===============  ===================
频率  树 code     时间代码后缀     时间范围示例
====  ==========  ===============  ===================
M     1           ``MM``           ``200001MM-202612MM``
Q     2           ``SS``           ``199201SS-202604SS``（季度写成 01–04）
A     3           ``YY``           ``1978YY-2025YY``
====  ==========  ===============  ===================

**分段表。** NBS 经常把同一指标按统计口径拆成几张表，例如
"全国居民消费价格分类指数 (上年同月=100) (2016-2020)""(2021-2025)""(2026-)"。
每张表只返回自己时段内的数据。不同分段之间唯一稳定的指标键是 ``ek_dp``
（指标编码 + 口径，例如 ``6021702000021|b504…_1``），显示名会随分段变化，
不能用来拼接。:func:`fetch_series` 会自动找到同一父目录下的兄弟分段，
按 ``ek_dp`` 拼接，并在重叠期优先采用较新的分段。

这个模块只负责"说话"：网络请求、目录缓存、分段拼接。数据清洗（累计值转当期值、
同比链接成定基指数等）在 :mod:`lib.preprocess.china`。
"""

from __future__ import annotations

import http.client
import json
import re
import ssl
import time
import urllib.error
import urllib.parse
import urllib.request
import warnings
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable, Sequence

import pandas as pd

BASE_URL = "https://data.stats.gov.cn/dg/website/publicrelease/web/external"
WEB_URL = "https://data.stats.gov.cn/dg/website/page.html"
NATIONAL_AREA = {"text": "全国", "value": "000000000000"}

USER_AGENT = (
    "Mozilla/5.0 (compatible; marco-bis-nbs/1.0; "
    "+https://github.com/wenddymacro/dsh_skills_metrics)"
)

FREQS: dict[str, dict[str, Any]] = {
    "M": {"code": 1, "suffix": "MM", "name": "月度", "label": "monthly"},
    "Q": {"code": 2, "suffix": "SS", "name": "季度", "label": "quarterly"},
    "A": {"code": 3, "suffix": "YY", "name": "年度", "label": "annual"},
}

#: 分段表名称末尾的时段标记，例如 "(2016-2020)""(-2015)""(2026-)""（2019-）"。
_SEGMENT_RE = re.compile(r"\s*[\(（]\s*(\d{4})?\s*[-—–至]\s*(\d{4}|至今)?\s*[\)）]\s*$")


class NBSError(RuntimeError):
    """NBS 接口返回错误或无法解析。"""


class NBSBlockedError(NBSError):
    """网站防火墙返回了人机验证页或跳转：本机 IP 暂时被限制访问。

    遇到它要立即停止所有请求，等几个小时后再试。不要重试、不要并发、也不要尝试绕过验证。
    """


BLOCKED_HINT = (
    "国家数据网站的防火墙返回了人机验证页（或跳转），说明这台机器的 IP 因请求过密被暂时限制。"
    "已停止全部请求。请过几个小时再运行；不要并行运行多个下载进程。"
    f"可以先在浏览器里打开 {WEB_URL} 确认网站本身可以访问。"
)


def normalize_freq(freq: str) -> str:
    """把 'M' / 'monthly' / '月度' 等写法统一成 'M' | 'Q' | 'A'。"""
    f = str(freq).strip()
    aliases = {
        "m": "M", "monthly": "M", "month": "M", "月": "M", "月度": "M",
        "q": "Q", "quarterly": "Q", "quarter": "Q", "季": "Q", "季度": "Q",
        "a": "A", "y": "A", "annual": "A", "yearly": "A", "year": "A",
        "年": "A", "年度": "A",
    }
    out = aliases.get(f.lower(), aliases.get(f))
    if out is None:
        raise ValueError(f"无法识别的频率 {freq!r}；可用 M / Q / A")
    return out


def segment_base_name(name: str) -> str:
    """去掉分段表名称末尾的时段标记，得到可以比较的基础名称。

    >>> segment_base_name("全国居民消费价格分类指数 (上年同月=100) (2016-2020) ")
    '全国居民消费价格分类指数 (上年同月=100)'
    """
    return _SEGMENT_RE.sub("", name.strip()).strip()


def segment_bounds(name: str) -> tuple[int | None, int | None]:
    """分段表名称里的起止年份；没有时段标记时返回 ``(None, None)``。"""
    m = _SEGMENT_RE.search(name.strip())
    if not m:
        return (None, None)
    start = int(m.group(1)) if m.group(1) else None
    end = int(m.group(2)) if m.group(2) and m.group(2).isdigit() else None
    return (start, end)


# ---------------------------------------------------------------------------
# 时间代码
# ---------------------------------------------------------------------------

def period_code(ts: pd.Timestamp | str, freq: str) -> str:
    """把日期转成 NBS 时间代码（不带后缀）：M→YYYYMM，Q→YYYY0q，A→YYYY。"""
    freq = normalize_freq(freq)
    ts = pd.Timestamp(ts)
    if freq == "M":
        return f"{ts.year:04d}{ts.month:02d}"
    if freq == "Q":
        return f"{ts.year:04d}{(ts.month - 1) // 3 + 1:02d}"
    return f"{ts.year:04d}"


def code_to_timestamp(code: str, freq: str) -> pd.Timestamp:
    """把 NBS 时间代码（如 ``202403MM``、``202602SS``、``2025YY``）转成日期。

    日期约定与 FRED-MD / FRED-QD 一致：月度取当月 1 日；季度取季末月份的 1 日
    （一季度 → 3 月 1 日）；年度取 1 月 1 日。
    """
    freq = normalize_freq(freq)
    digits = re.sub(r"[^0-9]", "", code)
    year = int(digits[:4])
    if freq == "M":
        return pd.Timestamp(year=year, month=int(digits[4:6]), day=1)
    if freq == "Q":
        q = int(digits[4:6])
        if not 1 <= q <= 4:
            raise NBSError(f"季度代码 {code!r} 中的季度序号不在 1–4 之间")
        return pd.Timestamp(year=year, month=3 * q, day=1)
    return pd.Timestamp(year=year, month=1, day=1)


def date_range_param(freq: str, start: Any = None, end: Any = None) -> str:
    """esData 的 ``dts`` 参数，例如 ``"200001MM-202612MM"``。"""
    freq = normalize_freq(freq)
    suffix = FREQS[freq]["suffix"]
    start, end = _resolve_bounds(freq, start, end)
    return f"{period_code(start, freq)}{suffix}-{period_code(end, freq)}{suffix}"


#: 默认起点：月度 / 季度从 1978 年（国家数据平台上最早的月度、季度数据在此之后），年度从 1949 年。
DEFAULT_START = {"M": "1978-01-01", "Q": "1978-01-01", "A": "1949-01-01"}
#: 每次取数请求覆盖的最长年数。请求跨度过长时服务端很慢，连接可能在中途被断开，所以分段请求。
CHUNK_YEARS = {"M": 10, "Q": 20, "A": 100}


def _resolve_bounds(freq: str, start: Any, end: Any) -> tuple[pd.Timestamp, pd.Timestamp]:
    start = pd.Timestamp(start) if start is not None else pd.Timestamp(DEFAULT_START[freq])
    end = pd.Timestamp(end) if end is not None else pd.Timestamp.today() + pd.DateOffset(years=1)
    return start, end


def date_chunks(freq: str, start: Any = None, end: Any = None) -> list[tuple[pd.Timestamp, pd.Timestamp]]:
    """把取数区间切成若干段（每段不超过 ``CHUNK_YEARS[freq]`` 年）。"""
    freq = normalize_freq(freq)
    start, end = _resolve_bounds(freq, start, end)
    if start > end:
        return []
    out = []
    cur = start
    while cur <= end:
        nxt = min(cur + pd.DateOffset(years=CHUNK_YEARS[freq]) - pd.DateOffset(days=1), end)
        out.append((cur, nxt))
        cur = nxt + pd.DateOffset(days=1)
    return out


# ---------------------------------------------------------------------------
# 数据结构
# ---------------------------------------------------------------------------

@dataclass
class CatalogNode:
    """目录树节点。``path`` 是从频率根节点往下的名称路径（不含根）。"""

    id: str
    name: str
    freq: str
    is_leaf: bool
    parent_id: str
    path: list[str] = field(default_factory=list)
    sdate: str | None = None
    edate: str | None = None
    explain: str | None = None

    @property
    def path_str(self) -> str:
        return " / ".join(self.path)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id, "name": self.name, "freq": self.freq,
            "is_leaf": self.is_leaf, "parent_id": self.parent_id,
            "path": self.path, "sdate": self.sdate, "edate": self.edate,
            "explain": self.explain,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "CatalogNode":
        return cls(**{k: d.get(k) for k in (
            "id", "name", "freq", "is_leaf", "parent_id", "path",
            "sdate", "edate", "explain")})


@dataclass
class Indicator:
    """目录叶子下的一个指标。``key`` 即 ``ek_dp``，是跨分段拼接用的稳定键。"""

    id: str
    key: str
    name: str
    semantic_name: str
    unit: str | None
    catalog_id: str
    note: str | None = None

    @classmethod
    def from_api(cls, d: dict[str, Any]) -> "Indicator":
        key = d.get("ek_dp") or f"{d.get('ek')}_{d.get('dp')}"
        return cls(
            id=d["_id"],
            key=str(key),
            name=(d.get("i_showname") or d.get("_name") or "").strip(),
            semantic_name=(d.get("ek_dp_name") or d.get("ek_name") or "").strip(),
            unit=(d.get("du_name") or None),
            catalog_id=d.get("catalogid") or "",
            note=d.get("i_mark"),
        )

    @property
    def code(self) -> str:
        """去掉哈希后缀的指标编码，如 ``6021702000021-6039802100001_1``。"""
        head, _, tail = self.key.partition("|")
        dp = tail.rpartition("_")[2] if "_" in tail else ""
        return f"{head}_{dp}" if dp else head


# ---------------------------------------------------------------------------
# 客户端
# ---------------------------------------------------------------------------

class NBSClient:
    """国家数据平台客户端。

    Parameters
    ----------
    cache_dir : path, optional
        目录树缓存目录（``catalog_<freq>.json``）。不给时不缓存。
    min_interval : float
        两次请求之间的最小间隔（秒），对服务器保持礼貌。请勿并行运行多个下载进程：请求过密会
        触发网站防火墙的人机验证，此时客户端抛出 :class:`NBSBlockedError` 并停止，不会重试。
    retries : int
        网络错误或 5xx 时的重试次数（指数退避）。
    """

    def __init__(
        self,
        cache_dir: str | Path | None = None,
        *,
        min_interval: float = 1.0,
        retries: int = 5,
        timeout: float = 90.0,
        base_url: str = BASE_URL,
    ) -> None:
        self.cache_dir = Path(cache_dir) if cache_dir else None
        self.min_interval = float(min_interval)
        self.retries = int(retries)
        self.timeout = float(timeout)
        self.base_url = base_url.rstrip("/")
        self._last_request = 0.0
        self._ssl = ssl.create_default_context()
        self._roots: dict[str, str] = {}
        self._indicator_cache: dict[str, list[Indicator]] = {}
        self._children_memo: dict[tuple[str, str], list[CatalogNode]] = {}

    # -- HTTP ---------------------------------------------------------------

    def _request(self, method: str, path: str, *, params: dict | None = None,
                 body: Any = None) -> Any:
        url = f"{self.base_url}/{path.lstrip('/')}"
        if params:
            url += "?" + urllib.parse.urlencode(params)
        data = json.dumps(body, ensure_ascii=False).encode("utf-8") if body is not None else None
        headers = {"User-Agent": USER_AGENT, "Accept": "application/json"}
        if data is not None:
            headers["Content-Type"] = "application/json;charset=UTF-8"

        last_error: Exception | None = None
        for attempt in range(self.retries + 1):
            wait = self.min_interval - (time.monotonic() - self._last_request)
            if wait > 0:
                time.sleep(wait)
            self._last_request = time.monotonic()
            req = urllib.request.Request(url, data=data, headers=headers, method=method)
            try:
                with urllib.request.urlopen(req, timeout=self.timeout, context=self._ssl) as resp:
                    raw = resp.read().decode("utf-8", errors="replace")
                if raw.lstrip()[:1] == "<":
                    # 返回 HTML 而不是 JSON：防火墙的人机验证页。立即停止，不重试。
                    raise NBSBlockedError(f"{BLOCKED_HINT}（{method} {url}）")
                payload = json.loads(raw)
            except urllib.error.HTTPError as exc:
                last_error = exc
                if exc.code in (301, 302, 303, 307):
                    raise NBSBlockedError(f"{BLOCKED_HINT}（HTTP {exc.code}：{method} {url}）") from exc
                if exc.code == 429:
                    # 明确的限流：放慢节奏，等久一点再试一次
                    self.min_interval = max(self.min_interval, 3.0)
                    if attempt < min(self.retries, 1):
                        time.sleep(60)
                        continue
                    raise NBSBlockedError(f"{BLOCKED_HINT}（HTTP 429：{method} {url}）") from exc
                if exc.code < 500:
                    raise NBSError(
                        f"NBS 接口返回 HTTP {exc.code}：{method} {url}。"
                        "如果是 403，可能被网站防火墙拦截：稍后再试，或确认网络能在浏览器里"
                        f"打开 {WEB_URL}。"
                    ) from exc
            except (OSError, http.client.HTTPException, json.JSONDecodeError, UnicodeDecodeError) as exc:
                last_error = exc
            else:
                if isinstance(payload, dict) and payload.get("success") is False:
                    raise NBSError(f"NBS 接口返回失败：{payload.get('message')!r}（{method} {url}）")
                return payload
            if attempt < self.retries:
                time.sleep(min(2 ** attempt * 2.0, 30))
        raise NBSError(f"NBS 请求失败（已重试 {self.retries} 次）：{method} {url}：{last_error}")

    # -- 目录树 -------------------------------------------------------------

    def children(self, parent_id: str, freq: str) -> list[dict[str, Any]]:
        """目录树中 ``parent_id`` 的直接子节点（原始 JSON）。``parent_id=""`` 取根。"""
        freq = normalize_freq(freq)
        out = self._request("GET", "new/queryIndexTreeAsync",
                            params={"pid": parent_id, "code": FREQS[freq]["code"]})
        return list(out.get("data") or [])

    def root_id(self, freq: str) -> str:
        """频率根节点（"月度数据""季度数据""年度数据"）的 id。"""
        freq = normalize_freq(freq)
        if freq not in self._roots:
            roots = self.children("", freq)
            if not roots:
                raise NBSError(f"取不到 {FREQS[freq]['name']} 目录树的根节点")
            self._roots[freq] = roots[0]["_id"]
        return self._roots[freq]

    def child_nodes(self, parent: CatalogNode | None, freq: str) -> list[CatalogNode]:
        """``parent`` 的直接子节点（``None`` 表示频率根节点），带内存缓存。"""
        freq = normalize_freq(freq)
        pid = parent.id if parent is not None else self.root_id(freq)
        path = parent.path if parent is not None else []
        memo_key = (freq, pid)
        if memo_key not in self._children_memo:
            nodes = []
            for k in self.children(pid, freq):
                name = (k.get("_name") or k.get("name") or "").strip()
                nodes.append(CatalogNode(
                    id=k["_id"], name=name, freq=freq,
                    is_leaf=bool(k.get("isLeaf")), parent_id=pid,
                    path=path + [name], sdate=k.get("sdate"), edate=k.get("edate"),
                    explain=k.get("explain"),
                ))
            self._children_memo[memo_key] = nodes
        return self._children_memo[memo_key]

    def _cached_catalog(self, freq: str) -> list[CatalogNode] | None:
        cache = self.cache_dir / f"catalog_{freq}.json" if self.cache_dir else None
        if cache and cache.exists():
            try:
                payload = json.loads(cache.read_text(encoding="utf-8"))
                return [CatalogNode.from_dict(d) for d in payload["nodes"]]
            except (OSError, json.JSONDecodeError, KeyError, TypeError):
                return None
        return None

    def catalog(self, freq: str, *, refresh: bool = False,
                progress: bool = False) -> list[CatalogNode]:
        """完整目录树（扁平列表，含非叶子节点）。有缓存时直接读缓存。

        完整遍历一棵树需要几百次请求（每个非叶子节点一次），首次运行要几分钟。某个子树多次
        重试仍失败时跳过它继续遍历，跳过的节点记在缓存的 ``incomplete`` 字段里，并发出警告；
        这样的缓存下次调用时会自动补全遍历。
        """
        freq = normalize_freq(freq)
        cache = self.cache_dir / f"catalog_{freq}.json" if self.cache_dir else None
        if cache and cache.exists() and not refresh:
            try:
                payload = json.loads(cache.read_text(encoding="utf-8"))
                if not payload.get("incomplete"):
                    return [CatalogNode.from_dict(d) for d in payload["nodes"]]
            except (OSError, json.JSONDecodeError):
                pass

        nodes: list[CatalogNode] = []
        skipped: list[dict[str, Any]] = []
        stack: list[CatalogNode | None] = [None]
        while stack:
            parent = stack.pop()
            try:
                kids = self.child_nodes(parent, freq)
            except NBSBlockedError:
                # 被限制时先把已遍历的部分写进缓存（标记为未完成）：find_catalog 等仍可用这部分缓存，
                # 下次调用 catalog() 会重新遍历补全
                pending = [parent] + stack
                skipped.extend({"id": n.id if n else "", "path": n.path if n else [],
                                "error": "blocked"} for n in pending)
                self._write_catalog_cache(cache, freq, nodes, skipped)
                raise
            except NBSError as exc:
                skipped.append({"id": parent.id if parent else "", "path": parent.path if parent else [],
                                "error": str(exc)})
                continue
            for node in kids:
                nodes.append(node)
                if not node.is_leaf:
                    stack.append(node)
            if progress and len(nodes) % 200 < len(kids):
                print(f"  {FREQS[freq]['name']}目录：已遍历 {len(nodes)} 个节点…", flush=True)

        if skipped:
            warnings.warn(f"{FREQS[freq]['name']}目录有 {len(skipped)} 个子树取不到，已跳过："
                          f"{[' / '.join(s['path']) for s in skipped][:5]}", UserWarning, stacklevel=2)
        self._write_catalog_cache(cache, freq, nodes, skipped)
        return nodes

    def _write_catalog_cache(self, cache: Path | None, freq: str,
                             nodes: list[CatalogNode], skipped: list[dict[str, Any]]) -> None:
        if not cache:
            return
        cache.parent.mkdir(parents=True, exist_ok=True)
        cache.write_text(json.dumps({
            "freq": freq, "root_id": self._roots.get(freq),
            "fetched_at": pd.Timestamp.now(tz="UTC").isoformat(),
            "incomplete": skipped,
            "nodes": [n.to_dict() for n in nodes],
        }, ensure_ascii=False, indent=1), encoding="utf-8")

    def search(self, keyword: str | Sequence[str], freq: str, *,
               leaves_only: bool = True) -> list[CatalogNode]:
        """在目录名称路径中搜索；多个关键词时要求全部出现。需要完整目录树（首次会遍历）。"""
        words = [keyword] if isinstance(keyword, str) else list(keyword)
        words = [w.strip() for w in words if w and w.strip()]
        hits = []
        for n in self.catalog(freq):
            if leaves_only and not n.is_leaf:
                continue
            text = n.path_str
            if all(w in text for w in words):
                hits.append(n)
        return hits

    def find_catalog(self, path: str | Sequence[str], freq: str) -> CatalogNode:
        """按名称路径定位目录节点，例如 ``"价格指数/居民消费价格分类指数 (上年同月=100)"``。

        每一级按"去掉空白后相等"匹配；最后一级也接受分段基础名（不含时段标记）。有完整目录
        缓存时直接查缓存；没有时沿路径逐层请求（只需几次请求，不必遍历整棵树）。
        """
        freq = normalize_freq(freq)
        parts = path.split("/") if isinstance(path, str) else list(path)
        parts = [p.strip() for p in parts if p.strip()]
        norm = lambda s: re.sub(r"\s+", "", s)  # noqa: E731

        def match(name: str, want: str, last: bool) -> bool:
            return norm(name) == norm(want) or (last and norm(segment_base_name(name)) == norm(want))

        cached = self._cached_catalog(freq)
        if cached is not None:
            hits = [n for n in cached
                    if len(n.path) == len(parts)
                    and all(match(a, b, False) for a, b in zip(n.path[:-1], parts[:-1]))
                    and match(n.path[-1], parts[-1], True)]
            if hits:
                return hits[0]

        parent: CatalogNode | None = None
        for i, want in enumerate(parts):
            last = i == len(parts) - 1
            kids = self.child_nodes(parent, freq)
            hit = next((k for k in kids if match(k.name, want, last)), None)
            if hit is None:
                raise NBSError(
                    f"在{FREQS[freq]['name']}目录中找不到 {'/'.join(parts)!r}"
                    f"（第 {i + 1} 级 {want!r} 不存在；该级可选：{[k.name for k in kids][:12]}）")
            parent = hit
        return parent

    def segments(self, node: CatalogNode | str, freq: str) -> list[CatalogNode]:
        """与 ``node`` 同属一个父目录、基础名相同的所有分段叶子（按起始年份排序）。"""
        freq = normalize_freq(freq)
        if isinstance(node, str):
            cached = self._cached_catalog(freq) or []
            found = [n for n in cached if n.id == node]
            if not found:
                return [CatalogNode(id=node, name=node, freq=freq, is_leaf=True, parent_id="")]
            node = found[0]
        base = segment_base_name(node.name)
        cached = self._cached_catalog(freq)
        if cached is not None and any(n.id == node.id for n in cached):
            pool = [n for n in cached if n.parent_id == node.parent_id]
        else:
            parent = CatalogNode(id=node.parent_id, name="", freq=freq, is_leaf=False,
                                 parent_id="", path=node.path[:-1])
            try:
                pool = self.child_nodes(parent, freq) if node.parent_id else [node]
            except NBSBlockedError:
                raise
            except NBSError:
                pool = [node]
        sibs = [n for n in pool if n.is_leaf and segment_base_name(n.name) == base] or [node]

        def order(n: CatalogNode) -> tuple[int, int]:
            s, e = segment_bounds(n.name)
            return (s if s is not None else (-1 if e is not None else 0),
                    e if e is not None else 9999)
        return sorted(sibs, key=order)

    # -- 指标与取数 ----------------------------------------------------------

    def indicators(self, catalog_id: str) -> list[Indicator]:
        """目录叶子下的指标列表。"""
        if catalog_id not in self._indicator_cache:
            out = self._request("GET", "new/queryIndicatorsByCid",
                                params={"cid": catalog_id, "dt": "", "name": ""})
            items = ((out.get("data") or {}).get("list")) or []
            self._indicator_cache[catalog_id] = [Indicator.from_api(d) for d in items]
        return self._indicator_cache[catalog_id]

    def raw_data(self, catalog_id: str, indicator_ids: Sequence[str], freq: str,
                 start: Any = None, end: Any = None,
                 area: dict[str, str] | None = None) -> pd.DataFrame:
        """取一张表里若干指标的数据，返回以日期为索引、指标 id 为列的 DataFrame。

        空字符串（未公布）记为 NaN。区间较长时按 :data:`CHUNK_YEARS` 分段请求再合并。
        """
        freq = normalize_freq(freq)
        rows: dict[pd.Timestamp, dict[str, float]] = {}
        for lo, hi in date_chunks(freq, start, end):
            body = {
                "cid": catalog_id,
                "indicatorIds": list(indicator_ids),
                "daCatalogId": "",
                "das": [area or NATIONAL_AREA],
                "showType": "1",
                "dts": [date_range_param(freq, lo, hi)],
                "rootId": self.root_id(freq),
            }
            out = self._request("POST", "stream/esData", body=body)
            for rec in out.get("data") or []:
                ts = code_to_timestamp(rec["code"], freq)
                row = rows.setdefault(ts, {})
                for v in rec.get("values") or []:
                    row[v["_id"]] = _to_float(v.get("value"))
        df = pd.DataFrame.from_dict(rows, orient="index")
        df = df.reindex(columns=list(indicator_ids))
        df.index = pd.DatetimeIndex(df.index, name="date")
        return df.sort_index()

    def fetch_series(self, catalog: str | CatalogNode, key: str, freq: str, *,
                     start: Any = None, end: Any = None, splice: bool = True,
                     area: dict[str, str] | None = None) -> tuple[pd.Series, dict[str, Any]]:
        """取一个指标的完整序列；``splice=True`` 时自动拼接所有分段表。

        Parameters
        ----------
        catalog : str or CatalogNode
            目录叶子的 id，或名称路径（见 :meth:`find_catalog`）。
        key : str
            指标键：``ek_dp``（推荐，跨分段稳定）、指标编码（``Indicator.code``，
            如 ``6021702000021_1``）、指标 id，或完整显示名。
        """
        freq = normalize_freq(freq)
        if isinstance(catalog, CatalogNode):
            node = catalog
        elif re.fullmatch(r"[0-9a-f]{32}", str(catalog)):
            node = catalog  # id
        else:
            node = self.find_catalog(catalog, freq)
        segs = self.segments(node, freq) if splice else (
            [node] if isinstance(node, CatalogNode)
            else [CatalogNode(id=node, name=node, freq=freq, is_leaf=True, parent_id="")])

        pieces: list[tuple[CatalogNode, Indicator, pd.Series]] = []
        for seg in segs:
            ind = match_indicator(self.indicators(seg.id), key)
            if ind is None:
                continue
            seg_start, seg_end = start, end
            s_year, e_year = segment_bounds(seg.name)
            if s_year is not None:
                lo = pd.Timestamp(year=s_year, month=1, day=1)
                seg_start = lo if start is None else max(pd.Timestamp(start), lo)
            if e_year is not None:
                hi = pd.Timestamp(year=e_year, month=12, day=1)
                seg_end = hi if end is None else min(pd.Timestamp(end), hi)
            df = self.raw_data(seg.id, [ind.id], freq, seg_start, seg_end, area)
            s = df[ind.id].dropna() if ind.id in df else pd.Series(dtype=float)
            pieces.append((seg, ind, s))
        if not pieces:
            raise NBSError(
                f"在目录 {getattr(node, 'path_str', node)!r} 的分段表中都找不到指标 {key!r}。"
                "用 `nbs_tool.py indicators <目录>` 查看可用指标。")

        series, overlaps = splice_segments([p[2] for p in pieces])
        first = pieces[-1][1]
        meta = {
            "key": first.key,
            "code": first.code,
            "name": first.name,
            "semantic_name": first.semantic_name,
            "unit": first.unit,
            "note": first.note,
            "segments": [
                {"catalog_id": seg.id, "catalog": seg.path_str or seg.name,
                 "indicator_id": ind.id, "n_obs": int(s.notna().sum()),
                 "start": str(s.index.min().date()) if len(s) else None,
                 "end": str(s.index.max().date()) if len(s) else None}
                for seg, ind, s in pieces
            ],
            "overlap_conflicts": overlaps,
        }
        series.name = first.code
        return series, meta


def _to_float(v: Any) -> float:
    if v is None:
        return float("nan")
    s = str(v).strip().replace(",", "")
    if s in ("", "-", "--", "—", "…", "...", "null", "None"):
        return float("nan")
    try:
        return float(s)
    except ValueError:
        return float("nan")


def match_indicator(items: Iterable[Indicator], key: str) -> Indicator | None:
    """按 ``ek_dp`` → 指标编码 → 指标 id → 显示名 / 语义名 的顺序匹配指标。"""
    items = list(items)
    key = str(key).strip()
    norm = lambda s: re.sub(r"\s+", "", s or "")  # noqa: E731
    for test in (
        lambda i: i.key == key,
        lambda i: i.code == key,
        lambda i: i.key.partition("|")[0] == key,  # 不带口径的指标编码：只在唯一时用
        lambda i: i.id == key,
        lambda i: norm(i.name) == norm(key),
        lambda i: norm(i.semantic_name) == norm(key),
    ):
        hits = [i for i in items if test(i)]
        if len(hits) == 1:
            return hits[0]
        if len(hits) > 1:
            raise NBSError(f"指标键 {key!r} 匹配到多个指标：{[h.name for h in hits]}；请改用 ek_dp。")
    return None


def splice_segments(pieces: Sequence[pd.Series], *, tol: float = 1e-6
                    ) -> tuple[pd.Series, list[dict[str, Any]]]:
    """按时间顺序拼接分段序列；重叠期取后面（较新）的分段，并记录数值不一致的日期。"""
    pieces = [p.dropna() for p in pieces if p is not None and len(p.dropna())]
    if not pieces:
        return pd.Series(dtype=float), []
    out = pieces[0].copy()
    conflicts: list[dict[str, Any]] = []
    for nxt in pieces[1:]:
        common = out.index.intersection(nxt.index)
        for ts in common:
            a, b = float(out.loc[ts]), float(nxt.loc[ts])
            if abs(a - b) > tol * max(1.0, abs(a), abs(b)):
                conflicts.append({"date": str(ts.date()), "older": a, "newer": b})
        out = pd.concat([out.drop(common), nxt]).sort_index()
    if conflicts:
        warnings.warn(
            f"分段表重叠期有 {len(conflicts)} 个日期数值不一致，已采用较新的分段"
            f"（首个：{conflicts[0]}）。",
            UserWarning, stacklevel=3)
    return out, conflicts
