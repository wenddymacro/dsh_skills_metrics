# 开发指南

## 架构理念

框架的构造使每个部分都可以改动而不破坏其他部分。每个设计决策都把适应性放在首位：

1. **skill 是模块化的。**只要其他 skill 依赖的约定（它的输入、输出和交接）仍然成立，一个 skill 就可以
   单独修改或替换。主控负责委托，不包含估计逻辑。
2. **接口约定，而非实现细节。**skill 之间通过结构化的输入和输出通信。只要约定成立，内部实现可以自由
   改动。
3. **主控是协调者，不是控制者。**它定义工作流的各个阶段，在 skill 之间分派。它自己负责的领域任务是
   第 5 阶段的经济合理性检查；设定、估计和呈现在各自的 skill 和库里。如果要改工作流本身，编辑
   `skills/orchestrator/SKILL.md`（模式分流在 `modes.md`）。
4. **知识库与逻辑分离。**经济背景（先验、数据来源、惯例）放在知识库里，不写死在估计 skill 中。改变
   国家背景永远不需要编辑 skill。
5. **渐进的复杂度。**可选的 skill（benchmarking、顾问规程、consistency-audit）增加能力，但不给标准运行
   增加负担。

## 接口约定

Python 层面的约定是拟合对象 API（`VARFit` 的子类、`parameter_draws()`）和 `IRFContainer`
（`scripts/lib/irf.py`）。下面这些 YAML 结构描述的是 agent 报告的内容，不是 Python 的输入输出。它们是
主控、研究日志和 results-presentation skill 使用的概念结构。

库使用的**数学约定**（期限下标、归一化、B_hat 布局、ddof 选择等）见 [`CONVENTIONS.md`](CONVENTIONS.md)。
从代码写公式，或把论文的数学翻译成库调用时，先查那个文件。


### 设定记录

specification skill 的[输出结构](skills/specification/SKILL.md#产出)就是决策记录：每个实质性选择及其
理由和知识来源，由 research-log skill 记录。方法可以添加模型特有的字段（例如 BVAR 的 `prior`、LP-IV 的
`instrument`）。这个记录不是运行配置：估计脚本通过 `lib.Spec`（`scripts/lib/specs.py`）读取自己的
`config.yaml`。

### 结果结构

agent 按以下结构报告每次估计运行：

```yaml
results:
  specification: 输入的回显（用于审计追踪）
  estimation_summary:
    method: string（人类可读的名称）
    convergence: dict 或 null（迭代方法）
  structural:
    irf: 标准化的 IRF 结构（见下）
    fevd: 标准化的 FEVD 结构或 null
    historical_decomposition: 结构或 null
  diagnostics: dict（来自 diagnostics skill，或内联）
  sensibility_flags: 字符串列表
  charts: 文件路径列表
  code_archive: 文件路径列表（所用的脚本）
```

### 标准化的 IRF 结构

无论用什么估计方法，agent 都按这个结构报告脉冲响应。在 Python 中，同样的内容是一个 `IRFContainer`：

```yaml
irf:
  shock_name:
    variable_name:
      horizon: [0, 1, 2, ..., H]
      median: [values]
      lower_68: [values]
      upper_68: [values]
      lower_90: [values]
      upper_90: [values]
```

这样 results-presentation skill 不需要知道是哪种方法产生的结果，就能为任何估计方法生成图。它也让 LP
与 VAR 的对比图成为可能：两者输出同样的结构，叠加起来很简单。

### 标准化的 FEVD 结构

```yaml
fevd:
  horizon:
    shock_name:
      variable_name:
        median: float
        lower_68: float
        upper_68: float
```

## 如何添加新的估计方法

方法论放在 `scripts/lib/`，不放在 `skills/`。添加一个新方法按以下清单进行：

1. **在 `scripts/lib/` 中添加一个模块**，遵循 [`scripts/lib/README.md`](scripts/lib/README.md) 中的
   模式：遵守依赖关系（DAG）的导入、拟合对象 API 和 `IRFContainer` 输出（见上面"接口约定"），如果
   拟合类型需要不确定性区间，还要有 `parameter_draws()` 方法。如果新方法是一种新的识别方案或约束方式，
   优先在现有模块中加一个参数（例如 `sign_restricted_irf` 上的 `higher_moment_restrictions`），而不是
   新建一个顶层函数。

2. **在 `tests/` 中添加单元测试。**至少包括：在一个小的合成例子上实例化、IRF / FEVD 输出约定测试，以及
   对任何新的数学选择（期限下标、归一化、ddof 等）在 `tests/test_conventions.py` 中加一个闭式约定契约。
   对输出有随机性的方法，在 `tests/test_coverage.py`（慢）中加一个蒙特卡洛覆盖率测试。

3. **更新 [`skills/model-selection/SKILL.md`](skills/model-selection/SKILL.md) 中的模型库表格。**
   加一行，写明模型类别、最适合的用途、样本要求、识别选项和库入口（`lib.<function_name>`）。

4. **如果适用，配一篇经典论文。**在
   [`skills/model-dictionary/entries/<id>.yaml`](skills/model-dictionary/entries/) 中加一个 YAML 条目，
   最好再在 [`scripts/replications/<id>/`](scripts/replications/) 下加一个可运行的复现，包含
   `config.yaml`、`replicate.py`、`README.md` 和 `paper_targets.yaml`。在 replicate.py 末尾运行
   `lib.compare_to_paper`，对照声明的论文主要数字进行验证。

5. **端到端冒烟测试。**把新的复现加入 `tests/test_replications_smoke.py`（慢）。确认在
   `pytest --runslow` 下流程能无错运行。

6. **在 [`TEST_SUITE.md`](TEST_SUITE.md) 中添加一个行为测试。**如果新方法引入了 agent 会分派到的、
   面向用户的行为（新的识别方案、新的先验、新的估计量），按"提示 / 预期 / 测试什么"的格式在第 5 层
   （或相关的层）下加一个测试。只有对没有 API 变化的纯内部重构才可以跳过。

就这些。主控不需要改动；第 4 阶段通过 `lib.run` 或生成的 `replicate.py` 直接调用新的 lib 函数。不需要
新的 SKILL.md 文件；见 [`CLAUDE.md`](CLAUDE.md) 中"这个项目是什么"一节的三层架构。

### 添加新的工作流 skill

与添加方法不同：如果你想添加一个新的*工作流* skill（与现有的主控 / 模型选择 / 设定 / 诊断 / 研究日志
等并列的新决策规程、输出格式或治理模式），原来的 SKILL.md 写法仍然适用：

1. 创建 `skills/<workflow-skill-name>/`，其中的 `SKILL.md` 包含 frontmatter（`name`、`description`）、
   目的、输入 / 输出，以及何时调用。
2. 把它接入主控的"调用子 skill"表格。
3. 如果开发会话或研究会话依赖这个 skill，更新 CLAUDE.md 的文件分工表。

这条路径比添加方法少见；大多数扩展发生在 `scripts/lib/`。

### 其他扩展点

- **新的数据来源：**在 `scripts/lib/data/fetchers/` 下添加一个 fetcher，并在 data-retrieval skill 中
  说明。国家统计局的 `nbs` fetcher（配合 `scripts/lib/data/nbs_client.py`）就是一个例子。
- **新的预置面板：**仿照 `data/nbs_m/` 写一个 `panel.yaml` 和 `UPDATE.md`，在 `data/registry.yaml`
  中登记。
- **新的顾问服务商：**在 `config.yaml` 的 `advisor:` 下添加一个服务商块。

## 如何修改现有 skill

### 修改实现细节

如果你想改变一个估计方法的内部工作方式（例如把 BVAR 抽样器从 Gibbs 换成哈密顿蒙特卡洛）：

- 编辑 lib 模块（如果是工作流 skill，编辑它的 `SKILL.md`）。
- 确保拟合对象 API 和 `IRFContainer` 输出（见上面"接口约定"）仍然成立。

### 修改接口

如果你需要改变一个 skill 接收或返回的内容（例如给 IRF 结构加一个新字段）：

- 这是破坏性改动。要更新：
  1. skill 本身。
  2. 本指南中的接口约定。
  3. 所有使用被改动输出的 skill（通常是 results-presentation）。
  4. 如果影响工作流分派，还要更新主控。

### 修改工作流

如果你想添加、删除或重新排列主控的阶段：

- 编辑 `orchestrator/SKILL.md`。
- 各阶段是用文字定义的，不是代码。
- 如果添加新阶段，为它创建一个新 skill，并加入子 skill 表格。

### 修改知识库结构

如果你需要新的知识库类别：

- 在 `knowledge-base/context/` 中添加新的模板文件，或创建新的子目录。
- 更新 `knowledge-base/SKILL.md` 中的查找规程。

## 版本

skill 的 frontmatter 只包含 `name` 和 `description`，这是 skill 加载器使用的两个字段。不要添加
`version`、`last_updated` 或 `changelog` 字段；这类逐文件的元数据会悄悄过时。框架版本在
`CITATION.cff` 中。要重现已发表的结果，使用那个发布版本和同样的数据文件。

## skill 的质量标准

### 清晰

- skill 由编程 agent 阅读，它能力强但会按字面理解。把指令写得像是给一位能干但不熟悉情况的同事看的。
- 使用具体的例子，而不是抽象的描述。

### 完整

- 每个 skill 都必须定义：输入、步骤、输出、合理性检查、参考文献。
- 要处理边缘情况：数据缺失、估计失败，或用户的请求不在 skill 范围内时会怎样。

### 简洁

- 尽量让每个 SKILL.md 保持在 500 行以内。
- 把详细的参考材料移到 `references/` 子目录。
- skill 应该能一口气读完。

### 实现：使用软件包，而不是原始代码

- `scripts/lib/` 在 `statsmodels`、`scipy` 和 `numpy` 能覆盖的步骤（OLS VAR 拟合、状态空间平滑、
  信息准则）调用它们，其余方法依据论文实现，并由测试集固定。
- 库已覆盖的方法，就调用库。不要换用别的软件包，也不要写新的估计量（见 `config.yaml` 中的
  `packages:`）。
- 库没有覆盖的方法，优先使用成熟的软件包，而不是自定义代码。
- 在研究日志中记录一次运行使用了哪些软件包及其版本。

### 可测试

- 一个 skill 应能用 Sims (1980) 的例子或等价的经典设定来测试。
- 测试用例的预期输出要写明（至少定性地写："货币冲击后产出应下降，峰值效应约在第 6 个季度"）。

## 保持三层一致

skill、lib 和字典会悄悄地彼此脱节：重建一篇论文的复现改了变量名，却没改固定这些名字的测试；加了一个
方法，主控的能力列表却没更新；删了一个目录，文档里却还有指向它的链接。有两道防线防止这种情况，开发者
在每批 skill / lib / 字典编辑之后两道都要跑：

1. **自动（每次运行测试）：**`tests/test_doc_consistency.py` 机械地检查 YAML 可解析性、索引与条目
   同步、过时的模块数 / 条目数、`verified.status` 是否有效、失效的 skill 链接、悬空的 `lib.*` 引用，
   以及复现目录是否完整。新的*可机械检查*的不变式加在这里。（中文化之后，"模块数 / 条目数"两项检查只
   覆盖英文表述，中文文档中的数字需要人工核对。）
2. **按需（语义）：**[`consistency-audit`](skills/consistency-audit/SKILL.md) skill 覆盖正则做不到的
   部分：阶段编号是否连贯、提案 / 确认流程、文档与实际做法是否一致、孤立的 skill。在发布前或重建后，
   用"审计框架"调用它。

## 来源与许可

`scripts/lib/` 是依据已发表论文写成的原创实现，由测试集固定；没有从 Canova-Ferroni BVAR_ 工具箱
（MATLAB）移植任何代码，它只用作数值约定的独立交叉核对。ECB 的 BEAR 工具箱用作具名约定的方法参考
（区块外生性收缩 lambda5、Villani 均值调整 Gibbs、相对量级符号约束）；也没有从它移植任何代码。
VAR-Toolbox（Cesa-Bianchi）在开发中纯粹用作独立的交叉验证对象（记录见下面"独立交叉核对"）；核对用的
测试框架只在维护者本地，从不分发（它需要 MATLAB 和 GPL-3.0 的工具箱）。FRED-MD / FRED-QD 数据文件
不转发；仓库只附带派生的逐序列元数据（变换编码、因子标记）和下载说明。原文 PDF 同样由用户暂存并被
gitignore（见 `papers/README.md`）。框架本身以 Apache-2.0 许可（见 LICENSE 和 NOTICE）。国家统计局
数据层是插件 `marcobis` 新增的，见 [`MODIFICATIONS.md`](MODIFICATIONS.md)；国家统计局数据不随框架
分发，由 `nbs_update.py` 从官方网站下载。

## 独立交叉核对

开发中，库的部分内容与独立实现做过数值交叉核对：频率学派 VAR 层（估计，递归、长期约束和外部工具变量
识别，脉冲响应，方差分解和历史分解），以及贝叶斯 VAR 和符号约束代码中的部分组件。约定相同的地方，结果
一致到数值精度；有意保留的约定差异在 CONVENTIONS.md 的相应位置有说明。这些是一次性的核对，核对用的
测试框架不分发。`tests/test_differential_statsmodels.py` 是 Python 内部常驻的差分测试。

## 已知缺口

框架没有实现以下内容。当其中某项适合某个研究问题时，agent 会说明，并提出最接近的现有替代方法。

**方法：**VECM / 协整 VAR 和 Johansen 秩检验（specification skill 的单整原则说明了水平 BVAR 的变通
做法）；带随机波动的常系数 BVAR（Carriero-Clark-Marcellino 一类）；结构情景分析和软条件约束
（`conditional_forecast` 是硬条件约束，且仅限简约式）；马尔可夫转换和门限 VAR 以及 GIRF（状态依存 LP
是最接近的替代）；未知日期的结构断点检验（Bai-Perron / QLR）；桥方程、MIDAS 即时预测、预测组合和
包含检验；`lib.report` 中的扇形图；DSGE-VAR。

**推断和选项：**LP-IV 的 Anderson-Rubin 弱工具变量稳健集合；异方差稳健的第一阶段 F（Montiel
Olea-Pflueger）和 Mertens-Ravn 可靠性统计量（proxy 与冲击相关系数的平方 / 可靠性特征值；只实现了
按可靠性调整冲击规模的归一化，而且只适用于单个工具变量）；零 + 符号推断的 ARRW (2018) 算法 3 重要性
权重，以及超出当期的零约束；DFM 载荷归一化（Geweke-Zhou）和 Bai-Ng 因子个数选择；多工具变量 proxy
路径的移动块 bootstrap；LP 的 Andrews 自动 HAC 带宽；`lib.run` 对 var/bvar 以外的分派（面板、LP、
LP-IV、FAVAR、DFM、TVP、MF-VAR 拟合，以及几种识别方法）；BLP 控制变量系数的先验和基于边际似然的 λ
选择；季节调整以及 `scripts/lib/preprocess/README.md` 中列出的其他操作（国家统计局数据大多未经季调，
这一缺口对中国数据尤其重要）。

**数据和环境：**`requirements.txt` 限定 `numpy<2`；Romer-Romer 和 Mertens-Ravn 复现需要暂存数据，
没有任何脚本会下载（openICPSR 116025）；Auerbach-Gorodnichenko 复现从 1959 年开始，而不是论文的
1947 年；国家统计局网站有防火墙，请求过密会被暂时限制访问，年度面板等需要在限制解除后下载。

**已实现部分的已知局限：**
- 蒙特卡洛覆盖率研究（`tests/test_coverage.py`）不覆盖长期约束识别、proxy-SVAR wild bootstrap 或
  BVAR 后验区间。
- proxy-SVAR 的 `one_sd` 估计对象是非标准的（有说明）；基于可逆性的一个标准差冲击才对应通常的对象。
- `_apply_sign_normalization` 对每个冲击只应用第一条 {变量: 符号} 规则，忽略后面的条目。
- 旋转抽样和参数抽样共用一个随机数种子。没有发现可测量的扭曲，而改用独立的随机流会改变每个设定了
  种子的复现，所以保留这一约定。

## 扩展你自己的副本

上游仓库以冻结的压缩包形式发布，不接受 pull request。预期的做法是扩展你自己的副本：

- 在你的副本中添加新的估计方法、字典条目或知识库，遵循接口约定，并达到现有组件满足的核验标准（代码有
  测试，条目逐字段对照原始论文核对）。
- 接口约定就是验收标准：遵循约定的组件就能与框架协同工作。

## 文件列表

完整的目录结构见 [README.md](README.md) 中的工作区结构一节。

---

## 既定约定

新的工作应遵循这些约定，除非有特定的理由偏离；任何偏离都要在复现或应用的 README 中说明。

1. **测试优先的验证，绝不以旧输出为真。**见 [`tests/README.md`](tests/README.md)。默认的验证选择，
   按顺序：
   - 理论性质（例如 h=0 时的 Cholesky IRF = chol(Σ)）
   - 跨软件包（statsmodels 参考）
   - 极限行为（例如 λ→∞ 时，BVAR → OLS）
   - **避免**把"与旧脚本一致"作为主要验证；只把它保留为回归基线

2. **复现目录结构**：每篇论文一个目录，每个目录包含：
   - `README.md`：论文引用、设定、预期结果、相对原文的范围
   - `config.yaml`：全部设定选择（与字典条目对应）
   - `paper_targets.yaml`：（建议）用于验证的论文数值；见
     [`scripts/replications/README.md`](scripts/replications/README.md) 中"论文目标验证"一节
   - `replicate.py`：薄的编排脚本（最多几百行），所有重活在 `lib` 里
   - `outputs/`：HTML 报告、数值快照、研究日志（运行时生成；被 gitignore，所以通过 `replicate.py`
     重新生成）

3. **字典条目与复现。**条目是论文设定；复现是可运行的演示。`verified.status` 的级别在
   [`skills/model-dictionary/SKILL.md`](skills/model-dictionary/SKILL.md)（"核验状态"）中定义。条目
   描述的是文献，不是实现。

4. **记录在案的替代。**许多复现用 FRED-MD/QD 的序列替代论文特有的数据（EBP、ff4 工具变量、新兴市场
   主权债券）。每个 README 都明确记录了这些替代，以及它们保留了什么、没保留什么。论文目标验证框架
   （`lib.compare_to_paper`）在构建时把替代引起的偏离明确显示出来。

5. **拟合对象的输出与识别函数对接。**`BVARFit`、`SteadyStateBVARFit`、`MFVARFit`、`TVPVARFit`、
   `PanelVARFit`、`HierarchicalPanelVARFit` 都是 `VARFit` 的子类；支持基于抽样推断的拟合会重写（或像
   全局 VAR 面板拟合那样继承）`parameter_draws()`，并接入 `cholesky_irf` / `long_run_irf`
   （`bands="parameter_draws"`）和 `sign_restricted_irf`（`parameter_uncertainty=True`）。混合、
   均值组和部分混合面板拟合只有点估计（`bands="none"`）；见模型选择的表格。新的拟合类型应遵循这一
   模式。

6. **Windows 控制台编码陷阱。**`cp1252` 无法显示 `→`、`Δ`、`Φ`、`Σ`、`≈` 这类 Unicode 字符。复现
   脚本的 print 语句应使用 ASCII 替代（代码内部可以使用 Unicode）。中文 Windows 控制台（GBK）也会遇到
   类似问题；国家统计局工具脚本输出中文，在 Windows 上运行时可能需要设置 `PYTHONIOENCODING=utf-8`。

7. **状态空间封装。**`StateSpaceModel` 是 `statsmodels.tsa.statespace.SimulationSmoother` 的薄封装。
   支持三维时变 `Z`、三维时变 `H`、二维时变 `obs_intercept`。原生处理 NaN 观测。

8. **三种入口模式的分流（主控）。**会话从模式 A、B 或 C 开始，可以在会话中途转换模式；见
   [`skills/orchestrator/modes.md`](skills/orchestrator/modes.md)。

9. **三个来源层级。**`scripts/replications/<id>/`（经典，公共示例，在模式 A 搜索中排在前面）、
   `scripts/applications/<id>/`（你过去的工作；以"你做过类似的"形式提出）、`outputs/`（草稿区，始终被
   gitignore，从不作为主控的来源；生成的模型产出可以再生，但保存在那里的会话记录不能，删除之前必须复制
   出来）。模式 B 和 C 的运行默认提升到 `applications/`；提升为经典很少见。

10. **agent 行为。**见 [`CLAUDE.md`](CLAUDE.md) 中的行为规则。

11. **数据层分离。**`lib.load_dataset(source, series, start, end, vintage)` 返回结构上干净的原始数据，
    以及 `df.attrs` 中的来源元数据（source、vintage、frequency、url、loaded_at、样本起止，逐序列的
    source_code + 来自 FRED-MD `transform_codes.csv` 的 recommended_transform）。`lib.transform(df,
    transforms)` 作为单独的一步做逐列变换（level / log / diff / log_diff / pct_change / 缩放变体），因为
    变换的决定属于模型。

12. **spec / run / diagnostics / sensitivity 层。**这是框架建立在确定性的库之上的*灵活性*骨架。
    `lib.Spec` 是一个不可变的 dataclass，结构与现有复现配置相同（`data` / `model` / `irf` /
    `forecast` / `metadata`）；`Spec.from_replication(id)` 把一个复现的 `config.yaml` 读成 `Spec`；
    `Spec.update(**overrides)` 深度合并到嵌套块中（部分覆盖会保留同级字段）。当模型类别（var、bvar）
    和识别方式（cholesky、sign_restrictions、proxy_svar、long_run）受支持时，`lib.run(spec, seed)`
    执行它，否则抛出 `NotImplementedError`；其余情况用复现的 `replicate.py`。它还会运行可选的预测块，
    返回一个 `SpecResult`。`lib.diagnostics(fit)` 一键生成残差 + 稳定性 + 滞后选择报告。
    `lib.sensitivity(base_spec, grid)` 是在 `lib.run` 上的笛卡尔积超参数扫描。它们一起让"我想用不同的
    λ₁ / 滞后阶数 / 样本跑论文 X"只需三行代码，而不用编辑 config.yaml 再重跑一个 200 行的 replicate.py。

13. **约定契约 + 论文目标验证**：在构建时发现漂移的两道互补防线：
    - [`tests/test_conventions.py`](tests/test_conventions.py) 保存固定框架数学约定（期限下标、
      归一化、B_hat 布局、ddof 选择）的闭式契约。任何带有约定选择的新 lib 函数都应在这里加一个契约。
    - [`CONVENTIONS.md`](CONVENTIONS.md) 是写公式时所用约定的文字参考；在把代码翻译成公式或反过来
      之前查阅。
    - `lib.compare_to_paper(results, paper_targets.yaml)` 提供逐复现的、对照声明论文数值的验证；做法见
      [`scripts/replications/README.md`](scripts/replications/README.md)。

## 架构决策

### 库

- **状态空间和 Gibbs 工具是根节点**，由 MF-VAR、TVP-VAR 和 DFM 共享。如果某个功能被不止一个下游
  模块需要，先把它提取成叶子层的工具。
- **没有延迟导入。**`_ensure_psd` 放在 `var.py`，这样 `inference.py` 导入它时不会形成环。新出现的延迟
  导入是一个坏味道。
- **`stochastic_volatility.py` 是自包含的**，可以在 TVP-VAR-SV、将来的 Cogley-Sargent 应用以及任何
  需要单变量随机波动的模型中复用。即使 `tvp.py` 是眼前唯一的调用者，也不要把随机波动的逻辑放进去。
- **Primiceri 2005 有三个实现**（`fit_tvp_var`、`fit_tvp_var_sv`、`fit_tvp_var_sv_primiceri`），
  反映复杂度的层次。现有的 `primiceri_2005_tvpvar/` 复现使用最简单的那个。换成
  `fit_tvp_var_sv_primiceri` 只需改 `replicate.py` 里的配置。
- **结构扩展**：有些字典条目带有 `model-dictionary/SKILL.md` 结构之外的字段（例如
  `implementation_notes.fred_alignment` 和 `verified.notes`）。保留它们，因为其中有 agent 需要的信息。
- **`fit_var` 增加了 VARX 支持**，用一个集中的 `_build_x_row` 辅助函数，供三个 bootstrap 调用点使用
  （`inference.residual_bootstrap_draws`、`identification._proxy_wild_bootstrap`、
  `identification._proxy_wild_bootstrap_multi`）。约定契约强制这种集中化。
- **多冲击 RWZ 2010、ADRR 2018（Type 1 + Type 2）、FEV 份额、相对量级和 AFM 2023 高阶矩约束在
  `sign_restricted_irf` 中都可以组合使用**：一个函数，在 `len(shock_names) > 1` 时分派到单独的
  `_sign_restricted_irf_multi_shock`。

### 数据层

- **运行时 fetcher 放在 `scripts/lib/data/fetchers/`**，通过 `lib.fetch_data(api, series,
  dataset_id, ...)` 实现 cache-on-fetch。`data/<id>/` 下的每个数据集目录在多次调用中累积列（无论用户的
  样本如何，都缓存完整序列）；逐序列来源信息在 `metadata.yaml`；抓取的数据集登记在被 gitignore 的
  `data/registry.local.yaml`。
- **`load_dataset` 与 `fetch_data`**：`load_dataset` 从注册表读取（FRED-MD、FRED-QD、国家统计局面板
  等预置数据）；`fetch_data` 访问实时 API（FRED、国家统计局 nbs、DBnomics、ONS、BoE IADB、外部存档）。
  两者都返回在 `df.attrs` 中带来源信息的 DataFrame。`load_dataset` 在读取时筛选；`fetch_data` 缓存完整
  历史，再通过参数筛选。
- **国家统计局面板**由 `scripts/tools/nbs_update.py` 按 `data/nbs_*/panel.yaml` 生成，清洗步骤在
  `lib.preprocess.china`。平台客户端 `nbs_client.py` 只用标准库联网，网站有防火墙，任何新代码都不能
  并行请求或高频请求。
- **`lib.preprocess`** 存放考虑频率的预处理（`deflate`、`nominalise`、`aggregate`、`impute`、
  `china`），区别于逐列标量变换的 `lib.transform`（log、diff、log_diff、pct_change）。趋势-周期滤波
  留在 `lib.filters`。
- **PeriodIndex 与 Timestamp 的对齐陷阱**：FRED-QD 和 `nbs_q` 使用季末的 Timestamp；
  `pd.resample("QS").mean()` 返回季初的 Timestamp。直接合并两者会得到全是 NaN 的行。把它们与外部
  重采样的数据混合时，合并前先把两边都转成 `PeriodIndex('Q')`。

## agent 的工作方式

- **报告负面发现。**Rigobon 2003 的弱识别结果，以及 BBE 2005 用 FRED-MD 替代数据时的符号问题，都是
  真实的发现；不要粉饰它们。
- **声称成功之前先跑测试。**没有展示测试输出，绝不说"已验证"。
- **给备选方案排序。**提出选项时，说明你会选哪个、为什么。
