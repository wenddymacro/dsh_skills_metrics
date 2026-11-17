---
name: gmd-data
description: >-
  获取和使用 Global Macro Database（GMD，https://www.globalmacrodata.com/）的全球宏观数据：
  239 个国家 / 地区、约 80 个年度变量（名义 / 实际 GDP、人均 GDP、消费、投资、进出口、经常账户、
  CPI、通胀、平减指数、房价、短期 / 长期 / 政策利率、M0–M4、汇率、实际有效汇率、政府收入 / 支出 /
  赤字 / 债务、人口、失业率、银行 / 主权债务 / 货币危机虚拟变量），拼接 160 多个来源，部分序列
  追溯数百年，含 IMF WEO 等预测值。用户要跨国宏观数据、全球宏观研究、"各国 GDP / 通胀 / 利率 /
  政府债务数据"、长历史年度序列、金融危机跨国样本、跨国面板 VAR / 面板局部投影，或 MaRCo 工作流
  第 3 阶段需要多国年度数据时使用。
---

# Global Macro Database（gmd-data）

数据来自 Global Macro Database（Müller, Xu, Lehbib & Chen 2025, NBER WP 33714），无需注册或
API key。**学术用途免费，其他用途需要作者书面许可**（https://www.globalmacrodata.com/license.html）：
第一次使用时把这一点告诉用户；如果用户的用途明显是商业性的，提醒他们先取得许可。用到 GMD 的成果
要引用上面的论文。

所有代码都在 MaRCo 工作区里，所以先按 `marco-bis` skill 的第 0 步准备好工作区，然后在
**工作区根目录**执行下面的命令（Windows 上把 `python3` 换成 `python`）。

| 位置（相对工作区） | 内容 |
|---|---|
| `data/gmd/UPDATE.md` | 数据说明、读取方法、注意事项 |
| `data/gmd/cache/GMD_<版本>.csv` | 下载的版本面板（`update` 生成） |
| `data/gmd/metadata.yaml`、`varlist.csv`、`countries.csv` | 版本号与下载时间、变量表、国家表（`update` 生成） |
| `scripts/tools/gmd_tool.py` | 版本、下载、变量 / 国家查询、覆盖、切取、来源拼接 |
| `scripts/lib/data/gmd_client.py` | 客户端；`lib.load_gmd(...)` |
| `scripts/lib/data/fetchers/gmd.py` | `lib.fetch_data(api="gmd", ...)` 的 fetcher |

## 步骤

1. **检查本机是否已有数据。** 看 `data/gmd/metadata.yaml` 是否存在、`vintage` 是什么；用
   `python3 scripts/tools/gmd_tool.py versions` 看是否有更新的版本。没有数据，或用户要最新版本时，
   告诉用户要联网下载约 30 MB，**征得同意后**运行：

   ```bash
   python3 scripts/tools/gmd_tool.py update                    # 最新版本
   python3 scripts/tools/gmd_tool.py update --version 2026_06  # 复现时固定旧版本
   ```

2. **找变量和国家代码。**

   ```bash
   python3 scripts/tools/gmd_tool.py vars              # 全部变量、单位、定义
   python3 scripts/tools/gmd_tool.py vars debt         # 搜索
   python3 scripts/tools/gmd_tool.py countries korea   # ISO3 代码、收入组、首末年份
   ```

   常用变量：`rGDP`（实际 GDP，百万本币）、`rGDP_pc`、`rGDP_USD`、`nGDP`、`CPI`（2015 = 100）、
   `infl`（%）、`deflator`、`strate` / `ltrate` / `cbrate`（%）、`M2`、`USDfx`（1 美元兑本币）、
   `REER`、`unemp`、`CA_GDP`、`exports_GDP`、`gen_govdebt_GDP`、`gen_govdef_GDP`、`HPI`、
   `BankingCrisis` / `SovDebtCrisis` / `CurrencyCrisis`（0/1）。

3. **看样本覆盖，再定样本。**

   ```bash
   python3 scripts/tools/gmd_tool.py coverage CHN USA DEU JPN --vars rGDP CPI strate
   ```

   输出每个国家-变量的首末年份、观测数和中间缺口数。缺口多的序列不要直接进 VAR；向用户提议
   截短样本或换变量。

4. **在分析脚本里读取。**

   ```python
   import lib
   df = lib.load_gmd(["CHN", "USA"], ["rGDP", "infl", "strate"], start=1980, version="2026_09")
   # 列名 rGDP_CHN、infl_USA …；DatetimeIndex 为每年 1 月 1 日，可直接和 nbs_a 合并
   panel = lib.load_gmd(["CHN", "USA", "DEU"], ["rGDP", "infl"], start=1960, wide=False)
   # 长表：ISO3, countryname, year, rGDP, infl —— 面板 VAR / 面板 LP 用
   ```

   需要和其他来源一起缓存成一个数据集时，用
   `lib.fetch_data(api="gmd", series={"gdp_chn": "CHN:rGDP@2026_09"}, dataset_id=...)`。
   `lib.load_dataset(source="gmd")` 不可用。

5. **临时查看或导出**（不改动注册数据）：

   ```bash
   python3 scripts/tools/gmd_tool.py extract --countries CHN USA --vars rGDP infl --start 2000
   python3 scripts/tools/gmd_tool.py extract --countries CHN --vars infl --long --forecasts
   python3 scripts/tools/gmd_tool.py extract --countries CHN USA JPN --vars rGDP --csv data/staging/g3.csv
   ```

## 必须主动提醒用户的事项

- **只有年度数据。** 月度 / 季度问题改用 FRED、国家统计局 `nbs_m` / `nbs_q` 或 DBnomics。
  年度 VAR 的样本通常只有几十个观测值，滞后阶数和变量数要相应克制（建议 1–2 阶、≤ 4 个变量，
  或用 BVAR 收缩）。
- **预测值默认剔除。** 当年以后的值是 WEO 等预测（`forecast_<变量>` = 1），默认置为缺失。
  只有用户明确要求时才用 `forecasts=True`，并在研究日志写明。
- **单位和口径。** 水平量多为百万本币，跨国比较用 `_USD` / `_GDP` 口径或对数增长率；
  `govdebt_GDP` 等不带前缀的财政变量是一般政府优先、缺失时用中央政府的合成口径，要说明。
- **拼接断点。** 长序列由多个来源按比例衔接。长样本研究用
  `gmd_tool.py raw <变量> --country <ISO3>` 查看 `source` 列在哪些年份切换，必要时在断点处加
  虚拟变量或截短样本。
- **版本。** 研究日志记录 `df.attrs["gmd_version"]`，同一研究自始至终用同一版本。
- **与国家统计局数据的关系。** 中国的年度序列 GMD 和 `nbs_a` 都有，数值可能因来源和衔接方式
  不同而有差异；中国单国研究优先用 `nbs_a`（官方口径），跨国比较用 GMD 保证口径一致。

## 出错时

- `无法下载 …`：网络问题或 S3 暂时不可用；稍后重试，或用 `--version` 指定本机已有的版本。
  离线时 `lib.load_gmd` 会自动使用本机已下载的最新版本。
- `没有国家代码 …`：用 ISO3（`CHN`、`USA`、`DEU`），用 `countries` 查询；不支持国家组，
  要 G7 等请写出代码列表。
- `没有变量 …`：变量名区分大小写（`rGDP`、`CPI`、`infl`），用 `vars` 查询。
