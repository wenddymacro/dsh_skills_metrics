---
name: data-retrieval
description: >
  两种模式的数据管理：(1) 预置数据集（FRED-MD/QD 由用户下载一次；国家统计局月度 / 季度 /
  年度面板由 nbs_update.py 下载清洗），附带完整元数据；(2) 运行时从 API 收集预置数据集里没有的
  序列。主控需要数据、用户要数据，或用户刷新预置数据集时使用。也负责 API 连接、数据质量检查和
  变换流程。调用任何 API 之前总是先查数据集注册表，因为预置数据更快，而且可以离线使用。存储的
  面板保存原始观测值；变换在读取之后再做。
---

# 数据获取

## 两种模式

### 模式 1：预置数据集（首选）

经过核验、带完整元数据、存放在本地的数据集。用户按各数据集的 `UPDATE.md` 刷新它们。agent
在调用任何 API 之前先查这些数据集。

**为什么首选：**没有 API 调用和速率限制，可以离线使用，同样的原始观测值在多次运行中给出同样的
结果。来源推荐的变换编码只存储、不应用；模型读取数据后自行做变换。来源信息记录在注册表和
`df.attrs` 里。

### 模式 2：运行时收集（备选）

需要的序列不在任何预置数据集里时，从 API 获取。也用于一次性分析、探索新变量，或预置数据集
尚未覆盖的经济体。

## 优先顺序

```
1. 预置数据集        （变量在某个已核验的数据集里就用它；中国数据先看 nbs_m / nbs_q / nbs_a）
       ↓ 没有
2. 知识库            （用户所在经济体特有的本地数据源）
       ↓ 没有指定
3. 运行时 API 调用   （FRED、国家统计局 nbs、DBnomics 覆盖的 ECB / IMF / BIS / OECD 等）
       ↓ 没有合适的 API，或请求失败
4. 用户提供的文件    （CSV、Excel 或其他格式）
```

### 第 4 层：用户暂存的数据集（`data/staging/`）

只能从作者存档或需要登录的地方获得的序列（Romer-Romer 冲击、Mertens-Ravn 的 AER 数据、
面板汇编）无法自动获取，属于**用户暂存**：用户把文件放到 `data/staging/<name>.csv`，脚本通过
`csv_file` fetcher 读取。约定：

- **位置和命名：**`data/staging/<描述性名称>.csv`，日期列放第一列；使用它的脚本的 README
  写明确切的格式和来源途径（存档 URL、DOI）。
- **注册表：**暂存文件不登记在 `data/registry.yaml`（它们是用户提供的输入，不是框架分发的
  数据集）；以使用它的脚本为准。
- **缺失时：**脚本（或你）必须干净地停下来，并给出获取说明。绝不替代、插值或编造。这是用户
  暂存，**不是** cache-on-fetch：两种流程截然不同（cache-on-fetch 由 connector 自动落盘；暂存
  需要有访问权限的人手工完成）。

### 推迟的取数（用户拒绝或推迟一次获取）

被拒绝的运行时取数不会在磁盘上留下任何东西，所以不会执行数据获取处置步骤。改为记录*计划*，让
以后的任何会话都能接着做：在分析目录写 `deferred_fetch_plan.yaml`，包括：
`status: deferred_by_user`、建议的获取途径（`lib.fetch_data` 调用及参数）、任何序列 ID 的
**来源**（"模型自身知识；取数前到来源页面核实"）、预先声明的处置组合（缓存目标 + fetcher 层级，
取数时再确认）、本地已有数据的清单，以及 `on_resume` 检查清单。研究日志引用或指向这份计划，
所以丢弃脚手架时不能把计划一起删掉。

---

## 数据集注册表

### 结构

预置面板和数据集注册表（`data/registry.yaml`）放在工作区根目录的 `data/` 下；`lib.fetch_data`
把抓取的缓存登记在已 gitignore 的 `data/registry.local.yaml`。只有 `connections/` 是 skill
本地的配置。

```
skills/data-retrieval/
├── SKILL.md               （本文件）
└── connections/           API 连接说明
    └── connections.yaml   key 变量名、接口地址、速率限制

data/                      （工作区根目录）预置数据集和抓取的数据集
├── registry.yaml          数据集注册表
├── fred_md/               FRED-MD 美国月度宏观面板
│   ├── dataset.csv        数据（不随框架分发；由 UPDATE.md 的步骤生成）
│   ├── transform_codes.csv  每个序列的 FRED 变换编码
│   └── UPDATE.md          一次性下载 + 刷新说明
├── fred_qd/               FRED-QD 美国季度宏观面板
│   ├── dataset.csv
│   ├── transform_codes.csv（+ factor_flags.csv）
│   └── UPDATE.md
├── nbs_m/ nbs_q/ nbs_a/   国家统计局月度 / 季度 / 年度面板
│   ├── panel.yaml         面板定义（序列、目录、指标键、清洗步骤、建议变换）
│   ├── UPDATE.md          说明
│   ├── dataset.csv        清洗后的数据（由 scripts/tools/nbs_update.py 生成）
│   ├── raw.csv            只做了分段拼接的原始数据
│   ├── series_info.csv    列的中文名、单位、清洗步骤、建议变换、样本起止
│   ├── transform_codes.csv  FRED-MD 格式的建议变换编码
│   └── metadata.yaml      版本、每个序列的来源与分段、冲突、定基指数核对
├── nbs_catalog/           国家统计局目录树缓存（自动生成，gitignore）
├── staging/               原始下载和用户暂存的序列（gitignore）
└── <id>/                  用户添加的或 cache-on-fetch 数据集
    ├── dataset.csv
    └── metadata.yaml      （抓取的数据集由 lib.fetch_data 写入）
```

### 注册表格式

格式见 [`data/registry.yaml`](../../data/registry.yaml)。每个条目记录 `id`、`name`、
`description`、`source`、`url`、`frequency`、样本起止（名义值和 `_actual`）、`last_updated`、
`vintage`、`transforms_applied: false`、`path`、`variables_actual`（实际序列数；`variables` 是
名义值）、`missing_pct` 和 `covers`。

### 数据集元数据格式

两个自带的 FRED 面板把逐序列元数据放在 `transform_codes.csv`（FRED-QD 另有
`factor_flags.csv`）里，数据集层面的来源信息在 `data/registry.yaml`，读取时放进 `df.attrs`。
国家统计局面板的逐序列信息在 `series_info.csv` 和 `metadata.yaml`。**cache-on-fetch 数据集**
（由 `lib.fetch_data` 写入）另有一个 `metadata.yaml`，每个抓取的序列一段：

```yaml
# cache-on-fetch 数据集的 metadata.yaml（数值仅为示意）
dataset_id: "uk_macro"
variables:
  - series_id: "indpro"              # 传给 fetch_data 的别名
    source_spec: "economy/economicoutputandproductivity/output/timeseries/k222/diop"
    api: "ons"
    endpoint: "https://www.ons.gov.uk"
    fetched_at: "2026-05-19T14:32:11+00:00"
    sample_start: "1992-10-01"
    sample_end: "2026-04-01"
    n_obs: 403
  # ……（每个抓取的序列一段）
last_updated: "2026-05-19T14:32:11+00:00"
```

单位、季节调整和变换说明不由 fetcher 写入；把数据集提升为预置数据集时手工补上。

### agent 怎样使用预置数据集

specification skill 请求数据时：

1. **查注册表**，找覆盖所需变量和样本的数据集。
2. **如果数据文件不在磁盘上**（注册表引用了它，但 `data/<id>/dataset.csv` 不存在；FRED-MD /
   FRED-QD / 国家统计局面板在新安装时都是这样）：见下面"预置数据缺失时"。**不要悄悄退回到
   运行时收集，也不要拿空数据继续。**
3. **找到了：**直接从 `data/<id>/dataset.csv` 读取，不调用 API。告诉用户："使用预置的 FRED-MD
   数据集（版本 2026-04，已核验）。变量：INDPRO（工业生产，对数差分）、CPIAUCSL（CPI，对数
   差分）、FEDFUNDS（联邦基金利率，水平）。"
4. **只找到一部分：**从数据集读取已有的变量，缺的变量通过运行时 API 获取，并在研究日志中注明
   来源混合。
5. **不在任何已登记的数据集里：**退回到运行时收集（上面的模式 2）。

### 预置数据缺失时

#### 国家统计局面板

`data/nbs_m/`、`data/nbs_q/`、`data/nbs_a/` 只带定义文件 `panel.yaml`，数据要运行脚本下载。
发现缺少数据时，告诉用户需要联网下载哪些面板、大概要几分钟，**征得同意后**在工作区根目录运行：

```bash
python3 scripts/tools/nbs_update.py --panel nbs_m      # 或 nbs_q / nbs_a / all
```

完成后检查输出里的 ✗（失败序列）和 `metadata.yaml` 的 `failed` 字段，再继续分析。详见
[`data/nbs_m/UPDATE.md`](../../data/nbs_m/UPDATE.md)。

#### FRED-MD 和 FRED-QD

FRED-MD 和 FRED-QD 的数据 CSV **不随框架打包**，新的工作区里没有它们。其他经济体的数据集
（某国央行的、ECB 的等）在用户填充时也遵循同样的模式。

如果 agent 发现缺少 FRED-MD 或 FRED-QD 数据文件（注册表引用了它，但磁盘上没有
`data/fred_md/dataset.csv` 或 `data/fred_qd/dataset.csv`）：

**先检查有没有可恢复的本地副本。**同一目录下的 `.bak`、改名的副本或历史版本副本可能让重新下载
变得不必要，但**绝不悄悄恢复备份**：对照注册表做完整性检查（行数 / 列数、日期范围、分析需要的
具体序列），报告结果，并在确认关口提出恢复（恢复会写入 `data/`，属于"先问再做"）。

如果没有可恢复的副本，**停下来，用下面的下载说明提示用户**。下载步骤照原样给出（不要改写 URL
或文件路径）；按块后的说明，只要求分析实际需要的文件。用户确认文件放好之前不要继续。

> **找不到 FRED 数据。**你的 `data/` 目录缺少一个或两个 McCracken（FRED-MD / FRED-QD）面板
> CSV。它们不随框架分发，需要手工下载一次。两个文件来自同一个页面，整个过程约 2 分钟。
>
> **第 1 步：在浏览器中打开 McCracken 页面：**
>
> https://www.stlouisfed.org/research/economists/mccracken/fred-databases
>
> **第 2 步：下载 FRED-MD（月度，约 126 个序列）。**
>
> 在页面上找到 **"FRED-MD: Monthly Data"** 一节，点击 `current.csv`（最新版本）的链接，
> 把文件保存为：
>
> ```
> data/staging/fred_md_current.csv
> ```
>
> （相对于工作区根目录）
>
> **第 3 步：下载 FRED-QD（季度，约 245 个序列）。**
>
> 在同一页面找到 **"FRED-QD: Quarterly Data"** 一节，点击它的 `current.csv` 链接，保存为：
>
> ```
> data/staging/fred_qd_current.csv
> ```
>
> **第 4 步（必需）：运行清洗步骤。**
>
> 原始 `current.csv` 文件顶部有元数据行：
> - FRED-MD：第 1 行是变换编码，第 2 行起是数据。
> - FRED-QD：第 1 行是因子标记，第 2 行是变换编码，第 3 行起是数据。
>
> 原始下载不能直接当作 `dataset.csv` 使用。运行 `data/fred_md/UPDATE.md` 或
> `data/fred_qd/UPDATE.md` 里的清洗步骤（各约 10 行 pandas，在对应目录下运行）。它会去掉元数据
> 行，写出 `dataset.csv` 和对应的元数据文件（`transform_codes.csv`，FRED-QD 另有
> `factor_flags.csv`）。如果误读了原始文件，loader 会报错并指向清洗步骤。
>
> **为什么要手工下载？**圣路易斯联储的文件服务器不接受脚本下载，所以必须在浏览器里下载。
>
> **两个文件都放好后告诉我**，我会继续你的分析。

用户确认放好后，agent 可以重新检查文件路径，继续原来的分析请求。如果分析只需要其中一个文件
（例如纯季度模型不需要 FRED-MD），agent 应只要求所需的文件，不要无谓地两个都要，但总是明确
说明要哪些文件、为什么。

### 更新预置数据集

每个数据集目录都有一个 `UPDATE.md`，写明刷新方法（见
[`data/fred_md/UPDATE.md`](../../data/fred_md/UPDATE.md)；下载步骤需手工完成，见上面"找不到
FRED 数据"）。FRED 面板刷新后，更新 `data/registry.yaml` 里的 `last_updated` 和 `vintage`；
国家统计局面板的版本由 `nbs_update.py` 自动写进 `metadata.yaml`，不改注册表。然后检查：

- [ ] 核心变量没有意外的缺失值
- [ ] 样本终点符合预期
- [ ] 变量个数与注册表的 `variables_actual` 一致（会随版本变化）
- [ ] 变换编码与上一版本相同
- [ ] 抽查 3–5 个数值，与 FRED 网站（或国家数据网站）核对

### 添加新经济体的数据集

对于非美国经济体，用户按同样的结构创建数据集：

1. 创建 `data/[经济体名称]/` 目录。
2. 从当地统计机构或央行收集数据。
3. 写 `metadata.yaml`，记录每个变量（序列 ID、来源、变换、单位、季节调整）。
4. 写 `UPDATE.md`，说明刷新方法。
5. 在 `registry.yaml` 中添加条目。
6. 核验并确认。

agent 可以帮忙起草元数据，但必须由用户核验。中国的国家统计局数据已经有现成的面板和 fetcher，
见下面"国家统计局数据"一节；人民银行的利率、社融等数据不在国家统计局平台上，需要按本节新建
数据集或用 `csv_file` 暂存。

---

## 运行时收集

### 连接配置

各来源的 API 路由（接口地址、API key 变量名、速率限制、备用包、文档链接）在
[`connections/connections.yaml`](connections/connections.yaml)。自定义来源作为新的一段加进去
（文件末尾有注释掉的模板）。

**关于 `connections.yaml` 和已实现的 fetcher。**连接文件记录 agent 可能临时访问的来源的 API
路由（包括 `sdmx`/`fredapi` 这类备用包的用法）；它不是 `lib.fetch_data` 的 fetcher 注册表。
已实现的 fetcher 是下面列出的七个；特别地，`dbnomics` 无需单独的 connections 条目就能覆盖
ECB/OECD/IMF/BIS/Eurostat/World Bank。

### 运行时收集流程

变量不在任何预置数据集里时：

1. 从 connections.yaml（或本地经济体的知识库）中**找最合适的来源**。美国序列用 `fred`；中国
   国家统计局的数据用 `nbs`（无需 key，见下面"国家统计局数据"）；**跨国年度数据**（239 个国家的
   GDP、价格、利率、财政、外贸、危机虚拟变量等长历史序列）先用 Global Macro Database `gmd`
   （无需 key，见下面"Global Macro Database"）；欧元区、OECD、IMF、BIS、
   Eurostat、World Bank 或跨国面板，`dbnomics` 通过一个无需 key 的 API 全部覆盖
   （`api="dbnomics"`，序列 id 为 `PROVIDER/DATASET/SERIES`）。
2. **检查 API key 是否可用。**如果来源需要 key 而没有设置，停下来，带用户完成设置（见下面
   **"设置 FRED API key"**）。（对于 FRED，缺 key 时 `lib.fetch_data(api="fred", …)` 会抛出一个
   清楚、可操作的错误，写明 `FRED_API_KEY` 和具体步骤。）
3. **取数之前先商定数据放在哪里。**`lib.fetch_data` 在取数过程中会写入缓存（`data/<dataset_id>/`）、
   其元数据和一条 `data/registry.local.yaml` 记录。除非本次运行已经商定了存储方式，否则先确认
   （下面"数据获取处置"的决策 A）。只放草稿区的数据，直接调用来源的 fetcher
   （`from lib.data import get_fetcher`；`get_fetcher(api).fetch(series, start, end)`），它返回
   序列但不写 `data/`。
4. 用配置的包**获取序列**。
5. 按用户或字典条目的规定**做变换**。
6. **给出摘要**请用户确认：变量名、来源、样本、单位、变换、缺失观测。
7. **提出**把缓存的序列提升为整理过的预置数据集，供以后使用（决策 A 选项 3）。这是对缓存的后续
   升级，不是第一次的存储决定。

### 设置 FRED API key

单个 FRED 序列（`lib.fetch_data(api="fred", …)`）需要一个免费 key。FRED-MD / FRED-QD 整体面板
**不需要**（它们通过手工下载暂存，见上文）。

1. **申请免费 key**（约 30 秒）：https://fred.stlouisfed.org/docs/api/api_key.html
2. **放进环境变量 `FRED_API_KEY`**，按用户方便选择：
   - **仅当前 shell：**`export FRED_API_KEY=your_key_here`（macOS/Linux）或
     `$env:FRED_API_KEY="your_key_here"`（Windows PowerShell）。
   - **以后的 shell（Windows）：**`setx FRED_API_KEY your_key_here`，然后打开新的 shell。
   - **持久设置：**把 `FRED_API_KEY=your_key_here` 加到项目的 `.env` 文件（如果运行环境会加载）
     或 shell 配置文件（`~/.bashrc` / `~/.zshrc`）。
3. **验证：**`from lib.data import get_fetcher; get_fetcher("fred").fetch({"rgdp": "GDPC1"})`
   （返回序列但不写 `data/`）。缺 key 时 fetcher 会抛出写明变量名和上述步骤的错误；key 无效时
   FRED 返回 HTTP 400（以警告形式显示）。

key 只存在于环境变量中，绝不写进 `config.yaml` 或任何提交的文件。`connections.yaml` 只记录
变量的*名字*（`api_key_env: FRED_API_KEY`），不记录 key 本身。

### Cache-on-fetch：让数据成为不断积累的资产

agent 从运行时 API 取数时，抓到的序列会**持久化到磁盘，并登记为预置数据集**，以后的任何项目
都可以不调用 API 直接复用。这把一次性的抓取变成随时间增长的持久数据资产。

`lib.fetch_data` 自带八个具体 fetcher：`fred`（单个 FRED 序列，需要 `FRED_API_KEY`）、`nbs`
（国家统计局国家数据，无需 key）、`gmd`（Global Macro Database 跨国年度面板，无需 key）、`dbnomics`（ECB / OECD / IMF / BIS / Eurostat / World Bank，
通过一个无需 key 的 API）、`ons`、`boe_iadb`、`csv_file` 和 `external_archive`。见
[`scripts/lib/data/fetcher.py`](../../scripts/lib/data/fetcher.py) 和
[`scripts/lib/data/fetchers/`](../../scripts/lib/data/fetchers/)。

#### 用法

```python
# 项目中第一次：调用 API，存盘，登记
raw = lib.fetch_data(
    api="ons",
    series={"indpro": "economy/economicoutputandproductivity/output/timeseries/k222/diop"},  # ONS：URL 路径字符串
    dataset_id="uk_macro",                  # 缓存目标
    start="1992-10", end="2026-04",
)

# 以后任何项目、任何时候：从磁盘读取，不调用 API
raw = lib.load_dataset(source="uk_macro", series={"indpro": "indpro"})
```

`fetch_data` 封装一个来源专用的 fetcher，把结果写进 `data/<dataset_id>/` 下的数据集目录，
更新逐序列元数据和注册表，并返回读取后的 DataFrame。

#### 每个来源的数据集目录

目录结构见上面"数据集注册表"中的 `data/<id>/`。每个缓存目录**随着新序列的抓取不断增加列**，
在 `dataset.csv` 中按日期合并。一个目录可以由多个来源 API 填充（例如 `uk_macro/` 的列既来自
ONS 也来自 BoE）。它的 `metadata.yaml` 为每个抓取的序列单独记录一段，各有自己的 `api` 和
`source_spec`，格式见上面"数据集元数据格式"。`fetch_data` 不写 `UPDATE.md`；数据集被提升时
手工写一个。

需要 `K222 + IUMABEDR` 的项目 B 可以复用项目 A 抓过的 `K222`（不调用 API），只在 `IUMABEDR`
还没有时才抓取。

#### 缓存刷新

库里没有缓存时效策略。`refresh="cache_first"`（默认）在别名、`api` 和 `source_spec` 都与存储
的来源信息一致时复用缓存序列；`refresh="force"` 重新抓取请求的序列；`refresh="stale_only"`
抛出 `NotImplementedError`。agent 应当：
- 复用之前，告诉用户缓存序列的 `fetched_at`。
- 强制重新抓取会覆盖一个冻结的版本时，先问。
- 在 `metadata.yaml` 中保留 `fetched_at`，保证运行可复现。

#### 注册表自动更新

抓取成功后，数据集目录就成为一个完整登记的来源。从那以后，
`lib.load_dataset(source="uk_macro", ...)` 的用法与 `fred_md` 完全相同：同样的元数据结构，
同样的 `df.attrs` 内容。

## 国家统计局数据

中国宏观数据的主要来源是国家统计局"国家数据"平台（https://data.stats.gov.cn/）。框架提供三层
支持，全部无需 API key：

| 层 | 用法 | 适用场景 |
|---|---|---|
| 预置面板 `nbs_m` / `nbs_q` / `nbs_a` | `lib.load_dataset(source="nbs_m", series=[...])` | 常用宏观指标（首选） |
| fetcher `nbs` | `lib.fetch_data(api="nbs", series={"x": "M\|目录路径\|指标键"}, dataset_id=...)` | 面板里没有的指标，分析脚本中使用 |
| 查询工具 `scripts/tools/nbs_tool.py` | `browse` / `search` / `indicators` / `fetch` | 找目录和指标键、临时查看 |

**序列说明的写法**（`nbs` fetcher）：`"频率|目录路径|指标键"`，例如
`"M|金融/货币供应量|37bea7cb68064788b91d4c1aa46bf97a_1"`（M2 期末值）。也可以写成字典，用
`clean` 指定 `cumulative_to_period` 或 `index_to_rate`。目录路径从"月度数据 / 季度数据 /
年度数据"往下写；分段表（如"…(2016-2020)"）写基础名即可，会自动拼接全部分段。

**NBS 数据与 FRED 的关键差异**，在第 3 阶段的变量对应和变换建议中要主动说明：

1. **分段表。**同一指标按口径或时段拆成多张表，按指标编码（`ek_dp`）拼接。重叠期以较新的表为准，
   数值冲突记录在面板的 `metadata.yaml`。
2. **累计值。**投资、财政、外贸、社零、利润、发电量等以年内累计公布。面板已换算为当月值；1–2 月
   合并公布的年份，默认把合计平均拆到 1、2 月（`jan_feb="split"`）。这是常用但有争议的做法，
   报告中要说明。
3. **价格指数。**只有同比（上年同月=100）和环比（上月=100）。面板里的 `cpi_index`、`ppi_index`、
   `core_cpi_index` 是用环比连乘、同比补齐链接出来的定基指数（2020=100），存在舍入误差，误差
   大小见 `metadata.yaml` 的 `chain_check`。
4. **季节调整。**除 PMI 和季度 GDP 环比外均未季调。春节导致 1、2 月存在移动假日效应。用水平量
   建 VAR 之前，与用户商定季调方法（STL / X-13，或在模型中加季节虚拟变量），或改用同比口径。
5. **口径断点。**规模以上工业起点标准、固定资产投资统计口径（平台上只有累计增速）、CPI
   分类（2016 年）、城镇调查失业率（2018 年起）等。长样本分析要检查断点，必要时用
   `lib.preprocess.china.splice_ratio` 做比例衔接，并记录在研究日志里。
6. **修订。**NBS 会修订历史数据，`nbs_update.py` 每次全量重新下载。研究日志里记下面板
   `metadata.yaml` 中的 `vintage`。

清洗函数都在 `lib.preprocess.china`：`cumulative_to_period`、`fill_january`、`chain_index`、
`index_to_rate`、`splice_ratio`、`regularize`。

## Global Macro Database（跨国年度数据）

https://www.globalmacrodata.com/ ：239 个国家 / 地区、约 80 个年度变量（国民账户、价格、利率、
货币、汇率、财政、外贸、失业、房价、危机虚拟变量），拼接 160 多个来源，部分序列可追溯到数百年前；
每季度发布一个版本（`YYYY_MM`）。**学术用途免费，其他用途需要作者书面许可**，所以不随框架分发，
引用 Müller, Xu, Lehbib & Chen (2025, NBER WP 33714)。详细说明见
[`data/gmd/UPDATE.md`](../../data/gmd/UPDATE.md)。

| 层 | 用法 | 适用场景 |
|---|---|---|
| 下载 / 查询工具 `scripts/tools/gmd_tool.py` | `versions` / `update` / `vars` / `countries` / `coverage` / `extract` / `raw` | 下载版本、查变量和 ISO3、看样本覆盖、查来源拼接 |
| `lib.load_gmd(countries, variables, start, end, version=, forecasts=, wide=)` | 宽表（`rGDP_CHN`，DatetimeIndex 为 1 月 1 日）或长表（`ISO3, year, …`） | 分析脚本中读取（首选） |
| fetcher `gmd` | `lib.fetch_data(api="gmd", series={"gdp_chn": "CHN:rGDP@2026_09"}, dataset_id=...)` | 与其他来源的年度序列合并缓存 |

`lib.load_dataset(source="gmd")` 不可用，会提示改用 `load_gmd`。第一次使用前先**征得同意**再运行
`python3 scripts/tools/gmd_tool.py update`（约 30 MB）。在第 3 阶段要主动说明：

1. **只有年度数据**；月度 / 季度研究不要用它充数。
2. **预测值默认被剔除**（`forecast_<变量>` = 1 的年份置为缺失）。只有用户明确要用 WEO 等预测时才加
   `forecasts=True`，并在研究日志里写明。
3. **单位**：水平量多为百万本币；跨国比较用 `_USD`、`_GDP` 口径或对数增长率。
4. **拼接断点**：长序列来自多个来源按比例衔接。长样本研究先用 `gmd_tool.py coverage` 看缺口，
   用 `gmd_tool.py raw <变量> --country <ISO3>` 查来源切换年份（`source`、`source_change` 列）。
5. **版本**：研究日志记录 `df.attrs["gmd_version"]`；同一研究固定一个版本（`version="2026_09"`）。
6. 适合的模型：跨国面板 VAR（`canova_ciccarelli_2013_panel_var`）、面板局部投影（如危机后果、
   财政乘数的跨国 LP）、长期增长 / 通胀历史分析、单个国家的年度 VAR。

## 数据获取处置

运行时取数产生新数据时（无论是通过 `lib.fetch_data`、手工粘贴用户提供的 CSV、模式 B 中下载论文
附录，还是 `replicate.py` 里的临时 HTTP 请求），**都要和用户一起决定数据和取数代码的去向**。在
第一次写盘之前确定数据放在哪里（决策 A），除非用户已经商定了本次运行的存储方式；取数代码的选择
（决策 B）和之后的提升可以在取数之后进行。这是主控第 7 阶段（处置与归档）在数据层的对应环节：
没有它，数据集会散落在不一致的位置，框架"每个决策都有来源"的承诺也会悄悄打折扣。

**只要新数据第一次落到磁盘上，这一步就是必需的。**绝不让数据放置停留在隐含状态。用户做两个
并行的选择：一个关于数据文件，一个关于取数的代码。

### 决策 A：数据放在哪里

五个选项，与第 7 阶段的结构对应：

1. **草稿 / 一次性。**把文件留在 `outputs/<run_id>/data/` 或临时位置。不登记，不提交，
   gitignore。适用于用户不打算复用的探索性抓取。以后的运行需要同样的数据时会重新抓取。

2. **本地缓存**（`lib.fetch_data` 的默认）。按 cache-on-fetch 约定保存到
   `data/<dataset_id>/dataset.csv`。自动登记在 `data/registry.local.yaml`（一个已 gitignore 的
   附加层，读取时与 `data/registry.yaml` 合并）；以后的 `lib.load_dataset(source=...)` 调用
   立即返回。不纳入版本管理；只存在于这台机器上。大多数运行时取数落在这里。

3. **提升为预置数据集**（FRED-MD / FRED-QD / 国家统计局面板这一层）。放置位置与缓存相同，*另外*：
   写一份完整的 `UPDATE.md` 记录刷新方法，补全 `metadata.yaml` 的来源 / 版本 / 变换说明，以
   明确的"首选"优先级登记；如果使用版本管理，把脚手架（CSV 本身以外的一切）纳入版本管理。适用于
   用户希望保持更新、在多个分析中复用的数据集。

4. **随框架副本保存。**适用于用户希望随自己的框架副本携带的小型公共数据集（经验法则：压缩后
   小于约 5 MB）。谨慎使用：它会让目录膨胀，让许可证追踪更复杂。大多数数据不属于这里；属于这里
   的是经典复现的*脚手架*，数据本身通常不是。

5. **丢弃。**删除文件。适用于没有结果的一次性探索，或与框架已有数据重复的情况。与选项 1 的区别：
   "草稿"表示"以后可能还要，先留在 outputs 里"；"丢弃"表示"用完了，现在就删"。

### 决策 B：取数代码怎么处理

三个选项：

1. **临时保留在 `replicate.py` 中。**取数逻辑写在复现 / 应用脚本里。当取数方法是专属于这篇论文的
   一段代码时（例如下载 Smith-Jones-2024 作者存档的 CSV，解码一个已知的列），这样做是合理的。

2. **记成一条 connector。**按连接配置的方式（见上面"运行时收集"）把方法加进
   `skills/data-retrieval/connections/connections.yaml`。这条记录是给以后会话看的说明（下一个
   agent 在找来源之前会先读它）；它本身不会变成 `lib.fetch_data` 的 fetcher。当用户预计还会再
   访问这个来源时（某个作者存档、某个央行的数据接口），这样做是合理的。

3. **提升为 `scripts/lib/data/fetchers/<source>.py`。**添加一个登记的 fetcher，带完整的输入输出
   约定、重试处理、错误规范化和 `metadata.yaml` 回写。当来源涵盖*一族*数据集时（例如一个提供
   大量序列的新央行 API），值得付出库级实现的成本。添加 fetcher 后，以后所有的复现和应用都能用
   这个来源。

### 决策参考

根据会话信号提出一个具体的（数据，fetcher）组合。常见模式：

| 会话信号 | 建议的（数据，fetcher） |
|---|---|
| 来自论文附录的一次性 CSV | （1 草稿 *或* 5 丢弃，1 临时） |
| 用户说"取一下最新的 BoE 利率，直接用" | （2 缓存，1 临时） |
| 用户开始采用一个新经济体的数据体系（例如为一个新国家建立背景） | （3 预置，2 connector） |
| 第一次调用某个新央行的 API；用户计划用它做更多分析 | （2 缓存，3 lib fetcher） |
| 用户想为可复现性随附一个小型公共数据集 | （4 提交，1 临时 *或* 2 connector） |
| 下载失败或与已有数据重复 | （5 丢弃，1 临时） |
| 用 `nbs` 取面板外的指标，用户之后还会用到 | （2 缓存，或加进 `panel.yaml` 作为 3 预置；fetcher 已在 lib 中） |

提出建议时总是附上理由，例如（Ruritania 是一个虚构的经济体）：

> *"这是我们第一次调用 Ruritania 中央银行的 API，你也说过还会对 Ruritania 做更多分析。我建议：
> **把数据集缓存**到 `data/ruritania_macro/`（选项 2），并**把 fetcher 提升到
> `lib/data/fetchers/`**（选项 3），这样以后的 Ruritania 复现可以直接使用。其他方案：如果只是
> 一次性分析，就临时保留在这个 replicate.py 里；如果你还在评估这家央行是不是合适的来源，就只放
> 草稿区。选哪个？"*

按主控的设计原则 3，绝不在没有方案的情况下问"这些数据你想怎么处理？"。

### 记录

在研究日志中与取数一起记录处置：

```yaml
data_disposition:
  fetched_at: "2026-06-02T14:21:00Z"
  source: "boe_iadb"
  dataset_id: "uk_macro"
  series: ["IUMABEDR", "LPMAUYN"]
  decision_data: "cache"           # scratch | cache | pre_collected | commit | discard
  decision_fetcher: "lib_fetcher"  # ad_hoc | connector | lib_fetcher
  destination_data: "data/uk_macro/"
  destination_fetcher: "scripts/lib/data/fetchers/boe_iadb.py"
  rationale: "会反复使用的英国来源；lib fetcher 让以后的复现更方便"
  prior_runs_using_this: []
```

两个决定都要记录，即使是"草稿" + "临时"。以后的会话需要知道之前的工作把数据层留在了什么状态。

### "先停下来问"清单

主控"先停下来问"规则的自然延伸。如果正要：

- 未确认层级就悄悄把抓取的数据存到 `data/<id>/` → **停，执行处置步骤**
- 未经用户同意就添加新的 connector 或 lib fetcher → **停，问**
- 未经用户确认就丢弃抓取的数据 → **停，问**
- 提交大于 5 MB 的数据文件 → **停，指出仓库膨胀的代价**

### 频率对齐

合并不同频率的变量时：

| 情形 | 方法 | 说明 |
|-----------|--------|-------|
| 月度 → 季度（流量，如 GDP） | 求和或平均 | 确认来源报告的是流量还是存量 |
| 月度 → 季度（存量，如 M1） | 期末值 | 季度最后一个月 |
| 月度 → 季度（比率，如利率） | 平均 | 3 个月的算术平均 |
| 季度 → 月度（分解） | 不推荐 | 有月度来源就用月度来源；否则用 Chow-Lin 插值 |

`lib.preprocess.aggregate` 会对照来源日历检查每个区间是否完整：全部缺失或不完整的区间（缺值、
缺行，或被截断的边界期）返回 NaN，而不是一个看起来完整的总数；"end"/"start" 使用计划中的端点，
而不是悄悄换成更早的观测值。只有明确要部分聚合和"最后一个*可用*端点"语义时，才传
`allow_partial=True`。

国家统计局季度面板的日期是季末月份 1 日（与 FRED-QD 一致），月度面板是当月 1 日。用
`lib.preprocess.aggregate` 把月度聚合到季度后，先把两边都转成 `PeriodIndex('Q')` 再合并。

**派生序列要用构造它的那个指数还原。**还原一个已发布的平减操作时（例如从 FRED 的 M1REAL 重建
名义 M1），要乘以来源平减时用的*同一个*价格指数（M1REAL 用的是 CPIAUCSL）；用其他指数会在结果
中留下相对价格成分。见 `lib.preprocess.nominalise` 的 docstring；在更低的观测频率上，还原是
近似的，应当如实说明。

总是告诉用户所用的对齐方法。

### 版本追踪

为了可复现，记录：

```yaml
data_provenance:
  variable: "INDPRO"
  source: "fred_md pre-collected dataset"   # 或 "FRED API runtime"、"nbs_m pre-collected dataset"
  vintage: "2026-04"
  retrieval_date: "2026-04-11"
  transform_applied: "dlog"
  frequency_original: "monthly"
  frequency_used: "quarterly (averaged)"
  missing_obs_filled: 0
  notes: ""
```

分析中的每个变量都把这些信息写进研究日志。

---

## FRED-MD 速查

FRED-MD 是主要的预置数据集，下面列出 VAR/BVAR 分析中最常用的变量。"变换"一列是 VAR 中常见的
选择，不是 FRED-MD 的官方编码（例如 CPIAUCSL 和 M1SL 的官方编码是 6，UNRATE 和 FEDFUNDS 是 2）；
官方编码在 `data/fred_md/transform_codes.csv`。

### 产出与收入
| 序列 | 名称 | 变换 | 典型用途 |
|--------|------|-----------|-------------|
| INDPRO | 工业生产 | dlog | 月度产出代理 |
| RPI | 实际个人收入 | dlog | 收入指标 |
| CUMFNS | 产能利用率 | level | 产出缺口代理 |

### 劳动力市场
| 序列 | 名称 | 变换 | 典型用途 |
|--------|------|-----------|-------------|
| UNRATE | 失业率 | level | 劳动力市场松紧 |
| PAYEMS | 非农就业 | dlog | 就业 |
| CES0600000008 | 平均时薪（商品生产） | dlog | 工资指标 |
| HOUST | 新屋开工 | log | 先行指标 |

### 价格
| 序列 | 名称 | 变换 | 典型用途 |
|--------|------|-----------|-------------|
| CPIAUCSL | CPI 全部项目 | dlog | 整体通胀 |
| CPIULFSL | CPI 不含食品 | dlog | 近似核心通胀（面板中不含食品的序列） |
| PCEPI | PCE 价格指数 | dlog | 美联储首选的通胀指标 |
| WPSFD49207 | PPI 最终需求：制成品 | dlog | 生产者价格 |
| OILPRICEx | 原油价格（WTI） | dlog | 大宗商品 / 供给冲击代理 |

### 货币与信贷
| 序列 | 名称 | 变换 | 典型用途 |
|--------|------|-----------|-------------|
| M1SL | M1 货币存量 | dlog | 狭义货币 |
| M2SL | M2 货币存量 | dlog | 广义货币 |
| TOTRESNS | 准备金总额 | dlog | 银行准备金 |
| BUSLOANS | 工商业贷款 | dlog | 信贷条件 |

### 利率与利差
| 序列 | 名称 | 变换 | 典型用途 |
|--------|------|-----------|-------------|
| FEDFUNDS | 联邦基金利率 | level | 政策利率 |
| TB3MS | 3 个月国库券 | level | 短期利率 |
| GS10 | 10 年期国债 | level | 长期利率 |
| BAAFFM | Baa 减联邦基金利差 | level | 信用利差 |
| T10YFFM | 期限利差（10 年减联邦基金） | level | 收益率曲线斜率 |

### 汇率
| 序列 | 名称 | 变换 | 典型用途 |
|--------|------|-----------|-------------|
| EXUSUKx | 美元 / 英镑汇率 | dlog | 双边汇率 |
| EXJPUSx | 日元 / 美元汇率 | dlog | 双边汇率 |
| EXCAUSx | 加元 / 美元汇率 | dlog | 双边汇率 |
| TWEXAFEGSMTHx | 贸易加权美元（发达经济体） | dlog | 有效汇率 |

### 把模型字典条目对应到 FRED-MD

经典复现以对应的 `scripts/replications/<id>/config.yaml` 为准，那里写明确切的序列、频率和变换。
其他任何对应关系都视为改编，需要和用户商定。

## 国家统计局月度面板速查（nbs_m）

完整列表和每列的单位、清洗步骤见 `data/nbs_m/series_info.csv`（下载后生成）或 `panel.yaml`。
"建议变换"是 FRED 编码，只供参考；序列未经季调时先处理季节性。

| 列 | 内容 | 建议变换 | 典型用途 |
|---|---|---|---|
| `cpi_index` / `core_cpi_index` / `ppi_index` | CPI / 核心 CPI / PPI 定基指数（2020=100，链接而来） | 5（季调后） | 价格水平 |
| `cpi_inflation` / `ppi_inflation` | CPI / PPI 同比涨幅（%） | 1 | 通胀 |
| `ip_yoy` | 规上工业增加值同比（%，1 月用 1–2 月累计同比填补） | 1 | 月度产出代理 |
| `electricity` | 发电量（当月，亿千瓦时） | 5（季调后） | 月度产出代理 |
| `retail_sales` / `retail_sales_yoy` | 社零当月值 / 同比 | 5 / 1 | 消费 |
| `fai_ytd_yoy` | 固定资产投资累计增速 | 1 | 投资 |
| `re_investment` / `re_sales` | 房地产投资 / 新建商品房销售额（当月） | 5 | 房地产 |
| `exports` / `imports` / `trade_balance` | 进出口（当月，千美元） | 5 / 5 / 1 | 外需 |
| `fiscal_revenue` / `fiscal_expenditure` | 一般公共预算收支（当月；支出 2021 年起才可用，见 `data/nbs_m/UPDATE.md`） | 5 | 财政 |
| `m0` / `m1` / `m2`、`m1_yoy` / `m2_yoy` | 货币供应量期末值 / 同比 | 6 / 1 | 货币 |
| `pmi_mfg` / `pmi_nonmfg` | 制造业 PMI / 非制造业商务活动指数 | 1 | 景气（已季调） |
| `unemployment` | 全国城镇调查失业率（2018 年起） | 2 | 劳动力市场 |

季度面板（`nbs_q`）的核心列：`gdp`（现价当季）、`gdp_real`（不变价当季）、`gdp_yoy_index` /
`real_gdp_growth`（实际同比）、`gdp_qoq_sa`（季调环比）、`gdp_deflator_yoy`（推算的平减指数
同比）、`capacity_util`（工业产能利用率）。

---

## 错误处理

- **缺少 API key：**告诉用户申请免费 key 的网址。
- **API 速率限制：**大多数 fetcher 不重试（`nbs` 客户端自带退避重试）。按递增的间隔等待后重试；
  等待超过 30 秒时告诉用户。
- **序列停更：**指出来，搜索后继序列，建议替代。国家统计局的表常以"(2026-)"这类新分段继续，
  `nbs_client` 会自动拼接；如果目录被改名，用 `nbs_tool.py browse` 找新路径。
- **缺失观测：**报告数量和位置；提供插值选项，但建议不要悄悄插值。`lib.load_dataset` **拒绝**
  悄悄删除请求样本*内部*缺失的观测（那会破坏基于日历的滞后和差分）：选连续的样本，用
  `lib.preprocess.impute` 插补，或传 `dropna=False` 并明确处理缺口。
- **近期数据参差：**新版本的 FRED-MD/QD 各序列更新速度不同，最后几期可能出现内部空洞，触发
  loader 的缺口检查。把读取范围（`end=` / 配置中的 `sample_end`）限定在分析实际使用的样本。
  gertler_karadi 和 stock_watson 两个复现展示了这种做法。国家统计局面板同理：各序列发布时间
  不同，最后一两个月常常不齐。
- **事件型工具变量序列**（某些月份没有可用公告的冲击序列）合理地包含内部 NaN：用
  `lib.fetch_data(..., dropna=False)` 获取并明确处理。标准约定是把没有公告的时期记为零意外，
  这样估计样本保持连续。直接删除这些行会破坏滞后，还会去掉高杠杆观测。
- **版本不符：**如果用户要求特定版本而预置数据集是另一个版本，发出警告，并记录实际使用的版本。
  没有任何 connector 能获取历史版本；用户需要把那个版本作为暂存文件提供。
