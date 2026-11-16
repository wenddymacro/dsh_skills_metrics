---
name: model-dictionary
description: >
  从文献中提取的计量建模方法登记册：以结构化设定的形式记录，已对照原始论文核对，每个条目都记录
  了核验来源。每个条目用结构化字段记录关键的设定决策（变量、先验、识别、样本），agent 不必阅读或
  解读原始论文就能检索。在模型选择和设定之前使用：agent 浏览字典，为用户的研究问题找到最相关的
  方法，然后提出建议。按索引查找减少了运行时反复从论文中提取信息；条目仍可能有错，需要接受审阅。
  任何 skill 需要基于文献的指引，或用户问"文献怎么建议""该参照哪篇论文""这个问题以前用过什么
  设定"，或提供一篇新论文要加入字典时触发。
---

# 模型字典

## 目的

模型字典是框架对计量文献的"机构记忆"。agent 不必在运行时阅读论文、冒着误读的风险，每个条目都以
结构化格式记录一篇论文的核心建模决策。条目先起草，再逐字段对照原始论文核对，并始终接受审阅。

**字典是起点，不是约束。**agent 的模型自身知识在每一步都保持活跃：建议调整、发现字典条目的
空白、提出新的组合、推理没有哪篇论文单独覆盖的设定，并在条目之间建立联系。

条目文件（`entries/*.yaml`）和索引（`index.yaml`）是结构化数据，保留英文原文：测试依赖其字段
和受控词表。

## 字典与模型自身知识怎样配合

二者互补，而不是先后顺序：

| 情形 | 字典提供 | 模型自身知识提供 |
|-----------|--------------------|-----------------------------|
| 经典问题（货币政策传导） | CEE (1999) 经过核验的设定 | "鉴于你的样本较短，可以把先验收得比 CEE 更紧" |
| 新问题（气候风险 + 货币政策） | 没有完全匹配，但有相关条目 | 创造性组合："从标准的货币 VAR 出发，按照 Sims (1992) 控制大宗商品价格的思路，加入一个气候风险变量" |
| 调整到另一个经济体 | 美国设定作为模板 | "对于你们这样的小型开放经济，汇率渠道占主导，所以调整 Cholesky 顺序，并考虑加入外国利率" |
| 先验选择 | GLP (2015) 的最优超参数作为参考 | "你的样本只有 GLP 的一半长，可能需要比他们的最优值更紧的先验" |
| 出乎意料的结果 | 用于比较的预期结果 | "第 8 期的符号反转不在字典的预期结果里，但与汇率超调的文献一致。这可能不是设定错误" |
| 合理性检查失败 | 已知的补救办法（为价格之谜加入大宗商品价格） | "标准补救在这里不起作用。可能是因为你们经济体的大宗商品出口结构，大宗商品价格对国内政策是内生的" |

字典降低了 agent 记错 Sims (1980) 实际设定的风险。模型自身知识防止 agent 把 Sims (1980) 生搬
硬套到不合适的情形中。

## 字典*不*做什么

- 它不取代 agent 的推理。agent 应当始终思考某个字典条目是否合适，而不只是查到就用。
- 它不把 agent 限制在已记录的方法内。如果用户的问题在字典里没有匹配，agent 用模型自身知识提出
  一个设定，并标出来请用户审阅。
- 它不妨碍 agent 建议修改字典条目。"CEE (1999) 用了 7 个变量，但对于你 80 个观测的样本，我建议
  去掉准备金，改用 5 个变量"，正是 agent 应当提供的那种推理。
- 它不让框架变成确定性的。用户背景不同的两次运行，应当对同一个字典条目做出不同的调整。

## 结构

```
model-dictionary/
├── SKILL.md                  （本文件）
├── entries/                  每种建模方法一个 YAML 文件
│   ├── sims_1980_var.yaml
│   ├── litterman_1986_bvar.yaml
│   ├── cee_1999_monetary_svar.yaml
│   ├── glp_2015_prior_selection.yaml
│   ├── bgr_2010_large_bvar.yaml
│   ├── uhlig_2005_sign_restrictions.yaml
│   ├── jorda_2005_lp.yaml
│   ├── primiceri_2005_tvpvar.yaml
│   └── ...
└── index.yaml                可检索的索引（手工维护；由 tests/test_doc_consistency.py 保持同步）
```

## 条目结构

每个字典条目都遵循同样的结构化格式。字段是为检索和匹配设计的，不是为了好读。（条目可以在核心
结构之外加入可选部分，例如带 `replication:` 指针和数据对齐说明的 `implementation_notes`，或
`construction_methodology` 这类方法专属的部分；见 DEVELOPMENT.md 的"Established conventions"
一节。）

```yaml
# --- 标识 ---
id: "<author_year_topic>"           # 唯一，snake_case
citation:
  authors: "<作者>"
  year: <年份>
  title: "<标题>"
  journal: "<期刊或书名>"
  volume: "<卷>"
  pages: "<页码范围>"

# --- 这个方法回答什么问题？ ---
research_questions:
  - "<研究问题>"
tags:
  - <标签>

# --- 模型设定 ---
model:
  class: "<模型类别>"                 # var | bvar | structural_var | sign_var | lp | tvp_var | stvar | panel_var | favar | dfm | mfvar | filter | shock_series
  prior: <null | 先验名称>            # 经典方法为 null；"minnesota"、"sims_zha" 等
  variables:
    endogenous:
      - name: "<变量名>"
        proxy: "<用来度量它的序列>"
        transform: "<log | level | diff>"
        role: "<在模型中的作用>"
    exogenous: []
  lags: <滞后阶数>
  frequency: "<monthly | quarterly | ...>"

# --- 识别 ---
identification:
  # method 是一个受控词表（由 tests/test_doc_consistency.py 强制检查）：
  #   cholesky | long_run | sign_restrictions | narrative_sign_restrictions |
  #   sign_restrictions_plus_higher_moments | external_instrument |
  #   heteroskedasticity | non_gaussian_independent_components |
  #   generalised_variance_decomposition | none | varies
  # 细节写在同一行的注释或 rationale 里，不写进取值。
  method: "<识别方法>"
  ordering:                           # 或者按方法需要写约束
    - "<变量名>"
  rationale: >
    <识别为什么成立，附论文页码>

# --- 样本 ---
sample:
  start: "<起始期>"
  end: "<结束期>"
  notes: "<样本对应的论文页码；任何截断都作为明确的偏离写出>"

# --- 预期结果（用于合理性检查） ---
expected_results:
  <冲击名称>:
    <变量>: "<预期响应，附论文页码>"
  notes: >
    <预期结果的背景说明>

# --- 何时推荐这个方法 ---
recommend_when:
  - "<条件>"
not_recommended_when:
  - "<条件>"
alternative_approaches:
  - id: "<其他条目 id>"
    reason: "<何时更适合用它>"

# --- 核验状态 ---
verified:
  status: "<draft | checked_against_paper | signed_off>"   # 见下面"核验状态"
  date: "<YYYY-MM-DD>"
  against: "<条目对照什么核对过>"
  pdf_location: "papers/<id>.pdf"    # 核验时的本地文件名；PDF 不随框架分发（见 papers/README.md）
  notes: "<所做的更正，附论文页码>"
```

完整示例见 [`entries/cee_1999_monetary_svar.yaml`](entries/cee_1999_monetary_svar.yaml)。

### 字段来源：论文的论断与框架的编辑内容

一个条目混合了两类内容，二者的区分必须保持清楚，因为这正是原作者读到条目时条目能站得住的原因：

| 来源 | 字段 | 标准 |
|---|---|---|
| **归属于论文** | `citation`、`model`（变量、滞后、频率、确定性项）、`identification`（方法、顺序 / 约束、理由、`headline_finding`）、`sample`、`expected_results` | 条目依赖的每个论断都附有原始论文的页码 / 表 / 图 / 公式出处。绝不把在论文里指不出来的东西归于论文；引用的措辞必须接近原文。 |
| **框架的编辑内容** | `research_questions`、`tags`、`recommend_when`、`not_recommended_when`、`alternative_approaches`、`implementation_notes` | 我们关于何时、如何使用该方法的判断。**不是**论文作者的陈述，也未经作者认可；措辞要与此相符。 |

相对于论文的数据替代和样本截断，写在条目的 `sample.notes` / `implementation_notes` 和对应复现
的 README 中，始终作为明确的偏离，绝不悄悄当作论文本身的设定。

`scripts/tools/make_author_dossiers.py` 把每个条目渲染成面向作者的档案，正是按这一区分组织的
（我们归于论文的、我们复现的、我们改动的、属于我们自己的）。实用的站得住检验是：*你愿意把这份
档案发给论文作者吗？*防漂移测试负责机械的那一半（`checked_against_paper` 条目必须有页码出处）。

## agent 怎样使用字典

### 第 1 步：解析研究问题

从用户的请求中提取关键词：
- 主题："货币政策""财政政策""汇率"等。
- 目标："传导""预测""识别"等。
- 背景："美国""小型开放经济""新兴市场""中国"等。

### 第 2 步：搜索字典

与索引的 `questions` 和 `tags` 字段匹配，形成候选清单。然后阅读候选条目的全文（包括
`recommend_when` 和 `not_recommended_when`），判断是否合适：背景、推荐情形，以及任何实现上的
差异。索引是英文的，用中文提问时先把关键词译成英文再匹配。

```
用户："货币政策如何影响产出和通胀？"

排序后的匹配：
  1. cee_1999_monetary_svar       （与研究问题完全匹配）
  2. sims_1980_var                （奠基之作，同一问题）
  3. uhlig_2005_sign_restrictions （同一问题，不同识别）
  4. primiceri_2005_tvpvar        （同一问题，时变）
```

### 第 3 步：按背景筛选

根据知识库应用 `not_recommended_when` 筛选：
- 经济体是开放的 → 筛掉只适用于封闭经济的条目。
- 样本较短 → 筛掉需要长样本的条目。
- 用户偏好符号约束 → 筛掉只用 Cholesky 的条目。

### 第 4 步：给出推荐

展示排名前 1–3 的匹配及其完整设定，引用字典条目（而不是原始论文：条目本身就是经过核验的信息
来源）。

> "关于货币政策传导的问题，文献提供了三种方法：
>
> 1. **Christiano、Eichenbaum、Evans (1999)：**7 变量结构 VAR，递归识别。加入大宗商品价格以消除
>    价格之谜。[已对照原文核验]
>
> 2. **Sims (1980)：**6 变量 VAR，奠基性的方法。更简单，但可能出现价格之谜。
>
> 3. **Uhlig (2005)：**用符号约束代替 Cholesky 顺序。更不预设立场，但置信带更宽。
>
> 结合你的经济体概况（美国、长样本、关注传导），我建议从 CEE (1999) 开始。要我建立这个设定吗？"

字典中的条目都基于美国或其他发达经济体的数据。用于中国时，模型自身知识和知识库要说明需要做的
调整（数据来源、政策工具、样本区间、季节性），这正是第 1 个表格所说的"调整到另一个经济体"。

### 第 5 步：采用设定

用户确认后，以条目作为论文设定的参考。条目描述的是论文；对应的复现可能使用不同的估计量、样本或
数据。阅读复现的 `config.yaml` 和 `README.md`，注明它与论文的不同之处，并通过主控的第 1A 阶段
确认可执行的设定。对于新的或经过调整的实现，把条目和待定的选择交给 specification skill，由它通过
知识库按本地情形调整（例如本地数据来源、变量代理）。

## 添加新条目

### 来自用户提供的论文

1. 用户上传或提供一篇论文的引用。
2. agent 把建模选择提取成条目草稿。
3. agent 逐字段对照论文核对草稿，加上页码出处，并把 `verified.status` 设为达到的级别。
4. 用户审阅草稿。确认后，条目保存到 `entries/`，并更新 `index.yaml`。

### 来自 agent 的模型自身知识

agent 可以基于训练知识起草条目，但必须标为 `verified.status: "draft"`，并在被当作权威之前逐字段
对照原始 PDF 核对（升级为 `checked_against_paper`；用户签认后进一步升级为 `signed_off`）。

```yaml
verified:
  status: "draft"                   # 已标记：尚未对照论文核对
  date: "2026-04-11"
  against: "parametric knowledge"
  notes: "AUTO-GENERATED: please verify against original paper"
```

**核验状态**：
`draft` 表示已起草但尚未对照论文核对。`checked_against_paper` 表示已逐字段对照原始 PDF 核对，
并有页码出处。`signed_off` 表示条目还经过了用户确认。model-selection 和 specification skill 应
优先使用 `checked_against_paper` 和 `signed_off` 条目，而不是 `draft` 条目。自带的条目都是
`checked_against_paper`。核验是尽力而为，不是保证。如果某个条目对你的分析很重要，自己对照论文
检查实质性字段，并记录疑似错误。

### 来自完成的分析

一次完成的分析，可以在用户自己的副本中通过上面同样的起草和核对步骤，记录为一个新条目。

## 与其他 skill 的关系

| skill | 怎样使用字典 |
|-------|--------------------------|
| 模型选择 | 搜索 `research_questions` 和 `tags` 来推荐模型类别 |
| 设定 | 新的或调整过的设定，从条目的 `model`、`identification`、`sample` 出发 |
| 合理性检查 | 把结果与 `expected_results` 比较 |
| 基准比较 | 用字典条目作为备选设定进行比较 |
| 知识库 | 对已记录的论文，字典条目优先于模型自身知识 |
| 顾问规程 | 用条目作为审阅的参考；何时升级由[顾问规程](../advisor-protocol/SKILL.md)及其启用设置决定 |

## 质量优先于数量

宁可少一些对照论文核对过的条目，也不要很多未核对的条目。条目只有在对照原始论文核对之后才被视为
权威。

## 索引生成

索引是一个扁平文件，列出所有条目及其可检索字段，手工维护，并由测试
（`tests/test_doc_consistency.py`）防止漂移。格式见 [`index.yaml`](index.yaml)。

agent 检索时只加载索引，然后只为匹配的结果读取完整条目。这样即使字典不断增大，查找仍然很快。
