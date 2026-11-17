"""Global Macro Database 数据层的测试：gmd_client、gmd fetcher、gmd_tool、注册表条目。

离线测试用伪造的发布文件（``FakeFetch``），不联网。联网测试标记为 slow，需要 ``--runslow``。
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
import yaml

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import lib  # noqa: E402
from lib.data import gmd_client as gc  # noqa: E402
from lib.data.fetchers import gmd as gmd_fetcher  # noqa: E402

VERSIONS_CSV = b"versions,version_package\n2025_12,2.0.0\n2026_09,2.0.0\n2026_06,2.0.0\n"
VARLIST_CSV = (b"variables,units,definition\n"
               b"rGDP,millions of LC,Real GDP\n"
               b"infl,in %,Inflation rate\n"
               b"strate,in %,Short-Term Interest Rate.\n")


def _panel_csv() -> bytes:
    rows = []
    for iso, name in (("CHN", "China"), ("USA", "United States")):
        for y in range(2020, 2029):
            fc = int(y >= 2026)
            rows.append({
                "countryname": name, "ISO3": iso, "id": iso, "year": y,
                "rGDP": 100.0 + y - 2020 + (0 if iso == "CHN" else 1000),
                "infl": 2.0 if iso == "USA" else 0.5,
                "strate": np.nan if (iso == "CHN" and y == 2021) else 3.0,
                "income_group": "High income" if iso == "USA" else "Upper middle income",
                "forecast_rGDP": fc, "forecast_infl": fc, "forecast_strate": 0,
            })
    return pd.DataFrame(rows).to_csv(index=False).encode()


class FakeFetch:
    def __init__(self):
        self.calls: list[str] = []
        self.files = {
            "helpers/versions.csv": VERSIONS_CSV,
            "helpers/varlist.csv": VARLIST_CSV,
            "distribute/GMD_2026_09.csv": _panel_csv(),
            "distribute/infl_2026_09.csv": b"ISO3,countryname,year,infl,IMF_WEO,WDI,source\n"
                                            b"CHN,China,2020,0.5,0.5,0.6,IMF_WEO\n",
        }

    def __call__(self, rel: str) -> bytes:
        self.calls.append(rel)
        if rel not in self.files:
            raise gc.GMDError(f"404 {rel}")
        return self.files[rel]


@pytest.fixture
def client(tmp_path):
    fake = FakeFetch()
    return gc.GMDClient(cache_dir=tmp_path / "cache", fetch=fake), fake


# ---------------------------------------------------------------------------
# gmd_client
# ---------------------------------------------------------------------------

def test_versions_sorted_newest_first(client):
    c, _ = client
    assert c.versions() == ["2026_09", "2026_06", "2025_12"]
    assert c.resolve_version(None) == "2026_09"
    assert c.resolve_version("latest") == "2026_09"
    assert c.resolve_version("2026_06") == "2026_06"
    with pytest.raises(ValueError):
        c.resolve_version("2026-09")


def test_panel_is_cached_on_disk(client, tmp_path):
    c, fake = client
    c.download()
    assert (tmp_path / "cache" / "GMD_2026_09.csv").is_file()
    assert c.cached_versions() == ["2026_09"]
    fresh = gc.GMDClient(cache_dir=tmp_path / "cache", fetch=fake)
    n = fake.calls.count("distribute/GMD_2026_09.csv")
    fresh.panel("2026_09")
    assert fake.calls.count("distribute/GMD_2026_09.csv") == n  # 读缓存，不再下载


def test_offline_falls_back_to_cached_version(client, tmp_path):
    c, fake = client
    c.download()

    def offline(rel):
        raise gc.GMDError("offline")

    off = gc.GMDClient(cache_dir=tmp_path / "cache", fetch=offline)
    (tmp_path / "cache" / "versions.csv").unlink()
    assert off.resolve_version(None) == "2026_09"


def test_variables_exclude_ids_and_forecast_flags(client):
    c, _ = client
    assert c.variables() == ["rGDP", "infl", "strate"]


def test_varlist_renames_column(client):
    c, _ = client
    v = c.varlist()
    assert list(v.columns) == ["variable", "units", "definition"]
    assert v.loc[v.variable == "strate", "definition"].item() == "Short-Term Interest Rate."


def test_countries_summary(client):
    c, _ = client
    df = c.countries()
    assert df["ISO3"].tolist() == ["CHN", "USA"]
    row = df.set_index("ISO3").loc["CHN"]
    assert (row.first_year, row.last_year) == (2020, 2028)
    assert row.income_group == "Upper middle income"


def test_extract_masks_forecasts_by_default(client):
    c, _ = client
    df = c.extract("CHN", ["rGDP", "infl"])
    assert "forecast_rGDP" not in df.columns
    assert df.loc[df.year >= 2026, "rGDP"].isna().all()
    assert df.loc[df.year <= 2025, "rGDP"].notna().all()


def test_extract_keeps_forecasts_with_flags(client):
    c, _ = client
    df = c.extract("CHN", ["rGDP"], forecasts=True)
    assert df.loc[df.year == 2027, "rGDP"].item() == 107.0
    assert df.loc[df.year == 2027, "forecast_rGDP"].item() == 1
    assert df.loc[df.year == 2025, "forecast_rGDP"].item() == 0


def test_extract_year_bounds_and_lowercase_iso(client):
    c, _ = client
    df = c.extract(["chn", "usa"], "infl", start="2021", end=2023)
    assert sorted(df.year.unique()) == [2021, 2022, 2023]
    assert set(df.ISO3) == {"CHN", "USA"}


def test_extract_rejects_unknown_country_and_variable(client):
    c, _ = client
    with pytest.raises(gc.GMDError, match="XXX"):
        c.extract("XXX", "rGDP")
    with pytest.raises(gc.GMDError, match="nope"):
        c.extract("CHN", "nope")


def test_wide_layout_matches_nbs_a_dates(client):
    c, _ = client
    w = c.wide(["CHN", "USA"], ["rGDP", "strate"], start=2020)
    assert list(w.columns) == ["rGDP_CHN", "rGDP_USA", "strate_CHN", "strate_USA"]
    assert isinstance(w.index, pd.DatetimeIndex)
    assert w.index[0] == pd.Timestamp("2020-01-01")
    assert w.index[-1] == pd.Timestamp("2028-01-01")  # strate 没有预测标记，保留到 2028
    assert np.isnan(w.loc["2021-01-01", "strate_CHN"])
    assert np.isnan(w.loc["2027-01-01", "rGDP_CHN"])
    assert w.attrs["gmd_version"] == "2026_09"


def test_raw_sources(client):
    c, _ = client
    df = c.raw_sources("infl")
    assert "IMF_WEO" in df.columns
    with pytest.raises(ValueError):
        c.raw_sources("../etc")


def test_get_falls_through_404_to_mirror(monkeypatch):
    seen = []

    class Resp:
        def __init__(self, data):
            self.data = data

        def read(self):
            return self.data

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    def fake_urlopen(req, timeout):
        seen.append(req.full_url)
        if req.full_url.startswith("https://a/"):
            raise gc.urllib.error.HTTPError(req.full_url, 404, "nf", {}, None)
        return Resp(b"ok")

    monkeypatch.setattr(gc.urllib.request, "urlopen", fake_urlopen)
    assert gc._get("x.csv", bases=("https://a", "https://b")) == b"ok"
    assert seen == ["https://a/x.csv", "https://b/x.csv"]  # 404 不重试


# ---------------------------------------------------------------------------
# fetcher
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("spec, expect", [
    ("CHN:rGDP", ("CHN", "rGDP", None, False)),
    ("usa:infl@2026_06", ("USA", "infl", "2026_06", False)),
    ({"country": "jpn", "variable": "CPI", "forecasts": True}, ("JPN", "CPI", None, True)),
])
def test_parse_spec(spec, expect):
    p = gmd_fetcher.parse_spec(spec)
    assert (p["country"], p["variable"], p["version"], p["forecasts"]) == expect


@pytest.mark.parametrize("bad", ["CHNrGDP", ":rGDP", "CHN:rGDP@26_09", 5])
def test_parse_spec_rejects(bad):
    with pytest.raises((ValueError, TypeError)):
        gmd_fetcher.parse_spec(bad)


def test_fetcher_returns_named_series(client):
    c, _ = client
    f = gmd_fetcher.GmdFetcher(client=c)
    out = f.fetch({"g": "CHN:rGDP", "i": {"country": "USA", "variable": "infl", "forecasts": True}})
    assert out["g"].name == "g"
    assert out["g"].index.max() == pd.Timestamp("2025-01-01")
    assert out["i"].index.max() == pd.Timestamp("2028-01-01")
    assert out["g"].attrs["gmd"]["version"] == "2026_09"


def test_fetcher_warns_and_skips_bad_series(client):
    c, _ = client
    f = gmd_fetcher.GmdFetcher(client=c)
    with pytest.warns(UserWarning, match="bad"):
        out = f.fetch({"bad": "XXX:rGDP", "ok": "CHN:infl"})
    assert list(out) == ["ok"]


def test_fetcher_is_registered():
    assert isinstance(lib.data.get_fetcher("gmd"), gmd_fetcher.GmdFetcher)
    assert lib.load_gmd is gc.load_gmd


# ---------------------------------------------------------------------------
# 注册表、loader、工具
# ---------------------------------------------------------------------------

def test_registry_entry():
    reg = yaml.safe_load((ROOT / "data" / "registry.yaml").read_text(encoding="utf-8"))
    entry = next(e for e in reg["datasets"] if e["id"] == "gmd")
    assert entry["loader"] == "load_gmd"
    assert entry["frequency"] == "annual"
    assert (ROOT / entry["path"] / "UPDATE.md").is_file()


def test_load_dataset_points_to_load_gmd():
    with pytest.raises(ValueError, match="load_gmd"):
        lib.load_dataset(source="gmd", series=["rGDP_CHN"])


def _load_tool():
    spec = importlib.util.spec_from_file_location("_gmd_tool", ROOT / "scripts" / "tools" / "gmd_tool.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_tool_update_and_extract(tmp_path, monkeypatch, capsys):
    tool = _load_tool()
    fake = FakeFetch()
    monkeypatch.setattr(tool, "GMD_DIR", tmp_path / "gmd")
    monkeypatch.setattr(tool, "_client",
                        lambda: tool.gc.GMDClient(cache_dir=tmp_path / "gmd" / "cache", fetch=fake))
    assert tool.main(["update"]) == 0
    meta = yaml.safe_load((tmp_path / "gmd" / "metadata.yaml").read_text(encoding="utf-8"))
    assert meta["vintage"] == "2026_09"
    assert meta["variables"] == ["rGDP", "infl", "strate"]
    assert (tmp_path / "gmd" / "countries.csv").is_file()
    out = tmp_path / "x.csv"
    assert tool.main(["extract", "--countries", "CHN", "USA", "--vars", "infl", "--csv", str(out)]) == 0
    df = pd.read_csv(out, index_col=0, parse_dates=True)
    assert list(df.columns) == ["infl_CHN", "infl_USA"]
    assert tool.main(["extract", "--countries", "XXX", "--vars", "infl"]) == 1


# ---------------------------------------------------------------------------
# 联网
# ---------------------------------------------------------------------------

@pytest.mark.slow
def test_live_versions_and_varlist():
    c = gc.GMDClient(cache_dir=None)
    assert gc.VERSION_RE.match(c.latest_version())
    assert "rGDP" in set(c.varlist()["variable"])
