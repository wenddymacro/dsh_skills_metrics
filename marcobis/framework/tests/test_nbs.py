"""国家统计局数据层的测试：nbs_client、nbs fetcher、lib.preprocess.china、nbs_update 面板定义。

离线测试用一个伪造的服务器响应（``FakeClient``），不联网。联网测试标记为 slow，
需要 ``--runslow`` 才运行。
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
from lib.data import nbs_client as nc  # noqa: E402
from lib.data.fetchers import nbs as nbs_fetcher  # noqa: E402
from lib.preprocess import china  # noqa: E402


# ---------------------------------------------------------------------------
# 伪造的国家数据平台
# ---------------------------------------------------------------------------

ROOT_M = "r" * 32
CAT = "c" * 32
SEG_OLD, SEG_NEW = "a" * 32, "b" * 32
OTHER = "d" * 32


def _ind(iid, key, name, cid):
    return {"_id": iid, "ek_dp": key, "i_showname": name, "ek_dp_name": name,
            "du_name": "%", "catalogid": cid, "i_mark": None}


class FakeClient(nc.NBSClient):
    """按路径返回预先准备好的 JSON；记录收到的请求。"""

    def __init__(self, data_old, data_new):
        super().__init__(cache_dir=None, min_interval=0, retries=0)
        self.calls = []
        self.data = {SEG_OLD: data_old, SEG_NEW: data_new}

    def _request(self, method, path, *, params=None, body=None):
        self.calls.append((method, path, params, body))
        if path.endswith("queryIndexTreeAsync"):
            pid = params["pid"]
            if pid == "":
                return {"data": [{"_id": ROOT_M, "_name": "月度数据", "isLeaf": False}]}
            if pid == ROOT_M:
                return {"data": [{"_id": CAT, "_name": "价格指数", "isLeaf": False}]}
            if pid == CAT:
                return {"data": [
                    {"_id": SEG_NEW, "_name": "测试指数 (2021-)", "isLeaf": True},
                    {"_id": SEG_OLD, "_name": "测试指数 (-2020)", "isLeaf": True},
                    {"_id": OTHER, "_name": "别的表", "isLeaf": True},
                ]}
            return {"data": []}
        if path.endswith("queryIndicatorsByCid"):
            cid = params["cid"]
            # 两个分段里显示名不同、ek_dp 相同；第二个指标只在新分段里有
            if cid == SEG_OLD:
                return {"data": {"list": [_ind("i-old", "6021702000021|h_1", "旧名称", cid)]}}
            return {"data": {"list": [
                _ind("i-new", "6021702000021|h_1", "新名称", cid),
                _ind("i-x", "999|h_1", "只在新表", cid),
            ]}}
        if path.endswith("stream/esData"):
            assert body["dts"] and body["dts"][0].endswith("MM"), body["dts"]
            cid = body["cid"]
            iid = body["indicatorIds"][0]
            rows = []
            for code, val in self.data[cid].items():
                rows.append({"code": code, "values": [{"_id": iid, "value": val}]})
            return {"data": rows}
        raise AssertionError(f"unexpected path {path}")


@pytest.fixture
def fake():
    old = {"202011MM": "101.0", "202012MM": "102.0", "202101MM": "103.0"}
    new = {"202101MM": "103.5", "202102MM": "", "202103MM": "104.0"}
    return FakeClient(old, new)


# ---------------------------------------------------------------------------
# nbs_client
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("code,freq,expected", [
    ("202403MM", "M", "2024-03-01"),
    ("202601SS", "Q", "2026-03-01"),
    ("202604SS", "Q", "2026-12-01"),
    ("2025YY", "A", "2025-01-01"),
])
def test_code_to_timestamp(code, freq, expected):
    assert nc.code_to_timestamp(code, freq) == pd.Timestamp(expected)


def test_date_range_param_formats():
    assert nc.date_range_param("M", "2000-01", "2026-10") == "200001MM-202610MM"
    assert nc.date_range_param("Q", "1992-01", "2026-12") == "199201SS-202604SS"
    assert nc.date_range_param("A", "1978", "2025") == "1978YY-2025YY"


def test_date_chunks_split_long_ranges():
    chunks = nc.date_chunks("M", "1990-01-01", "2026-10-01")
    assert chunks[0][0] == pd.Timestamp("1990-01-01") and chunks[-1][1] == pd.Timestamp("2026-10-01")
    assert len(chunks) == 4
    for (a, b), (c, _) in zip(chunks, chunks[1:]):
        assert c == b + pd.Timedelta(days=1)          # 首尾相接、不重叠
    assert len(nc.date_chunks("A", "1949", "2025")) == 1
    assert nc.date_chunks("Q", "2020-01-01", "2019-01-01") == []


def test_normalize_freq_accepts_chinese():
    assert nc.normalize_freq("月度") == "M"
    assert nc.normalize_freq("quarterly") == "Q"
    assert nc.normalize_freq("年") == "A"
    with pytest.raises(ValueError):
        nc.normalize_freq("weekly")


@pytest.mark.parametrize("name,base,bounds", [
    ("全国居民消费价格分类指数 (上年同月=100) (2016-2020) ", "全国居民消费价格分类指数 (上年同月=100)", (2016, 2020)),
    ("X (-2015)", "X", (None, 2015)),
    ("X (2026-)", "X", (2026, None)),
    ("固定资产投资价格指数（2019-）", "固定资产投资价格指数", (2019, None)),
    ("货币供应量", "货币供应量", (None, None)),
])
def test_segment_names(name, base, bounds):
    assert nc.segment_base_name(name) == base
    assert nc.segment_bounds(name) == bounds


def test_splice_prefers_newer_and_records_conflicts():
    a = pd.Series([1.0, 2.0, 3.0], index=pd.date_range("2020-01-01", periods=3, freq="MS"))
    b = pd.Series([3.5, 4.0], index=pd.date_range("2020-03-01", periods=2, freq="MS"))
    with pytest.warns(UserWarning, match="不一致"):
        out, conflicts = nc.splice_segments([a, b])
    assert list(out.values) == [1.0, 2.0, 3.5, 4.0]
    assert conflicts == [{"date": "2020-03-01", "older": 3.0, "newer": 3.5}]


def test_match_indicator_order_and_ambiguity():
    items = [nc.Indicator.from_api(_ind("1", "AAA|h_1", "甲", "c")),
             nc.Indicator.from_api(_ind("2", "AAA|g_1", "乙", "c"))]
    assert nc.match_indicator(items, "AAA|h_1").id == "1"
    assert nc.match_indicator(items, "乙").id == "2"
    with pytest.raises(nc.NBSError, match="多个指标"):
        nc.match_indicator(items, "AAA_1")  # 编码相同、哈希不同：必须用 ek_dp
    assert nc.match_indicator(items, "nope") is None


def test_find_catalog_walks_path_lazily(fake):
    node = fake.find_catalog("价格指数/测试指数", "M")
    assert node.id in (SEG_OLD, SEG_NEW)
    segs = fake.segments(node, "M")
    assert [s.id for s in segs] == [SEG_OLD, SEG_NEW]
    with pytest.raises(nc.NBSError, match="找不到"):
        fake.find_catalog("价格指数/不存在", "M")


def test_fetch_series_splices_segments_by_ek_dp(fake):
    with pytest.warns(UserWarning):
        s, meta = fake.fetch_series("价格指数/测试指数", "6021702000021_1", "M")
    assert s.index.min() == pd.Timestamp("2020-11-01")
    assert s.loc["2021-01-01"] == 103.5          # 重叠期取新表
    assert "2021-02-01" not in s.dropna().index   # 空字符串是缺失
    assert meta["name"] == "新名称"
    assert len(meta["segments"]) == 2
    assert meta["overlap_conflicts"][0]["date"] == "2021-01-01"


def test_waf_challenge_page_stops_without_retry(monkeypatch):
    calls = []

    class _Resp:
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def read(self):
            return b"<!DOCTYPE HTML><html><script>challenge()</script></html>"

    def fake_urlopen(req, timeout=None, context=None):
        calls.append(req.full_url)
        return _Resp()

    monkeypatch.setattr(nc.urllib.request, "urlopen", fake_urlopen)
    client = nc.NBSClient(cache_dir=None, min_interval=0, retries=5)
    with pytest.raises(nc.NBSBlockedError, match="人机验证"):
        client.children("", "M")
    assert len(calls) == 1, "遇到验证页必须立即停止，不能重试"


def test_fetch_series_unknown_key_raises(fake):
    with pytest.raises(nc.NBSError, match="找不到指标"):
        fake.fetch_series("价格指数/测试指数", "no-such-key", "M")


# ---------------------------------------------------------------------------
# fetcher 与 cache-on-fetch
# ---------------------------------------------------------------------------

def test_parse_spec_string_and_dict():
    s = nbs_fetcher.parse_spec("月度|金融/货币供应量|abc_1")
    assert s == {"freq": "M", "catalog": "金融/货币供应量", "key": "abc_1", "clean": "none"}
    d = nbs_fetcher.parse_spec({"freq": "Q", "catalog": "x", "key": "y", "clean": "cumulative_to_period"})
    assert d["clean"] == "cumulative_to_period"
    with pytest.raises(ValueError):
        nbs_fetcher.parse_spec("M|only-two")
    with pytest.raises(ValueError):
        nbs_fetcher.parse_spec({"freq": "M", "catalog": "x", "key": "y", "clean": "magic"})


def test_fetch_data_with_nbs_writes_cache(tmp_path, fake, monkeypatch):
    project = tmp_path / "proj"
    (project / "data").mkdir(parents=True)
    registry = project / "data" / "registry.yaml"
    registry.write_text("datasets: []\n", encoding="utf-8")
    monkeypatch.setattr(nbs_fetcher.NbsFetcher, "client", property(lambda self: fake))

    with pytest.warns(UserWarning):
        df = lib.fetch_data(api="nbs", series={"idx": "M|价格指数/测试指数|6021702000021_1"},
                            dataset_id="cn_test", registry_path=registry, dropna=False)
    assert "idx" in df.columns
    meta = yaml.safe_load((project / "data" / "cn_test" / "metadata.yaml").read_text(encoding="utf-8"))
    assert meta["variables"][0]["api"] == "nbs"
    local = yaml.safe_load((project / "data" / "registry.local.yaml").read_text(encoding="utf-8"))
    assert local["datasets"][0]["id"] == "cn_test"


# ---------------------------------------------------------------------------
# lib.preprocess.china
# ---------------------------------------------------------------------------

def _monthly(values, start="2020-01-01"):
    return pd.Series(values, index=pd.date_range(start, periods=len(values), freq="MS"), dtype=float)


def test_cumulative_to_period_jan_feb_modes():
    idx = pd.date_range("2020-01-01", "2021-12-01", freq="MS")
    cum = pd.Series(10.0, index=idx).groupby(idx.year).cumsum()
    cum[cum.index.month == 1] = np.nan
    assert np.allclose(china.cumulative_to_period(cum, "M").values, 10.0)
    comb = china.cumulative_to_period(cum, "M", jan_feb="combined")
    assert np.isnan(comb.iloc[0]) and comb.iloc[1] == 20.0
    nan = china.cumulative_to_period(cum, "M", jan_feb="nan")
    assert nan.iloc[:2].isna().all() and nan.iloc[2] == 10.0


def test_cumulative_to_period_series_starting_in_february():
    cum = _monthly([20.0, 30.0, 40.0], start="2020-02-01")
    out = china.cumulative_to_period(cum, "M")
    assert out.loc["2020-01-01"] == 10.0 and out.loc["2020-02-01"] == 10.0
    assert list(out.loc["2020-03-01":].values) == [10.0, 10.0]


def test_cumulative_to_period_does_not_bridge_gaps():
    cum = _monthly([10.0, 20.0, np.nan, 40.0, 50.0])
    out = china.cumulative_to_period(cum, "M")
    assert np.isnan(out.loc["2020-03-01"]) and np.isnan(out.loc["2020-04-01"])
    assert out.loc["2020-05-01"] == 10.0


def test_cumulative_to_period_quarterly():
    idx = pd.date_range("2020-03-01", periods=8, freq="QS-MAR")
    cum = pd.Series(5.0, index=idx).groupby(idx.year).cumsum()
    assert np.allclose(china.cumulative_to_period(cum, "Q").values, 5.0)


def test_fill_january_with_and_without_ytd():
    s = _monthly([np.nan, 6.0, 7.0])
    assert china.fill_january(s).iloc[0] == 6.0
    both_missing = _monthly([5.0, 5.0, 5.0, np.nan, np.nan, 8.0], start="2019-10-01")
    ytd = _monthly([np.nan, 7.5], start="2020-01-01")
    out = china.fill_january(both_missing, ytd=ytd)
    assert out.loc["2020-01-01"] == 7.5 and out.loc["2020-02-01"] == 7.5
    assert out.attrs["filled_january"] == ["2020-01-01", "2020-02-01"]


def test_chain_index_recovers_true_level():
    true = pd.Series(100 * 1.002 ** np.arange(48),
                     index=pd.date_range("2018-01-01", periods=48, freq="MS"))
    mom = true / true.shift(1) * 100
    yoy = true / true.shift(12) * 100
    level = china.chain_index(mom=mom.iloc[24:], yoy=yoy, base=2020)
    ref = true / true[true.index.year == 2020].mean() * 100
    common = level.dropna().index
    assert np.allclose(level.loc[common], ref.loc[common])
    assert level.attrs["chain_check"]["max_abs_diff_pp"] < 1e-8
    assert "同比回推" in level.attrs["chain_method"]


def test_chain_index_backcasts_one_year_before_data_start():
    # 核心 CPI 的情形：环比、同比都从 2021 年开始，基期 2020 只能由同比回推得到
    true = pd.Series(100 * 1.001 ** np.arange(48),
                     index=pd.date_range("2020-01-01", periods=48, freq="MS"))
    mom = (true / true.shift(1) * 100).loc["2021-01-01":]
    yoy = (true / true.shift(12) * 100).loc["2021-01-01":]
    level = china.chain_index(mom=mom, yoy=yoy, base=2020)
    assert level.index.min() == pd.Timestamp("2020-01-01")
    assert level.loc["2020"].mean() == pytest.approx(100.0)


def test_chain_index_mom_start_ignores_early_mom():
    true = pd.Series(100 * 1.002 ** np.arange(48),
                     index=pd.date_range("2018-01-01", periods=48, freq="MS"))
    mom = true / true.shift(1) * 100
    yoy = true / true.shift(12) * 100
    bad = mom.copy()
    bad.loc[:"2019-06-01"] += 2.0                     # 早期环比与同比不一致
    level = china.chain_index(mom=bad, yoy=yoy, mom_start="2019-07-01")
    assert level.attrs["chain_check"]["max_abs_diff_pp"] < 1e-8


def test_chain_index_yoy_only_is_labelled():
    yoy = _monthly(np.full(36, 102.0), start="2018-01-01")
    level = china.chain_index(yoy=yoy)
    assert "仅同比递推" in level.attrs["chain_method"]


def test_index_to_rate_and_splice_ratio():
    assert list(china.index_to_rate(_monthly([102.5, 99.0])).values) == [2.5, -1.0]
    old = _monthly([50.0, 51.0, 52.0, 53.0])
    new = _monthly([104.0, 106.0, 108.0], start="2020-02-01")
    out = china.splice_ratio(old, new, overlap=3)
    # 重叠期（2020-02 至 04）均值之比 106 / 52，旧序列首期 50 衔接为 50 × 106 / 52
    assert out.iloc[0] == pytest.approx(50.0 * 106.0 / 52.0)
    assert out.attrs["splice_ratio"] == pytest.approx(106.0 / 52.0)
    with pytest.raises(ValueError):
        china.splice_ratio(old, _monthly([1.0], start="2030-01-01"))


# ---------------------------------------------------------------------------
# 自带的面板定义
# ---------------------------------------------------------------------------

def _load_update_module():
    spec = importlib.util.spec_from_file_location("nbs_update", ROOT / "scripts" / "tools" / "nbs_update.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


PANELS = sorted(p.parent.name for p in (ROOT / "data").glob("nbs_*/panel.yaml"))


@pytest.mark.parametrize("panel", PANELS)
def test_shipped_panel_definitions_are_valid(panel):
    mod = _load_update_module()
    spec = mod.load_panel(panel)          # 会拒绝被 YAML 读成数字的指标键
    assert spec["id"] == panel
    nc.normalize_freq(spec["freq"])
    ids = {s["id"] for s in spec["series"]}
    for s in spec["series"]:
        assert isinstance(s["key"], str) and s["catalog"].strip() and s.get("label")
        assert s.get("tcode") in (1, 2, 3, 4, 5, 6, 7)
    for d in spec.get("derived", []):
        inputs = [d.get(k) for k in ("mom", "yoy", "source", "nominal", "real_yoy_index",
                                     "numerator", "denominator") if d.get(k)]
        assert inputs and set(inputs) <= ids, (d["id"], inputs)
    reg = yaml.safe_load((ROOT / "data" / "registry.yaml").read_text(encoding="utf-8"))
    assert panel in {e["id"] for e in reg["datasets"]}
    assert (ROOT / "data" / panel / "UPDATE.md").is_file()


def test_partial_update_keeps_full_history_of_other_columns():
    mod = _load_update_module()
    existing = pd.DataFrame({"old": [1.0, 2.0, 3.0, 4.0], "upd": [9.0, 9.0, 9.0, 9.0]},
                            index=pd.date_range("1990-01-01", periods=4, freq="MS"))
    new = {"upd": pd.Series([5.0, 6.0], index=pd.date_range("1990-03-01", periods=2, freq="MS"))}
    df = mod.merge_columns(new, existing)
    assert df.index.min() == pd.Timestamp("1990-01-01")      # 旧列的早期数据不能被截掉
    assert list(df["old"]) == [1.0, 2.0, 3.0, 4.0]
    assert df["upd"].loc["1990-01-01":"1990-02-01"].isna().all()  # 更新的列以新下载为准
    assert list(df["upd"].dropna()) == [5.0, 6.0]


def test_load_panel_rejects_numeric_keys(tmp_path, monkeypatch):
    mod = _load_update_module()
    d = tmp_path / "data" / "nbs_x"
    d.mkdir(parents=True)
    (d / "panel.yaml").write_text(
        "id: nbs_x\nfreq: M\nname: x\nseries:\n  - id: a\n    catalog: x\n    key: 6021702000021_1\n",
        encoding="utf-8")
    monkeypatch.setattr(mod, "ROOT", tmp_path)
    with pytest.raises(SystemExit, match="加引号"):
        mod.load_panel("nbs_x")


# ---------------------------------------------------------------------------
# 联网（--runslow）
# ---------------------------------------------------------------------------

@pytest.mark.slow
def test_live_cpi_yoy_spans_all_segments():
    client = nc.NBSClient(cache_dir=None)
    s, meta = client.fetch_series(
        "价格指数/居民消费价格分类指数 (上年同月=100)/全国居民消费价格分类指数 (上年同月=100)",
        "6021702000021_1", "M", start="2014-01")
    assert len(meta["segments"]) >= 3
    assert s.loc["2015-01-01":"2025-12-01"].notna().all()
    assert 95 < s.median() < 106
