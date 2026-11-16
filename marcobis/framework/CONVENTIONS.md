# 框架约定

`scripts/lib/` 中所用**数学约定**的权威参考。从代码写出公式，或者把论文的数学翻译成库调用时，先查
这个文件。

测试固定了代码的行为（`tests/test_conventions.py`）；这个文件固定的是**如何用公式描述这些行为**，
以及在多种都说得通的约定之间，库选择了哪一种。

如果发现代码违反了这里列出的约定，那就是 bug：在你的副本中修复它。如果这里缺少某个约定或说得不清楚，
那是文档 bug，请补充这个文件。

---

## 1. 变量

### 传给 `fit_var` / `fit_minnesota_bvar` 等函数的 `data` 中的变量尺度

框架**对变量尺度不做约定**。你在 DataFrame 里放什么，VAR 看到的就是什么。常见选择：

| 选择 | 何时使用 | 脉冲响应的含义 |
|---|---|---|
| 水平值的自然对数（`np.log(GDP)`） | 产出、价格、指数的标准做法 | 对数单位的脉冲响应；乘以 100 得到百分比 |
| `100 * np.log(level)` | 与使用这种尺度的论文对照时 | 脉冲响应直接是百分比 |
| 原始水平（利率、比率） | 利率、利差、V/U 比率 | 水平单位的脉冲响应（例如利率的百分点） |
| 增长率 / 一阶差分 | 按构造保证平稳 | 增长率单位的脉冲响应 |

**命名约定**：列名应当表明所做的变换。例如：`log_real_gdp`、`us_1y_rate`、`gdp_yoy_growth`。拿不准
时，在复现的 config.yaml 中说明。国家统计局面板的列名和单位见各面板的 `series_info.csv`（例如
`cpi_yoy` 是"上年同月=100"的指数，`cpi_inflation` 才是百分比）。

### 公式中的 `Y_t` 是什么意思

根据代码写数学公式时：

- 如果代码的输入 `data` 是对数水平 → 公式中的 `Y_t` 就是对数水平。不要再取一次对数。
- 如果代码的输入是 `100*log` → `Y_t` 已经是百分比单位。差分 `Y_t - Y_{t-4}` 直接给出百分比通胀。
- 如果代码的输入是原始水平 → `Y_t` 是水平值，表示对数时必须明确写 `log Y_t`。

**常见错误**：$Y_t$ 在代码中已经是对数变量，却写成 $\log Y_t - \log Y_{t-4}$。要么去掉 $\log$，要么给
公式中的符号改名。

---

## 2. 期限约定

框架中有两类对象使用期限。它们**有意使用不同的下标约定**，因为数学上要求如此。

### 脉冲响应期限：`h = 0, 1, ..., H`（冲击当期为 `h=0`）

`IRFContainer.median` 的形状是 `(H+1, n_vars, n_shocks)`。第 0 行是当期响应（与冲击同期）。第 H 行
是 H 期之后的响应。

`lp_irf` 和 `lp_iv_irf` 使用同样的约定。

数学：
$$\text{IRF}_h = \Phi_h \cdot s, \qquad h = 0, 1, \ldots, H$$

其中 $\Phi_0 = I_n$，$\Phi_h = \sum_{j=1}^{\min(h,p)} B_j \Phi_{h-j}$。

### FEVD 期限：`H = 1, 2, ..., H_max`（不报告 `H=0`）

给 `lib.structural_fevd` 或 `lib.generalised_fevd` 传一个数 `horizon=H`，指的是**向前 H 步的预测误差
方差**，它是 **H 项**之和（**不是** H+1 项）：

$$\text{FEV}_k(H) = \sum_{j=0}^{H-1} (\Phi_j \Sigma_u \Phi_j^\top)_{kk}$$

$$\text{FEVD}_{k, j}(H) = \frac{\sum_{s=0}^{H-1} (\Phi_s s_j)_k^2}{\text{FEV}_k(H)}$$

所以对季度数据，`horizon=8` = 向前 2 年的 FEV = 8 项之和。

**常见错误**：对 `j=0..H` 求和，而不是 `j=0..H-1`，得到 `H+1` 项。用 `lib.structural_fevd`，不要
自己写。测试固定了这一点：`tests/test_conventions.py::test_fevd_horizon_off_by_one_regression`。

### 预测期限：`h = 1, 2, ..., H`（`h=1` = 向前一步）

`lib.iterated_forecast` 和 `lib.conditional_forecast` 返回的预测从 `h=1`（最后一个观测之后的下一期）
开始。

---

## 3. 简约式拟合约定

### `B_hat` 的行 / 列布局（`lib.fit_var`）

`B_hat` 是一个 `(k, n)` 矩阵，其中 `n` 是内生变量个数，`k` 取决于确定性项 + 外生变量块：

```
B_hat 的行布局（从上到下）：
  第 0 .. n*p - 1 行           滞后系数（lag1_var1, lag1_var2, ..., lagp_varn）
  第 n*p 行                    常数项        （若 trend 属于 {"c", "ct"}）
  第 n*p + 1 行                线性趋势      （若 trend == "ct"）
  第 n*p + (c+d) .. 行         外生变量块    （若提供了 exog）
                               其中 c=0/1、d=0/1 取决于 trend
```

访问方法：

- `fit.lag_matrices()` → `p` 个矩阵的列表，每个 `(n, n)`。取第 `0..n*p` 行并重排 / 转置。
- `fit.B_hat[n*p, :]` → 常数项（trend 为 `"c"`/`"ct"`）。
- `fit.B_hat[n*p+1, :]` → 趋势项（trend 为 `"ct"`）。`[-1]`/`[-2]` 这样的简写只在没有外生回归元时
  成立。
- `fit.exog_coefs()` → 外生变量块（只在 `has_exog=True` 时）。

**趋势约定**：`X_act` 中趋势列的取值是 `1, 2, ..., T_eff`，其中 `T_eff = T - p`（这是本库的约定；
statsmodels 和 JMulTi 用 `p+1, ..., T`，只是截距的重新参数化：`const_here = const_sm + p·slope`）。

### `Sigma_u` 的除数

`fit.Sigma_u` 用自由度调整后的除数计算（不是未做偏差修正的 `1/T_eff`），并且不同路径的约定不同：

- **通过 statsmodels 的普通 VAR 拟合**：除数是 `T_eff - k`，其中 `k` 是**每个方程的回归元个数**
  （= `lags*n + constant + trend`）。这是 Lütkepohl 2005 §3.2.2 的小样本修正。算例：T=200、n=2、
  p=2、trend="c" 时，T_eff=198，k=5，除数=193（不是 196）。
- **VARX 拟合（提供了 `exog` 时）**：除数是 `T_eff`（纯 ML 估计量，没有 Bessel 修正）。与普通路径
  的差异在 `fit_var` 的 docstring 中有说明。
- **面板估计量**（`lib.panel.fit_*_var`）：四个估计量（`fit_pooled_var`、`fit_mean_group`、
  `fit_partial_pooling_var`、`fit_global_var`）都使用 ML 除数（1/T）。`fit_mean_group` 在平均之前把
  每个单位 `fit_var` 的 Lütkepohl Sigma_u 换算成 ML，这样各面板估计量的残差协方差处于同一尺度。

**对手推公式的含义**：一般而言 `Sigma_u != cov(u, ddof=1)`。比值
`Sigma_u / cov(u, ddof=1) = (T_eff - 1) / (T_eff - k)` 约为 1 + (k-1)/T_eff，在 T=200、k=5 时约 2%。
如果需要特定的尺度，直接从残差计算。

---

## 4. 结构识别约定

### Cholesky（`lib.cholesky_impact`、`lib.cholesky_irf`）

`cholesky_impact(Sigma_u)` 返回**下三角** Cholesky 因子 `L`，使得 `L @ L.T = Sigma_u`。按约定，
对角元素为正。

顺序 = `data` DataFrame 中的变量顺序。冲击 `j` 对排在它之前的变量（`0..j-1`）没有当期影响；变量 `j`
及其后的变量可以在当期响应。

**渐近蒙特卡洛区间抽样（包含 Σ 的不确定性）**：`VARFit.parameter_draws` 在抽取 ``B`` 的同时，从一个
以点估计为中心的逆 Wishart 分布中抽取 ``Sigma``（``scale = (T-k-n-1) Sigma_hat, df = T-k``，使得
``E[Sigma_draw] = Sigma_hat`` 精确成立）。这是有意把教科书中平坦先验的后验 ``IW(U'U, T-k)`` 重新
居中，后者的均值比 ``Sigma_hat`` 高出 ``(T-k)/(T-k-n-1)``，差距为 O((n+1)/T)。对 Σ 抽样会把它的
不确定性通过 ``L = chol(Sigma)`` 传递出去，使渐近蒙特卡洛区间达到名义的频率学派覆盖率
（`tests/test_coverage.py::TestCholeskyAsymptoticMCCoverage`）。

要固定 Σ：``fit.parameter_draws(..., include_sigma_uncertainty=False)``。

### Proxy-SVAR（`lib.proxy_svar_irf`）

三种归一化（第三种 `normalization="reliability"` 用于单个工具变量；见 `proxy_svar_irf` 的 docstring）：

**`normalization="unit_policy"`**：

$$s_p = 1, \qquad s_k = \frac{\Sigma_{uz, k}}{\Sigma_{uz, p}}$$

其中 $\Sigma_{uz, k} = \tfrac{1}{T_{\text{eff}}} \sum_t u_{t,k} z_t$（代码中是
`(u * z[:, None]).mean(axis=0)`）。

**`normalization="one_sd"`**：

$$s_p = \text{np.std}(u_p, \text{ddof}=1), \qquad s_k = s_p \cdot \frac{\Sigma_{uz, k}}{\Sigma_{uz, p}}$$

**ddof=1 这个细节**：库使用带 Bessel 修正的样本标准差（`np.std(..., ddof=1)`），**不是**
`sqrt(Sigma_u[p, p])`。两者相差约 `sqrt(T_eff / (T_eff - k_ar))`，很小，但在短样本中不为零。由
`test_one_sd_normalisation_h0_policy_equals_std_u_policy` 固定。

**只在子样本上观测到的工具变量**：`lib.proxy_svar_irf` 保留完整的残差样本，把未观测到工具变量的时期
填零（当期比率对填充方式不变；见 docstring 中关于 NaN 语义的说明）。有些其他实现则截取到共同样本
并在其中去均值。在 Gertler-Karadi (2015) 的数据上，两种约定的当期比率相差 2.1e-2，GK 脚注 4 的
可靠性尺度相差约 26%（相对值）。第一阶段 F 统计量只使用观测到工具变量的时期（在
`tests/test_identification.py` 中做了回归测试）。

**工具变量的均值**：交叉协方差 `(residuals * z[:, None]).mean(axis=0)` 是样本乘积除以 `T_eff`。在
`fit_var(trend="c")` 下，OLS 残差均值为零，所以无论 `z` 均值是否为零，它都等于 `Cov(u, z)`（高频
FOMC 意外按构造均值为零；叙事冲击通常也是）。有些其他实现把残差对 `[1, z]` 回归；在 `trend="c"`
下结果等价。如果用 `trend="n"` 拟合并传入均值不为零的工具变量，先把工具变量中心化，避免虚假相关。

### 符号约束（`lib.sign_restricted_irf`）

QR 旋转，带对角符号归一化：`Q = Q_raw @ diag(sign(diag(R)))`。

**单冲击模式**（`sign_restrictions` 中只有一个键）：只检查 Haar 旋转的第 0 列（允许翻转符号）。这是
标准的 Uhlig (2005) 接受 / 拒绝，因为 Haar 分布的 `Q` 的第一列在单位球面上均匀分布。这样是在均匀
条件测度下对识别集合抽样，而这一测度**本身就是**所报告对象的一部分（Baumeister-Hamilton 2015）。
`column_scan=True` 则扫描全部 `n` 列，接受第一个匹配的列。它在旋转上更高效，但引入了一个非标准的
测度（后面的列是在前面的列失败的条件下被接受的；KS 检验可以区分，区间边界会移动几个百分点）。

**多冲击模式**（多个键；Rubio-Ramirez-Waggoner-Zha 2010）：**固定**分配：冲击 `j` 对照 `Q` 的第 `j` 列
检查，每列允许翻转符号。Haar 的列是可交换的，所以固定分配在分布上不失一般性，接受与否也不取决于冲击
列出的顺序。

**残差 bootstrap**（`bands="residual_bootstrap"`）：重抽样的残差乘以 `sqrt(T/(T-k))` 重新缩放
（Stine 1987），bootstrap 的 Sigma 使用与点估计相同的 `T-k` 除数，因此 bootstrap 抽样以点估计的
脉冲响应为中心。

约束类型和元数据标签：

| 生效的约束 | `metadata["identification"]` |
|---|---|
| 仅符号 | `"sign_restrictions"` |
| 符号 + 叙事 | `"narrative_sign_restrictions"` |
| 符号 + FEV 份额 | `"sign_fev_share_restrictions"` |
| 三者都有 | `"narrative_sign_fev_share_restrictions"` |

### 零 + 符号约束（`lib.zero_sign_restricted_irf`）

Arias、Rubio-Ramírez & Waggoner (2018)：对结构当期矩阵同时施加零约束**和**符号约束。实现了算法 2
（简化为当期零约束，h=0）。

**算法**：逐列构造旋转 `Q`。对冲击 j，列 `Q[:, j]` 必须位于以下两者的公共零空间中：

1. ``Z_j = （P = chol(Σ_u) 中与冲击 j 的零约束变量对应的行）``，使得对每个受约束的 `v`，
   `(P Q[:, j])[v] = 0`。
2. ``Q[:, 1..j-1]'``（与已放好的列正交）。

从这个公共零空间中抽取一个随机向量，归一化后作为 `Q[:, j]`。所有列放好之后，用标准的列翻转逻辑在
`A_0 = P Q` 上检查符号约束。

**关键不变量**：零约束由算法保证，而不是统计上近似成立。被接受的脉冲响应对
`zero_restrictions[shock_j]` 中的每个 (v, j) 都精确满足 `IRF[0, v, j] == 0`。由
``tests/test_conventions.py::TestZeroSignRestrictionConventions`` 固定。

**范围**：只支持 `horizon=0` 的零约束（当期）。没有实现 ARRW 2018 的多期限约束。

**向后兼容**：`zero_restrictions=None`（或为空）时逐字节等同地委托给 `sign_restricted_irf`。零约束
生效时 `identification` 元数据标签为 `"zero_sign_restrictions"`，否则为 `"sign_restrictions"`。

### 长期约束（`lib.long_run_irf`）

Blanchard-Quah 1989：结构当期矩阵 `S` 使得长期矩阵 `(I - B(1))^{-1} S` 为下三角。永久性冲击排在前面。

### 异方差（`lib.heteroskedasticity_irf`）

Rigobon 2003。假设两个制度的方差比；结构冲击由跨制度的协方差差异识别。

**归一化**：广义特征分解把冲击协方差固定为排序后**第二个**制度标签中的单位阵（例如自带复现中的
衰退期）。所有报告的脉冲响应都是对"制度 2 中一个标准差"冲击的响应，列按照 scipy 的特征值升序排列，
这在经济上是任意的（用 `sign_normalization` 固定符号）。

### 集合识别和弱识别模型的推断注意事项

下面是对上述方法所报告推断的标准的、已发表的批评。它们是*方法本身已记录的局限*，不是实现上的 bug；
每一条在相应的 docstring 中也有说明。

1. **跨旋转的逐点分位数不是一个模型（Fry-Pagan 2011, JEL）。**`sign_restricted_irf` /
   `zero_sign_restricted_irf` 的区间是跨抽样的逐点分位数；逐点中位数一般不是*任何*一个被接受旋转的
   脉冲响应，把各期限 / 各变量的逐点中位数连起来，混合了不同的旋转。把区间报告为可接受集合的概括，
   而不是"模型的"响应。库**实现了** Fry-Pagan 中位数目标旋转：`lib.fry_pagan_median_target(draws)`
   选出最接近逐点中位数的那一个被接受旋转（按标准化的单元格），`sign_restricted_irf` 和
   `zero_sign_restricted_irf` 会自动把它附在 `metadata["median_target"]`（可 JSON 序列化；`irf`
   为嵌套列表）。需要一个自洽的单一模型响应时，把它与逐点区间一起报告。

2. **均匀 Haar 旋转先验是有信息的（Baumeister-Hamilton 2015, ECMA）。**"不预设立场"的符号约束仍然
   通过对 Q 的均匀抽样，在识别集合上施加了一个不平凡的先验；随着 T 增大，后验区间**不会**收缩到识别
   集合。依赖区间边界的结论继承了这个先验。

3. **零 + 符号抽样没有加权（ARRW 2018，算法 3）。**以零约束为条件抽取 Q（算法 2，即所实现的）会在
   识别集合上诱导出一个非均匀的密度；**没有**应用 ARRW 的重要性权重（他们算法 3 的体积元），所以跨
   抽样的分位数是相对于条件抽样测度的，而不是相对于条件上不预设立场的先验。一个后果是：零约束个数
   相同的冲击按调用者列出的顺序抽取，而这个顺序会改变所报告的分布。一个变量可以对同一冲击同时有当期
   零约束和符号约束；这时符号约束从第 1 期开始生效。

4. **叙事约束用的是拒绝抽样，不是 ADRR 的重要性抽样。**违反叙事约束的抽样被丢弃，剩下的等权；ADRR
   (2018, p. 2812) 指出这不是他们的算法 1（后者按叙事成立概率的倒数重新加权）。在 ADRR 复现的 README
   中有说明。贡献约束针对一个日期，默认针对从样本开始以来的累计贡献。论文的例子约束的是一期的意外
   变动（`contribution="unexpected"`），在其货币政策应用中使用 `overwhelming` 标准。不支持多期窗口。

5. **长期识别是脆弱的（Faust-Leeper 1997, JBES）。**`C(1)` 是零频率对象，估计精度趋于零；近单位根
   动态使 BQ 式的结论对低频设定很敏感。此外，`(I - ΣA)` 奇异的区间抽样会被跳过，这截掉了最具爆炸性
   （最宽）的抽样。

6. **Rigobon 区间不包含识别不确定性。**区间循环把旋转 `H` 固定在点估计（只有 VAR 系数变化）；制度
   协方差中的抽样误差（往往是主要的不确定性）**没有**反映出来。弱识别标记是一个启发式的特征值间隔
   阈值，不是正式检验（Lütkepohl-Netšunajev 2017；Lewis 2021）。

### 贝叶斯局部投影（`lib.blp_irf`）

Ferreira、Miranda-Agrippino & Ricco（2025, REStat 107(5)；2021 年工作论文的设计）。把每个期限的 LP
系数向该期限的迭代 VAR 脉冲响应收缩，收缩强度为 λ。

**凸组合形式**（在先验精度等于数据精度的自然共轭先验缩放下，简化的 BLP）：

```
β^BLP_{h, j} = (β^OLS_{h, j} + λ · β^VAR_{h, j}) / (1 + λ)
σ^BLP_{h, j} = σ^OLS_{h, j} / √(1 + λ)
```

* `β^OLS_{h, j}`：期限 h、响应变量 j 的频率学派 LP 系数（通过现有基于 HAC 的 `lp_irf` 流程得到）。
* `β^VAR_{h, j}`：变量 j 在期限 h 的迭代 VAR 脉冲响应，以 h=0 的 OLS LP 作为结构当期载荷。由一个
  基准 VAR(`var_lags`) 拟合构造。
* `λ`：`shrinkage` 参数。λ=0 → 纯 OLS LP；λ=1 → 等权；λ=∞ → 纯 VAR。

**算法不变量**（由 `tests/test_conventions.py::TestBLPConventions` 固定）：

* λ=0 时，BLP 的点估计和区间与 `lp_irf` 逐字节相同。
* h=0 时，BLP 系数不随 λ 变化，因为 h=0 的先验均值**就是** h=0 的 OLS LP 系数（构造 VAR 先验所用的
  当期载荷）。
* 区间在每个期限上都精确收缩 `1/√(1+λ)`。

**识别标签**：`"bayesian_lp"`；方法标签：`"bayesian_local_projections"`。

**范围**：这个实现只处理冲击系数。完整的 MAR 2021 框架还允许对控制变量系数施加 Minnesota 式先验；
这一部分没有实现。冲击系数的收缩已经体现了 BLP 的主要优势（降低长期限上 LP 的方差）。

### 状态依存局部投影（`lib.state_dependent_lp_irf`）

Auerbach-Gorodnichenko 2012 / Ramey-Zubairy 2018。两制度 LP，允许冲击效应在不同制度间不同。

每个期限 h、响应变量 j 的估计方程：

```
y_{j, t+h} = α^E_h + (α^R_h − α^E_h) · F_t
           + β^E_{jh} · s_t + (β^R_{jh} − β^E_{jh}) · F_t · s_t
           + γ_h^T Z_{t−1:t−p} + δ_h^T F_t · Z_{t−1:t−p} + u_{j, t+h}
```

其中 `s_t` 是冲击，`F_t ∈ [0, 1]` 是状态权重（1 = 衰退，0 = 扩张）。截距依制度而定（扩张期为
`α^E_h`，衰退期为 `α^R_h`）；实现中把 `F_t` 作为单独的回归元，使常数项随制度移动。

* **二元状态**（NBER 虚拟变量、Harding-Pagan 虚拟变量）：`F_t ∈ {0, 1}`
* **连续状态**（平滑转换 logistic，AG 2012）：`F_t ∈ [0, 1]`

同一套机制处理两者。

`interact_controls=True`（默认）包含 `F_t · Z_{t−1:t−p}`，即 Ramey-Zubairy 2018 的"饱和"设定，
允许依制度而定的动态。`interact_controls=False` 省略这些交互项；冲击系数仍与制度交互，但制度只通过
当期冲击渠道影响条件均值。

**返回容器的形状**：`(H+1, n_response, 2)`，最后一维是 `(expansion, recession)`。`shock_names` 为
`[f"{shock_name}_{state_names[0]}", f"{shock_name}_{state_names[1]}"]`，默认
`("expansion", "recession")`。

**衰退期标准误公式**：
`Var(β^R) = Var(β^E) + Var(β^R − β^E) + 2 · Cov(β^E, β^R − β^E)`，其中协方差取自回归系数的联合 HAC
协方差矩阵。有限样本 HAC 产生的微小负方差在区间中替换为 NaN。

`metadata["identification"]` 是字面量 `"state_dependent_lp"`；`metadata["state_mean"]` 报告 `F` 的
样本均值。

### 全局 / 面板 VAR 约定（`lib.fit_global_var`）

把各单位的面板堆叠成一个有 `N = n_units * n_vars_per_unit` 个内生变量的 VAR，堆叠后的变量名为
`"{unit}_{var}"`，列顺序为 `(u_0_v_0, u_0_v_1, ..., u_0_v_K-1, u_1_v_0, ...)`：单位在外层，变量在
内层。

Minnesota 收缩，对 `B_{ij}^{(p'), kl}`（单位 `j` 的变量 `l` 在滞后 `p'` 时对单位 `i` 的变量 `k` 的
影响）采用四种区块结构：

| 区块 | λ_eff |
|---|---|
| 本单位，本变量（i=j, k=l） | λ₁ |
| 本单位，交叉变量（i=j, k≠l） | λ₁ · λ₂ |
| 交叉单位，本变量（i≠j, k=l） | λ₁ · λ_cross_unit |
| 交叉单位，交叉变量（i≠j, k≠l） | λ₁ · λ₂ · λ_cross_unit |

滞后衰减：每个先验标准差都除以 `(p')^λ₃`。
方差缩放：每个区块的先验标准差乘以 `σ_eq / σ_col`，其中 σ 是预样本 AR(p) 残差的标准差（Sims-Zha /
BGR 约定）。

先验均值：本单位本变量的 1 阶滞后为随机游走（`B_{ii}^{(1), kk} = 1`），其他为零。

`lambda_cross_unit = 0` 使交叉单位区块精确为零（由
`tests/test_panel.py::TestGlobalVAR::test_recovers_block_diagonal_when_cross_unit_zero` 固定）。

逐区块访问：`fit.cross_unit_lag_block(unit_to, unit_from, lag)` 返回 K×K 子块。汇总统计量
`fit.average_cross_unit_spillover(lag)` 返回在指定滞后上交叉区块的平均 Frobenius 范数与本单位区块的
平均 Frobenius 范数之比（0 = 没有溢出；1 = 交叉区块与本单位区块一样大）。

拟合是 `VARFit` 的子类，提供一个 N 变量 VAR(p) 的接口，所以所有识别函数（`cholesky_irf`、
`sign_restricted_irf`、`proxy_svar_irf`）都可以直接用于堆叠系统。

### 非高斯 SVAR（`lib.nongaussian_svar_irf`）

Lanne-Meitz-Saikkonen 2017。利用结构冲击的非高斯性，在列置换和符号之外识别 `u_t = B ε_t` 中的结构
矩阵 `B`。

算法：

1. **预白化**残差：`Z = L^{-1} u`，`L = chol(Σ_u)`。
2. **找一个正交矩阵 Q**，使得 `ε_t = Q^⊤ z_t` 近似独立（且非高斯性最大）。两种方法：

   * `method="fastica"`：Hyvärinen (1999) 对称（并行）FastICA 不动点算法。与分布无关。返回解混矩阵
     `W = Q^⊤`。`ica_method` 元数据标签：`"fastica"`。
   * `method="pml_t"`：LMS 第 3 节的参数伪 MLE，假设每个结构冲击是独立同分布的标准化 Student-t，
     每个冲击有自己的自由度 `ν_j`。在正交矩阵的 Givens 角参数化上，用 L-BFGS-B 联合优化 `(Q, ν)`。
     从 FastICA 的解热启动，另加 `pml_t_n_restarts` 次随机重启；似然最高的结果胜出。`ica_method`
     元数据标签：`"pml_t"`。

3. **还原** `B = L Q`（注意转置：对 FastICA，`Q = W^⊤`；对 pml_t，直接返回 `Q`）。

两种方法的识别类别标签都是 `"nongaussian_svar"`。`ica_method` 元数据字段区分实际运行的内部算法。

单位方差缩放下的标准化 Student-t 密度（`method="pml_t"` 使用）：

$$f(x; \nu) = \frac{1}{\sigma} \cdot t_\nu\!\left(\frac{x}{\sigma}\right), \qquad \sigma = \sqrt{\frac{\nu - 2}{\nu}}$$

要求 `ν > 2`（方差有限）。优化器通过 `log(ν − 2)` 参数化 `ν`，使无约束优化器满足这个界。

返回的诊断：

* `jarque_bera`：每个冲击的 JB 统计量 + p 值
* `skewness`、`excess_kurtosis`：每个冲击的样本矩（Fisher 形式）
* `n_gaussian_like`：JB p > 0.10 的冲击个数
* `weak_nongaussianity`：若 `n_gaussian_like >= 2` 则为 True（LMS 最多允许一个高斯成分；不拒绝只是
  有限样本证据，不是证明）。同时报告 `max_jb_pvalue`。
* `fastica_converged`、`fastica_n_iter`、`fastica_final_diff`（总会填写，因为即使用 `pml_t`，
  FastICA 也是热启动）
* 当 `method == "pml_t"` 时另有：`pml_t_log_likelihood`、`pml_t_nu`（每个冲击的 ν 估计）、
  `pml_t_converged`、`pml_t_n_restarts_tried`、`pml_t_best_restart_index`

`weak_nongaussianity` 标记是主要的检查。在近高斯的数据上 LMS 识别会失败，而悄无声息的不可靠是最坏的
情形。相信 LMS 的输出之前一定先检查它。

### 符号约束 + 高阶矩（AFM 2023）

Andrade-Ferroni-Melosi 2023 在符号约束 SVAR 的基础上，对所隐含结构冲击序列的高阶矩施加不等式约束。
作为 `lib.sign_restricted_irf` 的参数 `higher_moment_restrictions` 加入；它可以与
`narrative_restrictions`（ADRR 2018）和 `fev_share_restrictions` 干净地组合。

**约束结构**（单条）：

```python
# 阈值（单冲击模式，或多冲击模式中按冲击）：
{"moment": "skewness" | "excess_kurtosis",
 "lower": float, "upper": float,   # 都是可选的，默认 -inf / +inf
 "abs": bool,                       # 为 True 时对 |moment| 施加界
 "shock": "name"}                   # 多冲击模式下必需

# 冲击之间的比较（仅多冲击模式）：
{"shock": "a", "moment": "...",
 "vs": "b", "comparison": "greater" | "less",
 "margin": float}                   # 可选，默认 0.0；严格的差距
```

**矩的名称**：

* `"skewness"`：`scipy.stats.skew(bias=False)`，调整后的 Fisher-Pearson 估计量（G1）。
* `"excess_kurtosis"`：`scipy.stats.kurtosis(fisher=True, bias=False)`，**Fisher 形式**（超额峰度 =
  峰度 − 3），**bias=False**（调整后的估计量 G2）。高斯冲击的 `excess_kurtosis = 0`。尖峰 = 正值。

  **与 MATLAB 的比较**：MATLAB 的 `kurtosis(x,0)` 是偏差修正后的 Pearson 峰度，等于 SciPy 的
  `kurtosis(x, fisher=False, bias=False)`；减去 3 才能与我们的超额峰度比较。MATLAB 默认的
  `kurtosis(x)`（标志 1）是有偏的矩估计量（SciPy 的 `bias=True`）。

**实现**：对于候选列 `Q[:, c]`，所隐含的结构冲击是 `ε_t = u_t^⊤ (P^{-⊤} Q[:, c])`，其中
`P = chol(Σ_d)`。这与叙事约束使用的投影相同，这里复用。

**识别标签**：增加 `"higher_moment"` 部分（例如 `"sign_higher_moment_restrictions"` 或
`"multi_shock_sign_higher_moment_restrictions"`）。

**默认值的固定**：
`tests/test_conventions.py::TestAFMHigherMomentConventions::test_none_is_byte_identical_to_baseline`
锁定 `higher_moment_restrictions=None` 与不传这个参数逐字节相同。

---

## 4b. BVAR（Minnesota）先验约定

`lib.MinnesotaPrior` 遵循 Sims-Zha (1998) / Bańbura-Giannone-Reichlin (2010) 的约定，通过与实际数据
堆叠在一起的虚拟观测编码（Theil 混合估计）。

### 超参数的方向

| 参数 | 取值越小表示 | 效果 |
|---|---|---|
| `lambda_1`（总体紧度） | 向先验均值的收缩**越紧** | 后验更接近随机游走先验；数据影响更小 |
| `lambda_2`（交叉变量紧度） | 交叉变量收缩**越紧** | 非对角的滞后系数被拉向 0（仅非对称模式） |
| `lambda_3`（滞后衰减） | 跨滞后的衰减越慢 | 较远的滞后收缩得不那么激进 |
| `lambda_4`（常数项紧度） | 截距的先验**越紧** | 较少调整；默认 100 = 近乎平坦 |
| `mu`（系数和） | SOC 先验越弱；`mu=0` 关闭 | `mu` 越大，越强制类似随机游走的"自身滞后之和"行为 |
| `delta`（虚拟初始观测） | 单一单位根先验越弱；`delta=0` 关闭 | `delta` 越大，共同趋势先验越强 |

### `lambda_2` 依模式而定（关键）

在**默认的对称** BGR (2010) 形式下（`asymmetric=False`）：

  先验协方差具有 Kronecker 结构 $\Sigma \otimes V_0$，其中 $V_0 = (X_d'X_d)^{-1}$ 是所有方程共享的
  回归元协方差因子（它的逆是先验精度）。这种结构**无法**在同一方程内对自身滞后与交叉变量系数编码
  不同的收缩。所以在对称模式下 `lambda_2` 是**悄无声息的无效参数**。

  由 `tests/test_conventions.py::test_lambda_2_no_op_under_symmetric_mode` 固定。

在**非对称**的 Litterman (1986) / Sims-Zha (1998) 形式下（`asymmetric=True`）：

  拟合变成逐方程的 Ridge 回归，每个方程有自己的精度矩阵。`lambda_2` 确实会缩放交叉变量系数的先验。
  `lambda_2` 越小 → 交叉变量收缩越紧 → 非对角元素被拉向 0。

  由 `tests/test_conventions.py::test_lambda_2_has_effect_under_asymmetric_mode` 固定。

非对称模式的取舍：

* `Sigma_u` 被视为固定的代入值（来自逐方程拟合的残差协方差），**不**从逆 Wishart 后验中抽取。
* 非对称模式下的 `BVARFit.parameter_draws` 在 `Sigma_u` 保持不变的情况下，从逐方程的高斯后验中抽取
  beta。
* 非对称模式下 `lib.log_marginal_data_density` 抛出 `NotImplementedError`（没有闭式 MDD）。

### 虚拟观测的个数 = 哪些子先验生效的信号

`fit.n_dummies` 报告堆叠在数据上方的虚拟行数。组成（对 $n$ 变量、$p$ 阶滞后的 VAR）：

  * $n \cdot p$ 行用于自身滞后紧度（`lambda_1`、`lambda_3`；始终生效）。
  * $n$ 行用于 Sigma 先验（`Yd = diag(σ)`，`Xd = 0`），在对称 / 共轭形式中；`asymmetric=True` 时没有。
  * 若 `trend="c"`，1 行用于常数项紧度（`lambda_4`）。
  * 系数和先验：`rw_deltas` 中每个非零元素对应一行（默认 $n$ 行），仅当 `mu > 0`。
  * 1 行用于虚拟初始观测先验，仅当 `delta > 0`。

由 `test_mu_zero_disables_sum_of_coefficients_dummies` 和
`test_delta_zero_disables_dummy_initial_observation` 固定。

### `rw_deltas` = 自身 1 阶滞后系数的先验均值

默认 `[1, 1, ..., 1]` = 每个变量都是随机游走先验。对于你认为是 I(0) / 围绕均值的白噪声的变量（例如
失业缺口、产出缺口），设为 0。混合的 `[1, 1, 0]` 也可以（逐变量设置）。

系数和行按 `rw_deltas` 缩放（BGR 2010），所以设为 0 的变量没有系数和行。虚拟初始观测行不受影响。

### 边际似然与滞后长度

`lib.log_marginal_data_density` 在同样的数据和滞后长度下，可以在不同超参数之间比较。当各拟合使用
同一个数据框时，它**不能**在不同滞后长度之间比较：`lags=p` 的拟合解释的是从第 `p + 1` 期开始的观测，
所以每个滞后长度解释的行不同，比较会偏向最长的滞后。要比较滞后长度，去掉前面的行，使每个拟合解释
同样的观测（最大滞后为 `P` 时，传 `data.iloc[P - p:]`）。

### `obs_scale`（GLS 逐观测方差缩放），Lenza-Primiceri 2022

加入 `obs_scale=s_t`（长度 `T - lags`）会在与 Minnesota 虚拟观测堆叠之前，把 `(Y_act, X_act)` 的
各行预先乘以 `1/s_t`。虚拟观测保持原来的权重；`s_t` 大的观测对后验的贡献更小。`obs_scale=None`
（默认）与不缩放的拟合逐字节相同。用于疫情时期的方差缩放。

---

## 4c. TVP-VAR 先验约定（`lib.fit_tvp_var`）

Primiceri (2005) 的 TVP-VAR 对以下各项施加独立的先验：

* **β_0**（初始期 VAR 系数）：
  $\beta_0 \sim N(\beta_{OLS}^{train}, 4 \cdot V_{OLS}^{train})$，其中
  $V_{OLS}^{train} = \Sigma_{OLS}^{train} \otimes (X^\top X)^{-1}$ 来自训练样本的 OLS。系数 4 是
  Primiceri 对 β_0 更宽松的先验。

* **Q**（β_t 随机游走漂移的协方差）：
  $Q \sim IW\big(k_Q^2 \cdot \tau \cdot V_{OLS}^{train}, \tau\big)$，其中 $\tau$ = `training_sample`，
  $k_Q^2$ = `Q_prior_scale`（**默认 1e-4**，即 Primiceri 的 $k_Q = 0.01$ 的*平方*，p. 831）。

  两个被固定的约定（`tests/test_conventions.py::TestTVPPriorConventions`）：

  1. IW 的尺度**乘以** $\tau$，而不是除以（Primiceri 2005 附录 C）。
  2. 尺度使用 $V_{OLS}^{train}$，**不是** β_0 的先验协方差 $4 V_{OLS}$。系数 4 只属于 β_0 的先验。

* **Σ**（不变的残差协方差）：IW，`df = Sigma_prior_df`（默认 `n+2`，刚好是正常先验），
  尺度 = `Sigma_OLS_train * df`。

对于随机波动扩展（`fit_tvp_var_sv`、`fit_tvp_var_sv_primiceri`），使用同样的 Q 先验校准。其他先验
不遵循论文：

* 对数波动率的新息：每个方差为 IG(3, 0.01)（均值 0.005），不按训练样本缩放；
* 首期对数波动率：N(0, 10)；
* 协方差状态（仅 `fit_tvp_var_sv_primiceri`）：IW(`S_prior_scale` · τ · I, τ)，`S_prior_scale` 默认
  1e-4。论文按训练样本 OLS 协方差系数的方差缩放这个先验。这里的尺度是一个固定数，所以要检查它是否适合
  数据的单位：取值 0.01 时，即使在协方差不变的数据上，协方差状态也会出现明显的漂移。

另外三个约定：

* 训练样本被用了两次，一次在先验中，一次在估计样本中（论文把它从估计中去掉），所以报告全部
  `T - lags` 个日期的路径；
* 波动率抽样器中 `log(y² + c)` 里的常数是 1e-6（论文用 0.001）。当残差的绝对规模很小（标准差接近
  0.001 或更小）时，波动率估计会被压平，所以数据要用百分比表示；
* 混合指示变量在系数块和协方差块之后、波动率之前抽取，这是 Del Negro and Primiceri (2015) 修正中的
  顺序。

---

## 5. Bootstrap 约定

### Wild bootstrap（`lib.proxy_svar_irf` 默认）

每期独立同分布的 Rademacher 权重 $\omega_t \in \{-1, +1\}$：

$$u_t^* = \omega_t \hat u_t, \qquad z_t^* = \omega_t z_t$$

同一个 $\omega_t$ 同时乘以残差和工具变量（在一次抽样内保持 proxy-SVAR 的交叉协方差结构）。

### 残差 bootstrap（`lib.residual_bootstrap_draws`、`lib.cholesky_irf`）

从残差的经验分布中有放回地独立同分布重抽样。每次 bootstrap 迭代抽取 `T_eff` 个。

稳定性过滤：如果重抽样后 VAR 的伴随矩阵有任何特征值的模 `>= eig_tol`（默认 1.0），丢弃这次抽样。
尝试次数上限为 `4 * n_draws`，超过就报错。

**不对称说明**：proxy-SVAR 的 bootstrap（`_proxy_wild_bootstrap`、`_proxy_moving_block_bootstrap`
和多工具变量版本）使用一个写死的、略宽松的容差 `1.01`，而不是 1.0。proxy 应用通常运行近单位根的
水平 VAR，严格的 1.0 过滤会丢弃大量重新估计的抽样，使区间产生偏差。1.01 的上限保留了那些略呈爆炸性、
但其脉冲响应在所报告期限内仍然表现良好的重新估计结果。

### Bootstrap 中的外生变量块

当 `fit.has_exog` 时，外生变量在各次 bootstrap 重复中保持**固定**（视为确定性的）。只对内生残差重抽样。

---

## 6. 容器约定

| 容器 | 形状 | 下标 |
|---|---|---|
| `IRFContainer.median` | `(H+1, n_vars, n_shocks)` | `[h, var, shock]`；`h=0` 是当期 |
| `FEVDContainer.median` | `(H+1, n_vars, n_shocks)` | 同样的轴；h>=1 时 `[h, ...]` 是向前 h 步的份额（h=0 行是退化的 / 按约定设为当期份额） |
| `HistoricalDecompositionContainer` | DataFrame 的字典，每个 `(T_eff, n_vars)` | `.shocks[name]`、`.deterministic_plus_initial`、`.other_shocks` |
| `ForecastContainer` | 点预测为 `(H, n_vars)`；密度预测为 `(n_paths, H, n_vars)` | 预测从 h=1 开始 |
| `ConditionalForecastContainer` | 与 ForecastContainer 相同 | 条件信息在元数据中 |

### 元数据字段

所有容器都带有一个 `metadata: dict` 字段。建议的键：

- `method`：自由格式的描述（"VAR / Cholesky"、"narrative sign restrictions"）
- `identification`：机器可读的标签（见第 4 节）
- `n_lags`、`n_obs_effective`
- `seed`：用于复现的随机数种子
- `parameter_uncertainty`：bool
- 符号约束：`n_attempted`、`n_accepted`、`acceptance_rate`、`n_rejected_by_narrative`、
  `n_rejected_by_fev_share`
- proxy-SVAR：`first_stage` 字典，含 `F`、`gamma`、`R2`、`n_obs`

---

## 7. 时间索引与样本对齐

### 有效样本

对 VAR(p)，`T_eff = T - p`。`Y_act` 的形状是 `(T_eff, n)`，从输入数据的第 `p` 个位置开始。残差与
`Y_act` 对齐：`fit.residuals[i]` 是 `fit.data.iloc[p + i]` 期的新息。

### `fit.data.index` 中的日期对齐

- `fit.data.index[:p]` → 初始条件（不计算残差）。
- `fit.data.index[p:]` → 有效样本，每期一个残差。
- `fit.data.index[p + i]` → 与 `fit.residuals[i]` 和 `fit.Y_act[i]` 对应的时期。

### PeriodIndex 与 Timestamp 的对齐

`load_dataset("fred_qd", ...)` 返回季末的 Timestamp（3 月、6 月、9 月、12 月）；国家统计局季度面板
`nbs_q` 采用同样的约定。pandas 的 `.resample("QS").mean()` 返回季初的 Timestamp（1 月、4 月、7 月、
10 月）。直接合并两者会得到全是 NaN 的行。

**把 FRED-QD（或 `nbs_q`）与外部重采样的数据混合时**，合并之前先把两者都转成 `PeriodIndex('Q')`，
最后再转回 Timestamp。做法：

```python
q = monthly.resample("QS").mean()
q.index = q.index.to_period("Q")          # 在 PeriodIndex('Q') 上对齐
merged = fredqd_df.set_axis(fredqd_df.index.to_period("Q")).join(q)
merged.index = merged.index.to_timestamp()  # 转回 Timestamp
```

---

## 8. 常见陷阱 / FAQ

### "论文用的是 100·log；我的数据是 log"

如果你的数据是自然对数，而论文用 100·log，有两个选择：
1. 拟合之前把数据乘以 100，直接得到与论文尺度一致的脉冲响应。
2. 保持自然对数，然后把脉冲响应乘以 100 得到百分比。

两种都行；选一种并保持一致。

### "2 年期限的 FEVD：H=8 还是 H=7？"

季度数据用 `horizon=8`，它对 8 项求和（j=0..7）。见第 2 节"期限约定"。

### "为什么 `np.std(u, ddof=1)` 不等于 `sqrt(Sigma_u[i,i])`？"

普通 VAR 除以 `T_eff - k`，而不是 `T_eff - 1`。确切比值见第 3 节"`Sigma_u` 的除数"。

### "为什么 `trend='ct'` 与 `trend='c'` 不一样？"

趋势列在 `X_act` 中加入一个 `1, 2, ..., T_eff` 的回归元，把确定性的线性时间趋势从滞后系数中吸收掉。
对于有持续低频变化的序列（大宗商品价格、整体 CPI），`'ct'` 会实质性地改变滞后系数和脉冲响应的
持续性。由 `tests/test_var.py::test_trend_ct_adds_trend_row_to_b_hat` 固定。

### "什么时候用 HD，什么时候用 FEVD？"

- **HD（历史分解）**把每个 $t$ 上 $Y_t$ 的观测路径分解为各冲击的贡献加上确定性项 + 初始条件。它是
  **时间上**的分解："2022Q1 的 Y_t 中有多少来自哪些冲击？"
- **FEVD（预测误差方差分解）**把向前 H 步预测误差的方差分解为各冲击的贡献。它是关于**期限分布**的
  陈述："在 2 年期限上，方差中有多大份额来自冲击 j？"

两者回答不同的问题。它们各自都有合理的期限约定，但并不一一对应。

---

## 8b. 独立交叉核对

与独立实现的交叉核对见 DEVELOPMENT.md 的"Independent cross-checks"一节；它们发现的约定差异在本文件
相应位置有说明。

## 9. 扩展本文件

如果你在 `lib.` 中加入了一个约定选择（新的归一化选项、期限约定或容器），在这里记录它，并尽可能在
`tests/test_conventions.py` 中配一个闭式测试。
