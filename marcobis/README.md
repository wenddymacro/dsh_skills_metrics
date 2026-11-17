# marcobis · DSH 插件

把 BIS 的 **MaRCo@BIS**（宏观计量研究助手）做成 [DeepSeek Harness](https://github.com/deepseek-ai/deepseek-harness)
插件，全部中文化，并新增**国家统计局数据层**和 **Global Macro Database 全球数据层**。

**图文使用指南：[docs/GUIDE.md](docs/GUIDE.md)**（从安装、设计 VAR 到下载数据、估计和读结果，附 DeepSeek Harness 桌面版实测截图）

安装后，会话的 skill 目录里会多出三个 skill：

- **`marco-bis`**：研究工作流的入口。你提出宏观计量问题（"货币政策冲击对中国工业生产和 CPI 有什么影响？"
  "复现 Sims (1980)"），agent 带你走七阶段流程：选模型 → 定设定 → 取数据 → 估计 → 合理性检查 → 报告 → 归档。
  每个关键决策都先给出方案、说明依据，等你确认后再继续。
- **`nbs-data`**：国家统计局月度、季度、年度数据的下载、清洗和取用，也可以单独使用（"帮我下载中国的 CPI 和 M2"）。
- **`gmd-data`**：[Global Macro Database](https://www.globalmacrodata.com/) 全球年度宏观数据（239 个国家 / 地区、约 80 个变量、
  长历史序列）的下载、查询和取用，也可以单独使用（"给我 G7 国家 1960 年以来的实际 GDP 和通胀"）。

上游框架来自 BIS 工作论文 *"MaRCo@BIS: AI-agentic econometric analysis for central bankers"*
（Lombardi、Park、Perez-Cruz，BIS Working Papers No. 1395，2026）随附的开源仓库（Apache-2.0）。

## 功能

- **七阶段人机协同工作流**：模式 A（复现字典中的论文）、B（提交新论文，起草设定后复现）、C（从研究问题出发设计设定）。
  价格之谜、爆炸根、弱工具变量等异常会被主动指出，不会被悄悄接受；所有决策写进研究日志。
- **估计方法**：VAR / BVAR（Minnesota、Sims-Zha、稳态先验、GLP 超参数优化）、局部投影（LP、LP-IV、状态依存、贝叶斯 LP）、
  Cholesky / 符号 / 零+符号 / 叙事 / 长期约束 / proxy SVAR / 异方差 / 非高斯识别、TVP-VAR、面板 VAR、FAVAR、
  动态因子模型、混频 VAR、条件预测、溢出指数、HP / Hamilton / BN 滤波等，由上游的 1,000 多个测试固定。
- **30 篇经典论文的复现**（Sims 1980、CEE 1999、Uhlig 2005、Gertler-Karadi 2015、Primiceri 2005……），每篇都有已核验的设定条目和论文目标值校验。
- **国家统计局数据层**（本插件新增）：
  - 月度面板 `nbs_m`（37 列）：CPI / 核心 CPI / PPI 同比和环比，链接出的定基指数（2020=100），规上工业增加值、
    服务业生产指数、发电量、工业企业利润，社零、固定资产投资、房地产投资与销售，进出口，财政收支，M0/M1/M2，PMI，调查失业率；
  - 季度面板 `nbs_q`（15 列）：现价 / 不变价 GDP 及主要行业增加值、GDP 指数、季调环比、产能利用率、居民收入、投资价格指数；
  - 年度面板 `nbs_a`（42 列）：生产法和支出法 GDP、人口就业工资、价格（含官方定基指数）、财政、外贸、汇率、M1/M2、社会融资规模、外汇储备、投资；
  - 自动清洗：按指标编码拼接分段表（如 CPI 的 -2015 / 2016-2020 / 2021-2025 / 2026- 四张表）、累计值换算为当月 / 当季值、
    1–2 月合并公布的处理、同比 / 环比链接定基指数（附核对误差）；原始值另存 `raw.csv`；
  - `nbs` fetcher 和 `nbs_tool.py`，可以按目录 / 指标抓取平台上任意全国指标。
- **Global Macro Database 全球数据层**（本插件新增）：
  - [GMD](https://www.globalmacrodata.com/)（Müller、Xu、Lehbib、Chen，NBER WP 33714）：239 个国家 / 地区的年度面板，
    国民账户、价格、利率、货币、汇率、财政、外贸、失业、房价、危机虚拟变量，拼接 160 多个来源，部分序列可追溯数百年；
  - `gmd_tool.py`：查看版本、下载、查变量和国家、样本覆盖、切取数据、查看来源拼接；
  - `lib.load_gmd(...)` 返回 `rGDP_CHN` 式宽表（与 `nbs_a` 日期约定一致）或长表（面板模型用），
    `lib.fetch_data(api="gmd", ...)` 可与其他来源一起缓存；预测年份默认剔除，版本可固定；
  - **GMD 学术用途免费，其他用途需要作者书面许可**，数据在本机下载，不随插件分发。
- **中文化**：skill、操作说明、README、数学约定等文档全部译为简体中文；代码、标识符、模型字典条目保留英文。

## 依赖

- DeepSeek Harness ≥ 0.2.1-rc.1
- 本机 Python 3.10 及以上（`python3`；Windows 上为 `python`）
- 估计需要 `numpy<2`、`pandas`、`scipy`、`statsmodels`、`plotly`、`PyYAML`（工作区里的 `requirements.txt`）。
  只下载国家统计局数据时，只需 `numpy`、`pandas`、`PyYAML`
- 网络：能访问 https://data.stats.gov.cn/ （国家统计局数据）、https://gmd-releases.s3.ap-southeast-2.amazonaws.com/ （GMD 数据）；FRED 数据需按说明手工下载

## 安装

**桌面版**：打开「插件 → 添加插件」，填入下面的地址，点击「安装」，再点击「立即启用」。`#` 后面是提交号，下面是目前最新的版本；要装别的版本，换成对应的提交号。

```text
github:wenddymacro/dsh_skills_metrics#068e3125a3efbb3c3d158d7de692336e018041fc&path:/marcobis
```

**命令行**（CLI 管理的 profile）：

```bash
dsh plugin --profile <profile> add "github:wenddymacro/dsh_skills_metrics#068e3125a3efbb3c3d158d7de692336e018041fc&path:/marcobis"
```

从本地 checkout 安装（便于开发）：

```bash
dsh plugin --profile <profile> add "link:/abs/path/to/dsh_skills_metrics/marcobis"
```

每一步的截图见 [使用指南](docs/GUIDE.md)。

如果把已安装的插件换成另一个来源或版本，需要重启 DeepSeek Harness，新代码才会生效。

## 使用

直接用自然语言提问即可，例如：

> 中国的货币政策冲击对工业生产和 CPI 有什么影响？用月度数据，帮我设计一个 BVAR。

> 复现 Sims (1980) 的六变量 VAR。

> 下载国家统计局的月度和季度宏观数据，告诉我 CPI 定基指数是怎么构造的。

第一次使用时，agent 会先征得你同意，在 `~/marco-workspace` 创建**工作区**（也可以指定别的位置，或设置环境变量
`MARCO_WORKSPACE`）。框架代码、数据和你的分析结果都放在工作区里，插件升级不会覆盖它们。之后 agent 会检查
Python 依赖，缺什么会把安装命令给你看，经你同意再安装。

### 工作区管理

```bash
python3 <插件目录>/skills/marco-bis/scripts/marco_workspace.py status    # 位置、版本、数据面板状态
python3 <插件目录>/skills/marco-bis/scripts/marco_workspace.py upgrade   # 插件升级后同步框架文件
python3 <插件目录>/skills/marco-bis/scripts/marco_workspace.py doctor    # 检查 Python 和依赖
```

升级时只覆盖你没改过的文件；你改过的文件保留原样，新版本另存为 `<文件>.new`，由你合并。`scripts/applications/`、
`data/` 下的数据、知识库 `context/` 和各处 `outputs/` 从不触碰。

### 全球数据（Global Macro Database）

在工作区根目录：

```bash
python3 scripts/tools/gmd_tool.py update                                  # 下载最新版本（约 30 MB）
python3 scripts/tools/gmd_tool.py coverage CHN USA JPN --vars rGDP CPI    # 样本覆盖
python3 scripts/tools/gmd_tool.py extract --countries CHN USA --vars rGDP infl --start 1980
```

```python
df = lib.load_gmd(["CHN", "USA", "JPN"], ["rGDP", "infl", "strate"], start=1960)
```

说明见工作区的 `data/gmd/UPDATE.md` 和 `gmd-data` skill。

### 国家统计局数据

在工作区根目录：

```bash
python3 scripts/tools/nbs_update.py --panel all          # 下载并清洗三个面板
python3 scripts/tools/nbs_tool.py browse 月度 "工业"      # 浏览目录
python3 scripts/tools/nbs_tool.py indicators 月度 "金融/货币供应量"
```

清洗规则、样本断点和已知缺口见工作区的 `data/nbs_m/UPDATE.md` 和 `nbs-data` skill。注意：

- 国家统计局网站有防火墙，**请求过密会被暂时限制访问**（返回人机验证页，持续几个小时）。客户端默认每秒最多一个请求，
  遇到验证页立即停止、不重试。请一次只运行一个下载进程。
- 除 PMI 和季度 GDP 环比外，序列都**未经季节调整**；用水平量建模之前要先处理季节性，agent 会在设定阶段提醒。

## 结构

```
marcobis/
├── package.json            # dsh.bundle 声明，不打包任何依赖
├── cordis.patch.yml        # 挂载本包的插件
├── index.js                # 用 dsh 自带的 skill-filesystem provider 挂载 skills/
├── locale/{en,zh}.json     # 插件管理器中显示的标题与描述
├── icon.svg
├── LICENSE, NOTICE         # 上游的 Apache-2.0 许可和 BIS 声明
├── skills/                 # 挂载到 DSH 的 skill（只有这三个）
│   ├── marco-bis/          # 入口：SKILL.md + scripts/marco_workspace.py
│   ├── nbs-data/           # 国家统计局数据
│   └── gmd-data/           # Global Macro Database 全球数据
├── framework/              # 上游框架的中文化版本（工作区模板，不直接挂载）
│   ├── CLAUDE.md, README.md, CONVENTIONS.md, MODIFICATIONS.md, config.yaml, ...
│   ├── skills/             # 12 个子 skill（主控、设定、数据获取、诊断……），由 agent 按路径读取
│   ├── scripts/lib/        # Python 参考库（含新增的 data/nbs_client.py、data/gmd_client.py、preprocess/china.py）
│   ├── scripts/replications/  # 30 个经典复现
│   ├── scripts/tools/      # nbs_update.py、nbs_tool.py、gmd_tool.py 等
│   ├── data/               # 注册表、FRED 与国家统计局面板定义、GMD 说明
│   └── tests/              # 上游测试 + test_nbs.py、test_gmd.py
└── test.mjs                # node --test test.mjs
```

框架里的 12 个子 skill 不挂载到 DSH 的 skill 目录，以免 `specification`、`benchmarking` 这类通用名字和别的插件冲突；
`marco-bis` skill 会引导 agent 按需读取它们。

## 测试

```bash
node --test test.mjs
```

检查 manifest、patch、locale、skill frontmatter、`apply()` 的挂载方式和框架模板的完整性；本机有 Python 3.10+
（带 numpy、pandas、PyYAML）时，还会测试工作区的初始化 / 升级、面板定义和清洗函数。

框架自身的测试在工作区里运行（需要完整依赖和 pytest）：

```bash
python3 -m pytest tests -q                       # 上游快速测试集 + 国家统计局离线测试
python3 -m pytest tests/test_nbs.py --runslow    # 包含联网测试
```

## 与上游的差别

- 全部 skill 和主要文档译为简体中文，"Claude Code"相关表述改为适用于任意 agent 环境；
- 新增国家统计局数据层（客户端、fetcher、清洗函数、三个面板、两个工具脚本、测试）；
- 新增工作区机制（`marco_workspace.py`），适配插件的安装方式；
- 上游的文档一致性测试中，检查"模块数 / 条目数"的正则只匹配英文，对中文文档不再起作用，修改文档数字时请人工核对。

逐文件的修改清单见 [`framework/MODIFICATIONS.md`](framework/MODIFICATIONS.md)。

## 许可与致谢

上游框架 © 2026 Bank for International Settlements，采用 [Apache-2.0](LICENSE) 许可，见 [`NOTICE`](NOTICE)。
本插件的修改与新增部分同样以 Apache-2.0 发布。BIS 的名称和标志未经其书面许可不得使用；本插件提及 BIS 仅为说明来源。
国家统计局数据的使用遵守国家统计局网站的相关规定。引用研究方法时请引用上游的 BIS 工作论文。
