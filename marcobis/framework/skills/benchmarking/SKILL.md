---
name: benchmarking
description: >
  适用于框架中任何估计方法的通用评价 skill。运行标准化的预测精度检验（与基准模型和已发表结果
  比较）、经济合理性检查，以及与匹配的参考实现对照的正确性验证。模型特定的拟合来自估计代码；本
  skill 评价它的产出。估计运行之后按需使用，检查流程和模型的预测表现；或者在准备论文时做正式的
  基准比较。用户说"基准比较""评价""测试一下模型""表现怎么样""比较预测"时触发。残差诊断的请求
  交给 diagnostics skill。
---

# 基准比较

## 设计原则

一个 skill，适用任何模型。本 skill 评价标准产出（脉冲响应、FEVD、预测），不含任何模型特定的
逻辑。某个方法不产出某项检查所需的输入时，跳过这项检查并说明原因。

预测基准比较对每个模型需要以下二者之一：完整的重新拟合与预测方法（给 `lib.rolling_forecasts` 的
`fit_fn`，任何调参都只在训练窗口内进行），或者匹配的样本外预测记录及其来源。模型特定的拟合由估计
代码提供。对于没有改动的拟合，使用它已有的诊断结果，不要重新计算。

## 两种模式

### 开发模式（快速检查）

估计运行之后几分钟内完成的通过 / 不通过检查。

### 论文模式（完整套件，用于发表）

完整的基准比较套件，用于达到发表水准的评价。准备投稿结果时使用。

---

## 开发模式

### 输入

```yaml
benchmark_request:
  mode: "development"
  results: 任何估计方法的输出（标准接口）
  data: 估计所用的数据集
  holdout_start: 日期（默认：样本最后 20%）
```

### 第 1 步：生成基准模型

用成熟的软件包，在同样的数据上自动生成以下基准：

| 基准 | 实现 | 用途 |
|----------|---------------|---------|
| 随机游走 | `statsmodels` 或简单平移 | 朴素基准；赢不了它是一个需要报告的发现 |
| 每个变量的 AR(1) | `statsmodels.tsa.ar_model.AutoReg` | 单变量基准 |
| 每个变量的 AR(p) | `statsmodels.tsa.ar_model.AutoReg`，用 BIC 选阶 | 更强的单变量基准 |
| 平坦先验 VAR(1) | `statsmodels.tsa.api.VAR` | 多变量下限 |
| 样本均值 | 简单计算 | 无条件基准 |

用最高效的软件包。agent 应使用现有的库，不要从头重写标准模型。

### 第 2 步：预测评价

用保留样本：

1. 只用训练样本估计模型。**整个流程都不得前视：**超参数、滞后阶数或任何其他需要调的量，都只能
   在训练窗口内选择（或在每个预测起点内重新调）。在全样本上调出来的"赢家"已经看过保留样本，
   它表面上的样本外优势是信息泄漏，不是能力。在报告中说明调参用的是哪个窗口。
2. 在期限 h = 1、4、8（季度）或 h = 1、6、12（月度）上做预测。
3. 计算被估计模型的产出和每个基准的 RMSFE，**在匹配的样本上**：每个参与比较的模型都在同样的
   有效（起点、期限、变量）单元上打分（`lib.forecast_score_matched` 负责这个匹配），这样某个模型
   一次拟合失败不会让比较换到不同的起点上。
4. 计算 RMSFE 比率：skill 产出 / 随机游走。小于 1.0 表示模型胜过随机游走。

**开发模式的标准：**

| 检查 | 类型 | 通过 | 未通过 |
|-------|------|------|------------|
| h=1 时相对随机游走的 RMSFE 比率 | 经验性（报告） | 至少一半变量 < 1.0 | 大多数变量 ≥ 1.0：标出并报告 |
| h=1 时相对 AR(1) 的 RMSFE 比率 | 经验性（报告） | < 1.1（与 AR 相差 10% 以内） | > 1.3（比 AR 差很多）：标出并报告 |
| 任何变量的 RMSFE = NaN 或 Inf | 流程（失败） | 没有 | 出现 |
| 预测方差 | 流程（失败） | 有限且合理 | 爆炸或为零 |

只有流程检查会让运行失败。赢不了随机游走或 AR 基准是需要报告的经验发现，不是估计出错的证据。

### 第 3 步：经济合理性检查

只用标准化的脉冲响应产出、与模型无关的检查：

| 检查 | 方法 | 通过 | 失败 |
|-------|--------|------|------|
| 稳定性 | 拟合诊断中的最大特征值模（`lib.diagnostics(...).stability`）；没有拟合时跳过 | 已报告，并按所声明的模型类别或复现标准分类（平稳 / 单位根 / 爆炸） | 存在未披露的爆炸根，或脉冲响应发散 |
| 脉冲响应收敛，暂时性冲击 | 最大期限上的响应 < 峰值响应的 10% | 是 | 否 |
| 脉冲响应收敛，永久性冲击（长期约束识别的冲击，或单位根系统中的水平响应） | 响应**趋于平稳**（最后约 8 期的变化相对峰值很小），而不是消失；在这里要求响应消失，会按构造否定正确的模型（例如 Blanchard-Quah 供给冲击对产出的响应） | 趋于平稳 | 在最大期限上仍有趋势 |
| 冲击当期的符号 | 与知识库中的预期符号对照（如有） | 一致 | 不一致：报告并调查，不算失败（见 specification skill） |
| 脉冲响应量级 | 峰值响应在该变量的合理范围内 | 合理 | 大得离谱或为零 |

在做收敛检查之前，先把每个冲击归为暂时性或永久性（识别方案会告诉你：长期 / 永久-暂时性方案会
指明哪些是永久性冲击；对平稳变换做的递归和符号方案，冲击是暂时性的）。

如果没有知识库（例如在新数据集上的第一次运行），跳过符号检查，只检查稳定性和收敛性。

### 第 4 步：正确性验证

如果有参考软件包（可配置），在参考软件包中用同样的设定估计同一个模型并比较。只有当参考实现与被
检查的模型使用相同的先验、估计量、识别方式和归一化时，才算数：

```yaml
reference_packages:
  var_ols:
    python: "statsmodels.tsa.api.VAR"     # 同样的 OLS 估计量和顺序
    r: "vars::VAR"
  bvar:
    python: null                          # 需要相同的先验和超参数；否则跳过
    r: "bvartools::bvar"                  # 仅限先验匹配时；后验模拟
  local_projections:
    python: "linearmodels"                # 或自写的 OLS 循环
    r: "lpirfs::lp_lin"
  sign_restrictions:
    python: null                          # 没有标准软件包；跳过
    r: "VARsignR"                         # 后验模拟
  tvp_var:
    python: null                          # 没有标准软件包；跳过
    r: "bvarsv"                           # 后验模拟
```

**比较指标。**对于确定性的估计量（顺序相同的 OLS VAR、OLS 局部投影），计算所有变量和期限上脉冲
响应点估计的最大绝对差。它应当接近数值精度；差得更多说明可能有实现错误。使用后验模拟的参考实现
（bvartools、VARsignR、bvarsv）需要匹配的算法、抽样次数和随机种子。对这些，比较后验中位数和区间
分位数，容差按各变量的单位和蒙特卡洛误差确定。

与经典 OLS VAR、随机游走或其他估计量不同的基准相比较，属于经验表现（第 2 步），不是正确性检查。

如果某个模型类别没有匹配的参考实现（例如 Python 中的符号约束 VAR），跳过这一步，只依靠合理性
检查。

### 第 5 步：报告

输出一份简洁的开发报告（示例；数字是假设的）：

```
============================================
DEVELOPMENT BENCHMARK REPORT
Model: BVAR (Minnesota prior)
Date: 2026-04-11
============================================

FORECAST ACCURACY (RMSFE ratio to random walk; empirical, reported)
          h=1     h=4     h=8
GDP       0.87    0.79    0.91    beats RW
CPI       0.94    0.85    0.88    beats RW
FFR       1.02    0.93    0.87    RW better at h=1
UNEMP     0.91    0.82    0.95    beats RW

SENSIBILITY
Stability:          PASS (max eigenvalue = 0.94)
IRF convergence:    PASS (all responses < 5% of peak at h=40)
Sign checks:        3/3 expected signs at impact (reported)

CORRECTNESS
Matched reference (same prior and hyperparameters): none   SKIPPED

OVERALL: PASS (pipeline and stability checks)
============================================
```

（报告可以用中文输出；上面保留英文是为了与代码输出一致。）

**如果有任何检查失败或被标出，**报告要突出它，并列出要检查的原因：

```
标记：所有变量在所有期限上相对随机游走的 RMSFE 比率都 > 1.0。
这是一个需要报告的经验发现。报告之前，检查是否有数据变换或预测对齐错误，以及先验是否过紧
（收缩到一个远离数据的先验均值）。如果都不是，就按原样报告结果。
```

---

## 论文模式

### 输入

```yaml
benchmark_request:
  mode: "paper"
  results: 任何估计方法的输出（标准接口）
  data: 估计所用的数据集
  holdout_start: 日期
  competitors: 竞争模型设定的列表（见下）
  specification_variants: 列表（用于跨设定比较）
```

### 第 1 步：完整的竞争模型集合

在开发模式的基准之上，加入可配置的外部竞争模型：

```yaml
competitors:
  # 始终包含（内部计算）
  internal:
    - random_walk
    - ar1
    - ar_bic
    - var1_flat
    - sample_mean

  # 可配置（需要额外的软件包或数据），例如：
  external:
    - name: "LASSO-VAR"
      implementation: "sklearn.linear_model.LassoCV on stacked VAR system"
      package: "scikit-learn"

  # 已发表结果（不需要计算，只做比较）
  published:
    - name: "GLP (2015)"
      source: "Giannone, Lenza, Primiceri (2015), Table 2"
      metric: "按系统规模给出的 MSFE 水平（BVAR 与平坦先验 VAR、因子模型、随机游走）；用同一行算出 RMSFE 比率 sqrt(MSFE_model / MSFE_RW)"
      notes: "适用于变量集合相近的美国数据"
```

**关键设计：竞争模型是数据，不是代码。**竞争模型列表在运行时提供（config.yaml 里没有固定的这一段）。
加一个新的竞争模型，就是在列表里加一项，而不是修改 benchmarking skill。

### 第 2 步：跨设定比较

接收一组设定变体，逐个估计并比较：

```yaml
specification_variants:
  - name: "Agent-specified"
    source: "framework output"
  - name: "Fixed textbook"
    specification: {variables: [...], lags: 4, prior: {lambda_1: 0.1, ...}}
  - name: "GLP-optimal"
    method: "在超参数网格上最大化边际似然（当这个变体参与样本外比较时，只在初始训练窗口内进行；
      全样本调参会泄漏评价期的观测）"
  - name: "Expert-specified"
    specification: {由用户提供}
  - name: "Cross-validated"
    method: "对 VAR 系数做带交叉验证的 ridge/LASSO"
```

每个变体都以相同方式估计和评价。benchmarking skill 不知道、也不关心设定是怎么确定的。它接收标准化
的产出并评价。

### 第 3 步：统计检验

对所有两两比较：

- **Diebold-Mariano 检验**（Diebold and Mariano, 1995），检验预测精度，使用 `lib.diebold_mariano`
  （Newey-West HAC 方差，带 Harvey、Leybourne、Newbold 1997 的小样本修正和 t(n-1) p 值）。
  调用者必须满足的要求（函数无法检查）：
  - **连续的预测起点。**HAC 截断（`horizon - 1`）和 HLN 因子假设损失序列的间隔等于一个预测期：
    滚动预测用 `step=1`，或者以起点间隔为单位传入期限。
  - **匹配的损失。**在相同的起点上配对两个模型的损失（先按起点合并再做差），绝不用两个各自删掉
    NaN 的数组。
  - **退化的差值会报错。**非零的*常数*损失差使检验无定义（一个模型以固定幅度占优）。直接报告损失；
    函数会报错，而不是返回 p = 1。
- **Giacomini-White 检验**（2006），检验条件预测能力。它不在 `scripts/lib/` 中；单独运行。
- 报告 p 值。使用 * p<0.10，** p<0.05，*** p<0.01 的惯例。

### 第 4 步：经济检查与预测精度并列

在一个不排序的表中，把经济检查放在预测表现旁边报告：稳定性分类（最大根）、脉冲响应是否平息、
当期和峰值符号、峰值量级，以及是否出现价格之谜。不要把预期符号、量级或没有价格之谜合成一个模型
质量分数，也不要按这样的分数给模型排序。出乎意料的结果要报告和调查，而不是扣分。

### 第 5 步：可用于论文的产出

生成：

1. **汇总表**（正文）：每个模型 / 设定一行，各列为每个期限的 RMSFE、经济检查（不排序）和 DM 检验
   结果。
2. **详细表格**（附录）：逐变量、逐期限的 RMSFE。
3. **RMSFE 柱状图**（正文）：按期限分组，按方法着色。

全部通过 results-presentation skill 以合适的风格生成。

---

## 接口

### 输入约定

benchmarking skill 接收任何估计方法的标准产出。不需要任何模型特定的字段。缺少某个字段时（例如 LP
没有 FEVD），跳过相应的评价。

### 输出约定

```yaml
benchmark_results:
  mode: "development" | "paper"
  model_evaluated: string
  forecast_accuracy:
    rmsfe: {variable -> {horizon -> value}}
    rmsfe_ratio_to_rw: {variable -> {horizon -> value}}
    lps: {variable -> {horizon -> value}} （仅论文模式）
    crps: {variable -> {horizon -> value}} （仅论文模式）
  baselines:
    {baseline_name -> {variable -> {horizon -> rmsfe}}}
  competitors: （仅论文模式）
    {competitor_name -> {variable -> {horizon -> rmsfe}}}
  statistical_tests: （仅论文模式）
    diebold_mariano: {pair -> {horizon -> {statistic, p_value}}}
  sensibility:
    stability: bool
    irf_convergence: bool
    sign_checks: {shock -> {variable -> match/mismatch}}
  correctness: （有匹配的参考实现时）
    max_irf_difference: float
    pass: bool
  overall_pass: bool （开发模式）
  charts: 文件路径列表（论文模式）
  summary_tables: 文件路径列表（论文模式）
```

---

## 添加新的竞争模型

要添加一个新的竞争模型，在运行时基准请求的 `competitors` 列表中加一项：

```yaml
- name: "My New Model"
  implementation: "怎样运行它的说明"
  package: "package_name"
```

benchmarking skill 用指定的软件包生成该竞争模型的预测，然后与所有其他竞争模型一样评价。不需要修改
benchmarking skill 本身。

如果竞争模型是已发表的结果（没有代码可运行），改为加到 `competitors.published`，并手工提供指标值。

## 参考文献

- Diebold, F.X. and Mariano, R.S. (1995). Comparing Predictive Accuracy. JBES.
- Harvey, D., Leybourne, S., Newbold, P. (1997). Testing the Equality of
  Prediction Mean Squared Errors. International Journal of Forecasting,
  13(2), 281-291.
- Giacomini, R. and White, H. (2006). Tests of Conditional Predictive Ability.
  Econometrica.
- Giannone, D., Lenza, M., Primiceri, G.E. (2015). Prior Selection for VARs. RESTAT.
- McCracken, M.W. and Ng, S. (2016). FRED-MD: A Monthly Database for
  Macroeconomic Research. Journal of Business & Economic Statistics.
