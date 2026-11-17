# MaRCo@BIS：宏观计量研究助手

**一个把 AI agent 变成宏观计量分析研究助手的 skill 框架。**它是 BIS 工作论文
*"MaRCo@BIS: AI-agentic econometric analysis for central bankers"*（Lombardi、Park 和
Perez-Cruz，BIS Working Papers No. 1395，2026）随附发布的公共产品。你在工作区里向 agent 提出研究
问题，agent 带你走一套七阶段工作流，每个重要决策都要你确认：模型选择、变量、滞后、识别、样本、
合理性检查、报告。每个选择都注明依据（你本人、字典条目、知识库或文献），agent 还被要求在异常
（价格之谜、爆炸根、弱工具变量）进入最终结果之前把它们指出来。

> 本工作区来自 DeepSeek Harness 插件 `marcobis`，是上游仓库的中文化版本，并新增了国家统计局
> 数据层。修改清单见 [`MODIFICATIONS.md`](MODIFICATIONS.md)。

框架由三部分组成：[skills](skills/)（工作流和领域知识，纯 Markdown）、一个由 1,000 多个测试覆盖
的 [Python 参考库](scripts/lib/)，以及一部经典论文设定的[字典](skills/model-dictionary/entries/)，
每个条目都配有可运行的复现。

## 快速上手

1. 在 DeepSeek Harness 中安装并启用 `marcobis` 插件（见插件的 README）。
2. 在对话里提出研究问题。agent 会先运行 `marco_workspace.py init` 创建工作区（默认
   `~/marco-workspace`），之后的所有文件都放在这里。
3. 安装 Python 依赖（Python ≥ 3.10，上游在 3.11 上测试；Windows 和 Ubuntu 上测试过，macOS 未经
   上游测试）：`python3 -m pip install -r requirements.txt`。只用 skill 层不需要它，但要*运行*估计
   就需要。可复现的版本锁定在 [requirements-reproduction.txt](requirements-reproduction.txt)。
4. 下载数据：
   - **中国数据：**`python3 scripts/tools/nbs_update.py --panel all`，下载国家统计局月度、季度、
     年度面板（见 `data/nbs_m/UPDATE.md`）。
   - **美国数据：**FRED-MD / FRED-QD 的 CSV 不随框架分发，按 `data/fred_md/UPDATE.md` 和
     `data/fred_qd/UPDATE.md` 手工下载一次，并运行其中的清洗脚本（原始下载需要先去掉元数据行，
     loader 才能读取）。
5. 提问。例如：
   - **模式 A：**"用 FRED 数据复现 Sims (1980) 的六变量 VAR。"
   - **模式 B：**"这是一份 PDF，复现 Smith and Jones (2024) 关于货币政策的研究。"
   - **模式 C：**"货币政策如何影响产出和通胀？""中国的货币政策冲击对工业生产和 CPI 有什么影响？"

agent 会把你的请求分到合适的模式，带你走完每个阶段，边做边生成代码和结果。每个检查点你都可以
确认或推翻；没有任何悄悄做出的决定。

要端到端地验证安装，先 `pip install pytest`（开发依赖，不在 `requirements.txt` 里）；然后
`python -m pytest tests -q` 运行快速测试集（约 2–3 分钟；依赖数据的测试在面板下载之前会干净地
跳过），`python -m pytest tests/test_replications_smoke.py --runslow` 让每个复现对照其论文目标
运行（约 20 分钟）：论文直接报告了可比数字的地方，目标取自论文；否则取作者自己同一复现的结果；见
[`tests/README.md`](tests/README.md)。

## 三种使用方式

框架支持三种入口模式，各有各的工作流：

| 模式 | 何时 | agent 做什么 |
|---|---|---|
| **A：字典执行** | 你点名一篇已在模型字典中的论文 / 方法 | 查找已核验的条目，运行现有的复现，报告结果 |
| **B：论文提交** | 你提供一篇字典里还没有的论文（PDF / URL / 引用） | 解析论文，起草字典条目，请你核对设定，然后执行 |
| **C：研究设计** | 你提出一个开放问题，心里没有具体方法 | 在字典中搜索匹配；没有匹配时，依据模型自身知识和经济理论设计设定，并标明每个决策的来源 |

模式可以在会话中途转换（例如字典条目核验之后，模式 B 转为模式 A），agent 总会明确告知转换。

完整的模式分流规程见 [`skills/orchestrator/SKILL.md`](skills/orchestrator/SKILL.md) 和
[`skills/orchestrator/modes.md`](skills/orchestrator/modes.md)。

## 一次会话的样子

```
你提出问题
  │
  ▼
0a. 知识库：加载保存的经济体背景（没有时提出建立，也可以不用它直接继续）
0b. 分流：模式 A / B / C
  │
  ▼
1. 模型选择 / 条目检索 / 论文解析                ✋ 确认
2. 设定（变量、滞后、先验、识别）                 ✋ 确认
3. 数据收集                                     ✋ 确认变量对应
4. 估计：运行现有脚本或新写一个薄脚本，报告结果（无需确认）
5. 合理性检查：价格之谜？稳定？量级合理？
   失败时：错误修正 / 事先规定的规则自动重跑（最多 5 次）；
   经济性的重新设定                              ✋ 确认（作为带标签的敏感性分析运行）
6. 结果与报告：交互式 HTML 报告（按需提供 PDF 图和 LaTeX 表）
7. 处置与归档                                    ✋ 归档 / 保存 / 提升 / 继续 / 丢弃
```

任何阶段都可以随时修改。分析进行到一半说"加上大宗商品价格"，框架只重跑受影响的阶段，保留未变的
工作，并在研究日志中记录这次修改。

## 会生成什么

| 内容 | 位置 | 保留还是可再生？ |
|---|---|:---:|
| 估计脚本 | `scripts/applications/<id>/`（默认）或 `scripts/replications/<id>/`（仅经典复现） | 保留 |
| 交互式 HTML 报告 | `scripts/<tier>/<id>/outputs/report.html` | 可再生 |
| 数值快照 | `scripts/<tier>/<id>/outputs/numerical_results.json` | 可再生 |
| 运行级研究日志 | `scripts/<tier>/<id>/outputs/research_log.json` | 可再生 |
| 会话记录：agent 的决策、关口、处置和续接状态 | `scripts/<tier>/<id>/outputs/session_research_log.json`（完成时另写 `research_log.md`），同目录的 `run_state.json` | **保留（不可再生）** |
| 数据集 CSV：预置面板（如 FRED-MD/QD、国家统计局面板）、运行时抓取的缓存、用户暂存的序列 | `data/<id>/dataset.csv` | 可再生（重新下载、重新抓取或重新暂存；见各数据集的 `UPDATE.md`） |

要从头开始：删除脚本 `outputs/` 目录中生成的文件并重跑，但先把上面的会话记录
（`session_research_log.json`、`research_log.md`、`run_state.json`）复制出来。它们记录了对话中
做出的决定，重跑脚本无法重建。`outputs/` 不纳入版本管理，所以这些文件也不会被提交，除非你把它们
复制到别处。数值产出由同样的代码、设置、随机种子（脚本自己的 `config.yaml`）和数据文件重新生成。

## 复现

[`scripts/replications/`](scripts/replications/README.md) 是一个公共示例库：**每个字典条目一个
经典复现**，各在自己的目录中，包含 README、配置、可运行脚本和 `paper_targets.yaml` 校验（产出可以
再生：重跑 `replicate.py` 即可重建，通常每个不到一分钟；少数复现需要论文专属的暂存数据，在其目录
的 README 中说明）。示例库自己的 [README](scripts/replications/README.md) 列出了所有示例。

[`skills/model-dictionary/entries/`](skills/model-dictionary/entries/) 中的模型字典收录了全部
已识别的设定。在你自己的副本中，模式 B 会添加新的字典条目，第 7 阶段可以把一个应用提升为经典复现。

## 数据

数据层（`data/<id>/`）与来源无关：无论来源是什么，每个数据集都是一个目录，包含 `dataset.csv`、
逐序列的元数据和一条注册表记录。数据集有三种来源：

- **预置面板：**经过整理，在 `UPDATE.md` 中说明，手工刷新。自带两组：
  - **国家统计局月度、季度、年度面板**（`nbs_m` / `nbs_q` / `nbs_a`）：由
    `scripts/tools/nbs_update.py` 自动下载并清洗（拼接分段表、累计值转当期值、1–2 月合并处理、
    链接定基价格指数），见 [`data/nbs_m/UPDATE.md`](data/nbs_m/UPDATE.md)；
  - 美国标准研究面板 **FRED-MD**（月度）和 **FRED-QD**（季度），1959 年至最新版本（CSV 不随框架
    分发；按各自的 `UPDATE.md` 下载一次）。
- **运行时抓取的缓存：**可插拔 fetcher（[`scripts/lib/data/fetchers/`](scripts/lib/data/fetchers/)）
  能取到的任何序列：`fred`（单个 FRED 序列；需要免费的 `FRED_API_KEY`；两分钟设置方法见
  `skills/data-retrieval/SKILL.md`）、`nbs`（国家统计局任意指标，无需 key）、`dbnomics`（通过
  一个无需 key 的 API 访问 ECB / OECD / IMF / BIS / Eurostat / World Bank）、`ons`、`boe_iadb`、
  `csv_file`、`external_archive`。抓取一次，本地缓存，自动登记。
- **用户暂存的序列：**没有稳定公开 URL 的数据（作者存档、内部序列），按需要它们的复现 README 中的
  约定放进 `data/staging/`。

预置的 CSV 完全不需要 API key。新的经济体通过同样三种途径添加自己的数据集；数据层中没有任何东西
专属于 FRED 或美国数据。

数据许可：框架不随附转发任何成批数据。connector 和复现脚本从第三方来源取数并保留本地副本，各来源
的使用条款对你适用，包括对存储、转发数据或将数据用于 AI 系统的任何限制。本产品使用 FRED® API，
但未经圣路易斯联邦储备银行认可或认证。用本框架获取 FRED 数据，即表示你同意
[FRED® API Terms of Use](https://fred.stlouisfed.org/docs/api/terms_of_use.html) 和
[FRED® Services Terms of Use](https://fred.stlouisfed.org/legal/)。国家统计局数据的使用遵守国家
统计局网站的相关规定；请合理控制下载频率。

## skill 清单

[`skills/`](skills/) 下的 skill 覆盖工作流和知识。估计方法单独放在
[`scripts/lib/`](scripts/lib/)；见下面"估计方法"。

| 阶段 | skill | 说明 |
|-------|-------|-------------|
| 0 | [knowledge-base](skills/knowledge-base/SKILL.md) | 经济体概况、惯例、先验信念；受理时加载，全程参考 |
| 0 | *（主控）* | 受理并分流到模式 A / B / C |
| 1 | [model-selection](skills/model-selection/SKILL.md) | 研究问题 → 方法 |
| 1 | [model-dictionary](skills/model-dictionary/SKILL.md) | 论文设定：查找、来源和条目整理 |
| 2 | [specification](skills/specification/SKILL.md) | 变量、滞后、先验、识别、样本 |
| 3 | [data-retrieval](skills/data-retrieval/SKILL.md) | FRED-MD/QD、国家统计局面板 + 运行时 API 抓取 |
| 4 | *（交给 `scripts/lib/`）* | 估计方法在库里，不是按方法划分的 skill |
| 4 | [diagnostics](skills/diagnostics/SKILL.md) | 残差检验和模型充分性检查（统计关口） |
| 5 | *（主控）* | 经济合理性检查（符号、量级、稳定性）；使用第 4 阶段的诊断结果 |
| 6 | [results-presentation](skills/results-presentation/SKILL.md) | 图、表和 HTML 报告 |
| 7 | *（主控）* | 处置与归档：归档、保存为应用、提升、继续、丢弃 |
| — | [orchestrator](skills/orchestrator/SKILL.md) | 协调所有阶段的主循环 |
| — | [benchmarking](skills/benchmarking/SKILL.md) | 按需与基准、竞争模型和已发表结果比较；不是阶段关口 |
| — | [consistency-audit](skills/consistency-audit/SKILL.md) | 按需审计 skills、lib 和字典之间的漂移 |
| — | [advisor-protocol](skills/advisor-protocol/SKILL.md) | 可选：请另一个模型审阅困难的推导；默认关闭 |
| — | [research-log](skills/research-log/SKILL.md) | 会话决策、版本、处置和续接状态 |

## 估计方法

估计在 [`scripts/lib/`](scripts/lib/README.md) 中完成，这个 Python 库涵盖：

- **VAR / BVAR：**经典 VAR、Minnesota / Sims-Zha 先验、虚拟观测、GLP 超参数优化、稳态 / 均值
  调整先验（Villani 2009）、小型开放经济的区块外生性、多工具变量 proxy SVAR
- **局部投影：**线性 LP、LP-IV、状态依存 LP（Auerbach-Gorodnichenko 2012 / Ramey-Zubairy 2018）、
  贝叶斯 LP（Ferreira、Miranda-Agrippino & Ricco 2025）
- **识别：**Cholesky、符号约束（基本 / 多冲击 RWZ 2010 / 叙事 ADRR 2018 Type 1 + Type 2 / 量级 /
  FEV 份额 / 高阶矩 AFM 2023）、零+符号（ARRW 2018）、长期约束（Blanchard-Quah）、异方差
  （Rigobon 2003）、非高斯 SVAR（Lanne-Meitz-Saikkonen 2017 FastICA + 参数伪 MLE）
- **时变 / 面板 / 混频：**带随机波动的 TVP-VAR（Primiceri 2005）、Lenza-Primiceri 2022
  COVID-VAR、面板 VAR（混合 / 均值组 / 贝叶斯部分混合 / 分层 / 跨国堆叠）、MF-VAR
  （Schorfheide-Song 2015）、FAVAR（BBE 2005）、BDFM（Banbura-Modugno 2014）
- **预测 / 分解：**迭代预测、滚动窗口样本外、Diebold-Mariano、条件预测（BGL 2015）、历史分解、
  结构 FEVD、溢出指数（Diebold-Yilmaz 2012）
- **滤波 / 周期定年：**HP 滤波、Hamilton 2018 滤波、Beveridge-Nelson、Kamber-Morley-Wong 2018
  BNF、简化的 Bry-Boschan / Harding-Pagan 定年
- **预处理 / 数据：**平减 / 还原名义值、聚合（混频）、插补（线性 / Kalman / 基于 Shumway-Stoffer
  的 EM）、中国官方数据清洗（`lib.preprocess.china`）、FRED-MD/QD 读取、可插拔 fetcher（FRED、
  国家统计局、DBnomics、ONS、BoE IADB、外部存档）
- **验证：**`compare_to_paper`（论文目标验证），以及用于超参数扫描的 spec / run / diagnostics /
  sensitivity 层

对于非 Python 的目标语言（R / Julia / Matlab），agent 按同样的方法论生成代码，以 lib 各模块的
docstring 为标准规格。

## 工作区结构

```
marco-workspace/
├── README.md                       本文件
├── CLAUDE.md                       agent 的操作说明
├── MODIFICATIONS.md                相对上游的修改说明
├── DEVELOPMENT.md                  架构 + 如何添加新方法（英文）
├── CONVENTIONS.md                  scripts/lib/ 使用的数学约定
├── TEST_SUITE.md                   agent 行为的人工检查清单（英文）
├── config.yaml                     agent 读取的推荐默认值（lib 不读取）
├── requirements.txt                Python 依赖
├── CITATION.cff, LICENSE, NOTICE, SECURITY.md
├── .marco-workspace.json           工作区清单（插件升级用，不要手工修改）
│
├── skills/                         工作流 + 知识，每个 skill 一个目录
│   ├── orchestrator/               主循环（七阶段工作流）+ 模式分流
│   ├── knowledge-base/             经济体概况（context/ 初始为空；由你填写）
│   ├── model-dictionary/           index.yaml + entries/（经典论文设定）
│   └── <其他 skill>/SKILL.md        决策规程、产出、研究日志
│
├── scripts/
│   ├── lib/                        Python 参考库（估计、数据、预处理）
│   ├── replications/               复现示例，每个字典条目一个目录
│   ├── applications/               你自己的分析（初始为空）
│   └── tools/                      工具（国家统计局下载 / 查询、作者档案）
│
├── data/
│   ├── registry.yaml               数据集注册表
│   ├── nbs_m/ nbs_q/ nbs_a/        国家统计局面板：panel.yaml + UPDATE.md；数据由 nbs_update.py 生成
│   ├── fred_md/                    UPDATE.md + 变换编码；dataset.csv 由 UPDATE.md 的步骤生成
│   ├── fred_qd/                    UPDATE.md + 变换编码和因子标记；同上
│   ├── staging/                    原始下载和暂存的序列（gitignore）
│   └── <id>/                       运行时抓取的缓存（由 lib.fetch_data 创建）
│
├── papers/                         为模式 B 暂存的原文 PDF（PDF 被 gitignore）
├── tests/                          1,000 多个单元测试 + 慢速的覆盖率 / 冒烟测试
└── outputs/                        根目录草稿区；每次运行的结果在 scripts/<tier>/<id>/outputs/
```

架构原则、标准化的 IRF/FEVD 输出约定，以及如何添加新的估计方法或经典复现，见
[DEVELOPMENT.md](DEVELOPMENT.md)。

## 给框架开发者

如果你在改造框架本身（而不是用它做研究），见：

- [`CLAUDE.md`](CLAUDE.md)：agent 在这个工作区中被调用时的定向说明
- [`DEVELOPMENT.md`](DEVELOPMENT.md)：架构 + 接口约定
- [`CONVENTIONS.md`](CONVENTIONS.md)：由测试固定的数学约定
- [`scripts/lib/README.md`](scripts/lib/README.md)：Python 库的模块和依赖关系
- [`tests/README.md`](tests/README.md)：测试纪律，以及每一层测试固定了什么

## 隐私与数据流向：用于内部数据之前必读

agent 会话会把你的提示以及 agent 读取的任何文件内容（包括你让它读的数据文件）发送给模型服务商的
API 处理（在 DeepSeek Harness 中，是你为它配置的模型服务）。在把框架用于**保密的内部序列或未发表的
分析**之前，先按你所在机构的政策确认，包括机构批准的部署方式和数据保留条款。预置的 FRED 数据、
国家统计局公开数据和复现示例库都是公开的，不涉及这个问题。可选的顾问规程
（`skills/advisor-protocol/`）让 agent 把数学问题发给第二个模型，使用 `config.yaml` 中设置的服务商。
在你把那里的 `advisor.enabled` 设为 `true` 之前，它是关闭的。开启后，它只应发送公式和推导，绝不发送
数据；这是对 agent 的指示，不是技术过滤（见其 SKILL.md）。

## 验证状态和预期用途

这是一个研究工具：产出是专家判断的输入，不是官方统计或政策建议，每次运行都设计为要经过审阅
（提案 → 确认关口、合理性检查、研究日志）。验证是尽力而为；尽管如此，仍可能存在错误。支撑这些数字
的是：

- 参考库的数学约定由 1,000 多个测试固定，包括已知数据生成过程上的参数还原约定，以及递归 VAR 和
  局部投影区间的蒙特卡洛覆盖率研究；
- 经典复现对照逐篇论文的 `paper_targets.yaml` 约定进行验证。论文报告了可直接比较的数字时，目标取
  论文本身的数字；对大多数复现，部分或全部目标是作者自己同一复现的结果，它们能发现回归，但本身不能
  证明与论文一致（文件头或每个目标的 `location` 字段会说明是哪种）；
- 每个字典条目都逐字段对照原始论文 PDF 核对过；
- 与论文的已知差异（样本缺口、方法演示）记录在各复现的 README 中；
- 开发过程中，库的一部分曾与独立的 MATLAB 工具箱做过数值比较：频率学派 VAR 层，以及贝叶斯 VAR 和
  符号约束代码中的部分组件。这些是一次性的检查。记录和约定差异见
  [`DEVELOPMENT.md`](DEVELOPMENT.md) 的"Independent cross-checks"一节和 `CONVENTIONS.md`；
- 集合识别和 LP 方法的标准推断批评记录在 `CONVENTIONS.md` 第 4 节和相关 docstring 中。

各方法的证据强度并不相同。VAR 层（OLS 估计，递归、长期约束和单工具变量 proxy 识别，脉冲响应和分解）
以及 HP 和带通滤波器与独立实现做过比较；Minnesota BVAR 和符号约束抽样器在开发中比较过一次；所有
其他方法，包括时变、混频、因子、面板和非高斯模型，依赖的是库自己在模拟数据上的测试。最后这一组的
结果需要更谨慎：结果重要时，用另一个实现核对。[复现索引](scripts/replications/README.md)为每个
复现标注它是遵循论文设定、用论文的系统但修改了方法，还是只演示方法。

国家统计局数据层（`nbs_client`、`lib.preprocess.china`）是本插件新增的，由 `tests/test_nbs.py`
覆盖，未经上游作者审阅。

## 发布

上游框架以独立压缩包形式随工作论文发布，公开仓库是同一版本的冻结副本。本工作区由 DeepSeek Harness
插件 `marcobis` 生成。

## 如何引用

见 [`CITATION.cff`](CITATION.cff)（GitHub 据此显示"Cite this repository"按钮）。引用时请引用
上游的 BIS 工作论文。

## 许可

[Apache-2.0](LICENSE)。Copyright © 2026, Bank for International Settlements。见
[`NOTICE`](NOTICE) 和 [`SECURITY.md`](SECURITY.md)（漏洞报告）。

## 免责声明

以下为上游免责声明原文（英文为准）：

The repository content is provided "as is", without warranty of any kind, express or implied, including but not limited to the warranties of merchantability, fitness for a particular purpose and noninfringement. Nothing in the License shall constitute, or be construed as constituting a waiver, express or implied, of any privileges, immunities and/or exemptions enjoyed by the BIS. See the License for more details regarding permissions and limitations. Copyright © 2026, Bank for International Settlements.

This repository contains sample code. The code was developed for the purposes of an experimental project. The content in this repository does not constitute regulatory, financial, legal or any other professional advice and should not be acted on as such. BIS shall not be liable for any damage or loss of any kind howsoever caused as a result of the use of the information contained or referenced in this repository.

This repository is not maintained. No contributions are expected and issues or pull requests are likely to remain unresolved.

The views expressed in this repository are those of the authors and do not necessarily reflect the views of the BIS or its member central banks. The authors acknowledge the use of artificial intelligence in research assistance and editorial refinement. Responsibility for all errors remains with the authors. References to individual firms and projects are for illustrative purposes and should not be construed as any statement on the soundness or the legal or regulatory status of any firm or project.

中文大意：仓库内容按"原样"提供，不作任何明示或暗示的保证；不构成监管、金融、法律或任何其他专业
建议；BIS 不对因使用其中信息造成的任何损失负责；仓库不再维护；文中观点属于作者，不一定代表 BIS 或
其成员央行的观点。
