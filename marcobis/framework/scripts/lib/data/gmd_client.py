"""Global Macro Database（GMD，https://www.globalmacrodata.com/）客户端。

GMD 由 Müller、Xu、Lehbib、Chen 整理（NBER WP 33714，2025），把 160 多个历史和现行来源
拼接成一张**国家 × 年份**的年度面板：239 个国家 / 地区，1086 年至今，附 IMF WEO 等来源的
预测值（到当前年份后约 5 年）。每季度发布一个版本（``2026_09`` 这样的编号）。

许可：**学术用途免费，其他用途需要作者书面许可**（https://www.globalmacrodata.com/license.html）。
所以数据不随框架分发，由用户运行时下载到本机缓存。

数据文件（与官方 Python 包 ``global_macro_data`` 用的是同一组地址）::

    https://gmd-releases.s3.ap-southeast-2.amazonaws.com/data/
    ├── helpers/versions.csv            # 版本列表
    ├── helpers/varlist.csv             # 变量、单位、定义
    ├── distribute/GMD_<版本>.csv        # 整个面板（约 30 MB，宽表：每个变量一列）
    └── distribute/<变量>_<版本>.csv     # 单个变量的各来源原始值和拼接链（"raw"）

面板的列：``countryname, ISO3, id, year``，变量列（``rGDP``、``CPI``、``infl``……），
``income_group``，以及每个变量的预测标记 ``forecast_<变量>``（1 = 该年的值是预测值）。

本模块只依赖标准库和 pandas。下载的版本文件缓存在 ``<缓存目录>/GMD_<版本>.csv``，同一版本
不会重复下载（发布后的版本文件不会再改）。
"""

from __future__ import annotations

import io
import re
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Iterable, Sequence

import pandas as pd

BASE_URLS = (
    "https://gmd-releases.s3.ap-southeast-2.amazonaws.com/data",
    # GitHub 镜像只有 helpers/*（版本表、变量表），没有版本数据文件
    "https://raw.githubusercontent.com/KMueller-Lab/Global-Macro-Database/refs/heads/main/data",
)
HOMEPAGE = "https://www.globalmacrodata.com/"
LICENSE_URL = "https://www.globalmacrodata.com/license.html"
CITATION = ("Müller, K., Xu, C., Lehbib, M., & Chen, Z. (2025). The Global Macro Database: "
            "A New International Macroeconomic Dataset. NBER Working Paper 33714. "
            "https://doi.org/10.3386/w33714")
USER_AGENT = "marcobis-gmd/1.0 (+https://github.com/wenddymacro/dsh_skills_metrics)"
TIMEOUT = 120
RETRIES = 3

ID_COLS = ("countryname", "ISO3", "id", "year")
NON_VARIABLE_COLS = set(ID_COLS) | {"income_group"}
VERSION_RE = re.compile(r"^\d{4}_\d{2}$")
VAR_RE = re.compile(r"^[A-Za-z][A-Za-z0-9_]*$")


class GMDError(RuntimeError):
    """GMD 下载或查询失败。"""


# ---------------------------------------------------------------------------
# 网络
# ---------------------------------------------------------------------------

def _get(relative: str, bases: Sequence[str] = BASE_URLS, timeout: int = TIMEOUT) -> bytes:
    errors: list[str] = []
    for base in bases:
        url = f"{base}/{relative}"
        for attempt in range(RETRIES):
            try:
                req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
                with urllib.request.urlopen(req, timeout=timeout) as resp:
                    return resp.read()
            except urllib.error.HTTPError as exc:
                errors.append(f"{url}: HTTP {exc.code}")
                if 400 <= exc.code < 500:
                    break  # 文件不存在，换下一个地址
            except (urllib.error.URLError, TimeoutError, OSError) as exc:
                if attempt == RETRIES - 1:
                    errors.append(f"{url}: {exc}")
                else:
                    time.sleep(0.5 * 2 ** attempt)
    raise GMDError(f"无法下载 {relative}：" + "；".join(errors))


def _read_csv_bytes(raw: bytes, **kwargs) -> pd.DataFrame:
    return pd.read_csv(io.BytesIO(raw), **kwargs)


def check_version(version: str) -> str:
    if not VERSION_RE.match(str(version)):
        raise ValueError(f"GMD 版本号格式应为 YYYY_MM（如 2026_09），收到 {version!r}")
    return str(version)


# ---------------------------------------------------------------------------
# 客户端
# ---------------------------------------------------------------------------

class GMDClient:
    """下载、缓存并按国家 / 变量 / 年份切取 GMD 面板。

    Parameters
    ----------
    cache_dir : 路径，可选
        版本文件和辅助表的缓存目录。``None`` 时不写磁盘（每次都下载，只适合测试）。
    fetch : 可调用对象，可选
        ``fetch(relative_path) -> bytes``，测试时用来替换网络访问。
    """

    def __init__(self, cache_dir: str | Path | None = None, fetch=None) -> None:
        self.cache_dir = Path(cache_dir) if cache_dir else None
        self._fetch = fetch or _get
        self._panels: dict[str, pd.DataFrame] = {}
        self._varlist: pd.DataFrame | None = None
        self._versions: list[str] | None = None

    # -- 辅助表 ------------------------------------------------------------

    def _cached_bytes(self, relative: str, name: str, refresh: bool = False) -> bytes:
        path = self.cache_dir / name if self.cache_dir else None
        if path is not None and path.is_file() and not refresh:
            return path.read_bytes()
        raw = self._fetch(relative)
        if path is not None:
            path.parent.mkdir(parents=True, exist_ok=True)
            tmp = path.with_suffix(path.suffix + ".part")
            tmp.write_bytes(raw)
            tmp.replace(path)
        return raw

    def versions(self, refresh: bool = True) -> list[str]:
        """可用版本，新的在前。默认联网刷新（版本表很小）；离线时退回缓存。"""
        if self._versions is not None and not refresh:
            return self._versions
        try:
            raw = self._cached_bytes("helpers/versions.csv", "versions.csv", refresh=refresh)
        except GMDError:
            if self.cache_dir and (self.cache_dir / "versions.csv").is_file():
                raw = (self.cache_dir / "versions.csv").read_bytes()
            else:
                raise
        df = _read_csv_bytes(raw, dtype=str)
        col = "versions" if "versions" in df.columns else df.columns[0]
        vs = [v.strip() for v in df[col].dropna() if VERSION_RE.match(v.strip())]
        if not vs:
            raise GMDError("versions.csv 里没有可识别的版本号")
        self._versions = sorted(set(vs), reverse=True)
        return self._versions

    def latest_version(self) -> str:
        return self.versions()[0]

    def cached_versions(self) -> list[str]:
        if not self.cache_dir or not self.cache_dir.is_dir():
            return []
        out = [m.group(1) for p in self.cache_dir.glob("GMD_*.csv")
               if (m := re.match(r"^GMD_(\d{4}_\d{2})\.csv$", p.name))]
        return sorted(out, reverse=True)

    def resolve_version(self, version: str | None) -> str:
        """``None`` / ``"latest"`` → 最新版本；离线时退回本机已缓存的最新版本。"""
        if version and version != "latest":
            return check_version(version)
        try:
            return self.latest_version()
        except GMDError:
            cached = self.cached_versions()
            if cached:
                return cached[0]
            raise

    def varlist(self, refresh: bool = False) -> pd.DataFrame:
        """变量表：``variable, units, definition``。"""
        if self._varlist is None or refresh:
            raw = self._cached_bytes("helpers/varlist.csv", "varlist.csv", refresh=refresh)
            df = _read_csv_bytes(raw, dtype=str)
            df = df.rename(columns={"variables": "variable"})
            for c in ("variable", "units", "definition"):
                if c not in df.columns:
                    df[c] = ""
            df = df[["variable", "units", "definition"]].fillna("")
            df["definition"] = df["definition"].str.strip()
            self._varlist = df.reset_index(drop=True)
        return self._varlist

    # -- 面板 --------------------------------------------------------------

    def panel_path(self, version: str) -> Path | None:
        return self.cache_dir / f"GMD_{check_version(version)}.csv" if self.cache_dir else None

    def download(self, version: str | None = None, refresh: bool = False) -> str:
        """确保某个版本的面板在缓存里，返回实际版本号。"""
        ver = self.resolve_version(version)
        self._cached_bytes(f"distribute/GMD_{ver}.csv", f"GMD_{ver}.csv", refresh=refresh)
        return ver

    def panel(self, version: str | None = None) -> pd.DataFrame:
        """整张面板（长表：每行一个国家-年份）。"""
        ver = self.resolve_version(version)
        if ver not in self._panels:
            raw = self._cached_bytes(f"distribute/GMD_{ver}.csv", f"GMD_{ver}.csv")
            df = _read_csv_bytes(raw, low_memory=False)
            missing = [c for c in ("ISO3", "year") if c not in df.columns]
            if missing:
                raise GMDError(f"GMD_{ver}.csv 缺少列 {missing}，文件格式可能变了")
            df["year"] = pd.to_numeric(df["year"], errors="coerce").astype("Int64")
            df = df.dropna(subset=["year"])
            df.attrs["gmd_version"] = ver
            self._panels[ver] = df
        return self._panels[ver]

    def variables(self, version: str | None = None) -> list[str]:
        df = self.panel(version)
        return [c for c in df.columns
                if c not in NON_VARIABLE_COLS and not c.startswith("forecast_")]

    def countries(self, version: str | None = None) -> pd.DataFrame:
        """``ISO3, countryname, income_group, first_year, last_year``。"""
        df = self.panel(version)
        cols = [c for c in ("ISO3", "countryname", "income_group") if c in df.columns]
        g = df.groupby("ISO3")["year"].agg(first_year="min", last_year="max")
        meta = df[cols].dropna(subset=["ISO3"]).drop_duplicates("ISO3", keep="last").set_index("ISO3")
        return meta.join(g).reset_index().sort_values("ISO3").reset_index(drop=True)

    def raw_sources(self, variable: str, version: str | None = None) -> pd.DataFrame:
        """单个变量的各来源原始值与拼接链（``distribute/<变量>_<版本>.csv``）。"""
        if not VAR_RE.match(variable):
            raise ValueError(f"变量名不合法：{variable!r}")
        ver = self.resolve_version(version)
        raw = self._cached_bytes(f"distribute/{variable}_{ver}.csv",
                                 f"raw/{variable}_{ver}.csv")
        return _read_csv_bytes(raw, low_memory=False)

    # -- 切取 --------------------------------------------------------------

    def extract(
        self,
        countries: Iterable[str] | str | None = None,
        variables: Iterable[str] | str | None = None,
        start: int | str | None = None,
        end: int | str | None = None,
        *,
        version: str | None = None,
        forecasts: bool = False,
    ) -> pd.DataFrame:
        """按国家、变量、年份切取长表。

        返回列 ``ISO3, countryname, year, <变量…>``；``forecasts=False``（默认）时把预测年份
        的值置为缺失，只留实际值。``forecasts=True`` 时保留预测值，并附带 ``forecast_<变量>``
        标记列。
        """
        df = self.panel(version)
        ver = df.attrs.get("gmd_version")
        all_vars = self.variables(ver)
        vars_ = _as_list(variables) or all_vars
        unknown = [v for v in vars_ if v not in all_vars]
        if unknown:
            raise GMDError(f"GMD {ver} 没有变量 {unknown}；用 gmd_tool.py vars 查看可用变量")
        isos = [c.upper() for c in _as_list(countries)]
        if isos:
            have = set(df["ISO3"].dropna())
            missing = [c for c in isos if c not in have]
            if missing:
                raise GMDError(f"GMD {ver} 没有国家代码 {missing}（用 ISO3，如 CHN、USA）；"
                               "用 gmd_tool.py countries 查看")
            df = df[df["ISO3"].isin(isos)]
        y0, y1 = _year(start), _year(end)
        if y0 is not None:
            df = df[df["year"] >= y0]
        if y1 is not None:
            df = df[df["year"] <= y1]
        flags = [f"forecast_{v}" for v in vars_ if f"forecast_{v}" in df.columns]
        keep = [c for c in ("ISO3", "countryname", "year") if c in df.columns]
        out = df[keep + vars_ + flags].copy()
        for v in vars_:
            out[v] = pd.to_numeric(out[v], errors="coerce")
            f = f"forecast_{v}"
            if f in out.columns:
                out[f] = pd.to_numeric(out[f], errors="coerce").fillna(0).astype(int)
                if not forecasts:
                    out.loc[out[f] == 1, v] = float("nan")
        if not forecasts:
            out = out.drop(columns=flags)
        out = out.sort_values(["ISO3", "year"]).reset_index(drop=True)
        out.attrs["gmd_version"] = ver
        return out

    def wide(
        self,
        countries: Iterable[str] | str,
        variables: Iterable[str] | str,
        start: int | str | None = None,
        end: int | str | None = None,
        *,
        version: str | None = None,
        forecasts: bool = False,
        sep: str = "_",
    ) -> pd.DataFrame:
        """宽表：DatetimeIndex（每年 1 月 1 日），列名 ``<变量><sep><ISO3>``，如 ``rGDP_CHN``。

        日期约定与国家统计局年度面板 ``nbs_a`` 相同，可以直接合并。
        """
        long = self.extract(countries, variables, start, end, version=version, forecasts=forecasts)
        vars_ = [v for v in _as_list(variables)]
        out = long.pivot(index="year", columns="ISO3", values=vars_)
        out.columns = [f"{v}{sep}{iso}" for v, iso in out.columns]
        out.index = pd.to_datetime(out.index.astype(int).astype(str) + "-01-01")
        out.index.name = "date"
        out = out.dropna(how="all")
        out.attrs["gmd_version"] = long.attrs.get("gmd_version")
        return out


# ---------------------------------------------------------------------------
# 工具函数
# ---------------------------------------------------------------------------

def _as_list(x: Iterable[str] | str | None) -> list[str]:
    if x is None:
        return []
    if isinstance(x, str):
        return [t for t in re.split(r"[,\s]+", x) if t]
    return [str(t) for t in x]


def _year(x: int | str | pd.Timestamp | None) -> int | None:
    if x is None or x == "":
        return None
    if isinstance(x, pd.Timestamp):
        return x.year
    m = re.match(r"^\s*(-?\d{1,4})", str(x))
    if not m:
        raise ValueError(f"无法从 {x!r} 解析年份")
    return int(m.group(1))


def default_cache_dir() -> Path | None:
    """缓存放在 ``<项目>/data/gmd/cache/``；找不到注册表时退回 ``~/.cache/marco-gmd``。"""
    try:
        from .registry import load_registry
        return Path(load_registry()["_project_root"]) / "data" / "gmd" / "cache"
    except Exception:  # noqa: BLE001
        return Path.home() / ".cache" / "marco-gmd"


_DEFAULT_CLIENT: GMDClient | None = None


def default_client() -> GMDClient:
    global _DEFAULT_CLIENT
    if _DEFAULT_CLIENT is None:
        _DEFAULT_CLIENT = GMDClient(cache_dir=default_cache_dir())
    return _DEFAULT_CLIENT


def load_gmd(
    countries: Iterable[str] | str,
    variables: Iterable[str] | str,
    start: int | str | None = None,
    end: int | str | None = None,
    *,
    version: str | None = None,
    forecasts: bool = False,
    wide: bool = True,
) -> pd.DataFrame:
    """读取 GMD：``wide=True`` 返回 ``rGDP_CHN`` 式宽表（DatetimeIndex），否则返回长表。

    >>> df = lib.load_gmd(["CHN", "USA"], ["rGDP", "CPI", "strate"], start=1960)
    >>> panel = lib.load_gmd("G7", ...)  # 不支持国家组，请写出 ISO3 列表

    第一次调用会下载整个版本文件（约 30 MB）到 ``data/gmd/cache/``。``df.attrs`` 里记录
    版本号、来源和引用格式，研究日志要写进去。
    """
    client = default_client()
    if wide:
        df = client.wide(countries, variables, start, end, version=version, forecasts=forecasts)
    else:
        df = client.extract(countries, variables, start, end, version=version, forecasts=forecasts)
    df.attrs.update({
        "source": "Global Macro Database",
        "url": HOMEPAGE,
        "citation": CITATION,
        "license": "学术用途免费；其他用途需作者书面许可（" + LICENSE_URL + "）",
        "forecasts_included": forecasts,
    })
    return df
