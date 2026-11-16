---
name: nbs-data
description: >-
  获取和清洗国家统计局（NBS）"国家数据"平台的中国宏观数据：月度、季度、年度三张预置面板
  （CPI / 核心 CPI / PPI 同比、环比与链接出的定基指数，规上工业增加值、服务业生产指数、发电量、
  工业企业利润，社零、固定资产投资、房地产投资与销售，进出口，财政收支，M0/M1/M2，PMI，
  城镇调查失业率，季度现价 / 不变价 GDP 及增加值、GDP 指数、季调环比、产能利用率，年度
  支出法 GDP、人口就业工资等），以及按目录 / 指标抓取任意 NBS 指标。自动拼接按时段拆分的
  分段表，把累计值换算成当月 / 当季值，处理 1–2 月合并公布。用户要中国宏观数据、国家统计局
  数据、"下载 CPI / GDP / M2 / 社零 / 工业增加值数据"、"更新中国数据"、"统计局数据清洗"、
  做中国的 VAR / 宏观实证，或 MaRCo 工作流第 3 阶段需要中国数据时使用。
---

# 国家统计局数据（nbs-data）

数据来自国家统计局"国家数据"平台 https://data.stats.gov.cn/ （2025 年改版后的新平台）。
无需注册或 API key。所有代码都在 MaRCo 工作区里，所以先按 `marco-bis` skill 的第 0 步准备好
工作区，然后在**工作区根目录**执行下面的命令（Windows 上把 `python3` 换成 `python`）。

| 位置（相对工作区） | 内容 |
|---|---|
| `data/nbs_m/`、`data/nbs_q/`、`data/nbs_a/` | 月度 / 季度 / 年度面板：`panel.yaml`（定义）、`UPDATE.md`（说明），下载后生成 `dataset.csv`、`raw.csv`、`series_info.csv`、`transform_codes.csv`、`metadata.yaml` |
| `scripts/tools/nbs_update.py` | 按 `panel.yaml` 下载、清洗、写出面板 |
| `scripts/tools/nbs_tool.py` | 浏览目录、搜索、查看指标键、取单个序列 |
| `scripts/lib/data/nbs_client.py` | 平台客户端（目录、指标、取数、分段拼接） |
| `scripts/lib/data/fetchers/nbs.py` | `lib.fetch_data(api="nbs", ...)` 的 fetcher |
| `scripts/lib/preprocess/china.py` | 清洗函数：`cumulative_to_period`、`fill_january`、`chain_index`、`index_to_rate`、`splice_ratio` |

## 什么时候用哪种方式

1. **预置面板（首选）。** 常用宏观指标都在面板里。检查 `data/nbs_m/dataset.csv` 等文件是否
   存在、`metadata.yaml` 的 `vintage` 是否够新。不存在或过旧时，告诉用户要联网下载（月度面板
   32 个序列加 5 个派生序列，服务器正常时需要几分钟），**征得同意后**运行：

   ```bash
   python3 scripts/tools/nbs_update.py --panel nbs_m      # 或 nbs_q / nbs_a / all
   ```

   脚本逐个打印 ✓ / ✗，最后输出 JSON 汇总。有失败的序列时，把原因告诉用户；常见原因是 NBS
   调整了目录名称，这时用 `nbs_tool.py browse` 找到新路径，改 `panel.yaml` 后用
   `--only <id>` 重跑。

   在分析脚本里读取：

   ```python
   df = lib.load_dataset(source="nbs_m", series=["cpi_index", "ip_yoy", "m2"],
                         start="2010-01", dropna=False)
   ```

   列的中文名、单位、清洗步骤和建议变换（FRED 编码）在 `series_info.csv`。

2. **面板里没有的指标。** 先找到目录和指标键：

   ```bash
   python3 scripts/tools/nbs_tool.py browse 月度                          # 一级目录
   python3 scripts/tools/nbs_tool.py browse 月度 "工业/工业主要产品产量"
   python3 scripts/tools/nbs_tool.py search 月度 粗钢                      # 首次搜索会遍历整棵目录树，约几分钟
   python3 scripts/tools/nbs_tool.py indicators 月度 "工业/工业主要产品产量/粗钢"
   ```

   然后按用途选择：
   - **一次性看看**：`nbs_tool.py fetch 月度 "<目录>" <指标键> [--clean ...] [--csv data/staging/x.csv]`；
   - **分析脚本里用**：`lib.fetch_data(api="nbs", series={"steel": "M|工业/工业主要产品产量/粗钢|<指标键>"}, dataset_id="cn_extra")`，
     数据缓存到 `data/cn_extra/` 并自动登记（首次写入新数据集之前，按 data-retrieval skill 的
     "数据获取处置"先和用户商定存放位置）；
   - **长期使用**：加进对应的 `panel.yaml`，运行 `nbs_update.py --panel nbs_m --only <id>`。

   指标键优先用 `indicators` 列出的编码（如 `6021702000021_1`）。编码在表内不唯一（标 `*`）时，
   改用显示名（如 `利润总额累计值 (亿元)`）。

## 清洗规则（务必向用户说明）

NBS 的原始数据不能直接放进 VAR。面板和工具做了下面这些处理，原始值都保留在 `raw.csv` 里：

| 问题 | 处理 | 函数 |
|---|---|---|
| 同一指标按时段拆成多张表（如 CPI 的"-2015""2016-2020""2021-2025""2026-"） | 按指标键 `ek_dp` 拼接；重叠期取较新的表，数值不一致的日期记在 `metadata.yaml` 的 `overlap_conflicts` | `nbs_client.splice_segments` |
| 流量只公布年内累计值（社零、投资、财政、外贸、利润、发电量等） | 差分成当月 / 当季值；上期累计缺失时本期记缺失，不跨期瞎补 | `china.cumulative_to_period` |
| 1–2 月合并公布（春节） | 累计值：1–2 月合计平均拆到 1、2 月（默认 `split`，可选 `combined` / `nan`）；增长率：1 月用 1–2 月累计同比（2 月值）填补 | `cumulative_to_period(jan_feb=...)`、`china.fill_january` |
| 价格只有同比、环比 | 环比连乘出定基指数，环比缺失的早期用同比回推，基期 2020=100；`metadata.yaml` 的 `chain_check` 给出"定基指数推算的同比"与官方同比的偏差 | `china.chain_index` |
| 指数形式的增长率（上年同期=100） | 减 100 得到百分比 | `china.index_to_rate` |
| 口径断点（基期、统计范围调整） | 不自动处理；需要时用重叠期比例衔接 | `china.splice_ratio` |

**季节调整：**除 PMI 和季度 GDP 环比外，NBS 序列都**未经季节调整**。不要直接对水平量做对数
差分然后放进 VAR。设定阶段要和用户商定以下几种做法之一：

- 改用同比口径；
- 对水平量做季节调整：statsmodels 的 STL 可以直接用；X-13ARIMA-SEATS 需要另装 X-13 程序，
  还要考虑春节的移动假日效应；
- 在模型里加季节虚拟变量。

**样本与断点：**几个需要提醒用户的断点：

- 城镇调查失业率从 2018 年起才有全国月度数据；
- 核心 CPI（不含食品和能源）、服务 CPI 在国家数据平台上只有 2021 年以后的数据，
  `core_cpi_index` 的 2020 年是用 2021 年同比回推的；
- CPI 分类在 2016 年改为"食品烟酒"口径；
- 规模以上工业的起点标准在 2007、2011 年调整过；
- 固定资产投资在平台上只有累计增速，没有水平值。

**源数据本身的缺口**（不做猜测性填补，保留为缺失）：

- 财政收支：1998–2009 年和 2016 年的 12 月累计值未公布，换算出的 12 月当月值缺失；
- 出口、进口：1995–1996 年有零星月份的累计值缺失；
- 工业企业利润：2007–2008 年只有少数月份。

`series_info.csv` 的 `internal_gaps` 列给出样本内部的缺失期数。`lib.load_dataset` 默认
`dropna=True`，遇到内部缺失会报错，以防日历被悄悄打乱。这种情况下用 `dropna=False`，并且
明确处理缺失：选连续的子样本（例如从 2000 年或 2010 年开始），或用 `lib.preprocess.impute`。

## 说明与限制

- 只取**全国**数据。分省数据在平台的"地区数据"里，这里没有覆盖。
- NBS 会修订历史数据，所以每次 `nbs_update.py` 都会全量重新下载。结果依赖下载日期，
  研究日志里要记下 `metadata.yaml` 的 `vintage`。
- **网站防火墙。**平台有防火墙（旧接口 `easyquery.htm` 已返回 403）。请求过密时，防火墙会对
  本机 IP 返回 JavaScript 人机验证页，持续几个小时。客户端识别到验证页（或 HTTP 302 / 429）会
  抛出 `NBSBlockedError` 并**立即停止**，`nbs_update.py` 也会中止，不会写出半成品。
  这时要做的是：
  - 告诉用户原因，建议几个小时后再下载；
  - 不要重试，不要换 User-Agent，不要用浏览器自动化去过验证；
  - 客户端默认两次请求间隔 1 秒，**一次只运行一个下载进程**；
  - 遍历整棵目录树（`search`、`--refresh-catalog`）请求很多，只在确实需要时才做。
- 联网下载和写入 `data/` 都属于"先问再做"。下载前说明要下载哪些面板、大概耗时多久。
- 联网下载和写入 `data/` 都属于"先问再做"。下载前说明要下载哪些面板、大概耗时多久。
