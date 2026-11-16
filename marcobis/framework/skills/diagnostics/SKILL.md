---
name: econometric-diagnostics
description: >
  VAR/BVAR 模型的残差诊断和模型充分性检验。主控到达第 4 阶段（估计）的诊断步骤时使用，其结果
  供第 5 阶段合理性检查使用；用户要求检查残差，检验自相关、异方差、正态性或结构断点时也使用。
---

# 计量诊断

## 进行的检验

**内置的一组检验。**`lib.diagnostics(fit)` 提供：

- 逐方程：Ljung-Box（一个或多个滞后）、Jarque-Bera 和 ARCH-LM；
- 系统层面：伴随矩阵特征值的最大模，附带状态标签（稳定性）；
- AIC/BIC/HQ 滞后阶数比较：在 p = 1..`max_lag_search` 上重新拟合 OLS VAR，报告每个准则选出的 p。

下面标为*附加*的检验不属于内置的一组；问题需要时，agent 可以单独运行它们（例如用 statsmodels）。

### 残差层面的诊断

对 VAR 系统中的每个方程：

1. **自相关。**在滞后 4、8、12（季度）或 6、12、24（月度）上做 Ljung-Box 检验。
   （`lib.diagnostics(fit, lb_lags=[...])` 一次调用就能算出所有要求的滞后；报告中的诊断表在每行
   标出实际使用的滞后。）*附加：*系统的 Breusch-Godfrey LM 检验。
2. **异方差。**ARCH-LM 检验（Engle, 1982），检测条件异方差。*附加：*检验无条件异方差的 White
   检验。
3. **正态性。**逐方程的 Jarque-Bera 检验。*附加：*系统的 Lomnicki-Jarque-Bera 检验。
   注意：宏观数据中非正态很常见，除非非常极端，否则不是否定模型的理由。

**中国数据：**未经季节调整的月度 / 季度序列，残差常在季节滞后（月度 12、季度 4）上出现显著
自相关，春节月份也常出现大残差。看到这类信号时，先回到设定阶段检查季节性是否处理好，而不是
直接加滞后阶数。

### 系统层面的诊断

1. **稳定性。**伴随矩阵的特征值。报告最大根，把动态归类为平稳（小于 1）、单位根（在抽样误差
   范围内等于 1）或爆炸（大于 1）。一致地应用所声明的模型类别和复现标准，把近单位根的抽样
   不确定性作为公开披露的诊断项，不要凭有限期的图形认定稳定。
   （`lib.diagnostics` 报告最大模；在单位圆图上画出特征值是附加步骤。）
   **水平系统的裁定：**只要 max |eig| ≥ 1.0，`lib.diagnostics` 就会标为"non-stationary /
   unstable"，但对数水平的 VAR（或采用随机游走 Minnesota 先验的 VAR）合理地位于单位圆上或略在
   其外；有几个经典复现就是对照 1.0 ± 0.05 这样的预期区间来验证的。按以下顺序裁定：
   (i) 设定是否有意保留类似单位根的持续性（水平 + 收缩）？如果是，接近 1 是预期之中的，不是
   失败；(ii) 对脉冲响应应用第 5 阶段的标准：暂时性冲击的响应应当消失，永久性冲击的响应应当
   收敛到有限极限；长期限上的发散是失败信号，但在有限期限内看起来平稳的响应，并不能证明大于 1
   的根是稳定的；(iii) 把 lib 的标签当作执行 (i)–(ii) 检查并披露分类的提示，绝不当作自动否决
   或自动通过。
2. **滞后阶数比较。**p = 1..`max_lag_search` 上 AIC、BIC 和 HQ 的选择（内置；与拟合所用 p 不同
   的选择会列在警告中）。
3. **Granger 因果**（*附加*）。区块外生性的 Wald 检验。有助于解释系统结构。
4. **滞后排除**（*附加*）。每个滞后在所有方程中的联合显著性。
5. **集合识别模型：接受率。**对于符号 / 零约束方案，把接受的抽样数 / 尝试数与经典运行或条目的
   预期范围对照（Uhlig 复现验证的是约 0.06 ± 0.04）。接受率低，或没有达到 `target_accepted`
   配额，是计算和精度上的警告。接受率取决于变量个数、约束、提议分布和抽样器，所以要同类相比，
   查看接受的抽样数和有效抽样数，并单独检查稳定性。不要凭一个通用的接受率阈值推断约束无效，也
   不要悄悄报告接受抽样数过少的结果。

### 结构断点检测（可选，附加）

1. CUSUM 和 CUSUM 平方检验。
2. 样本较长时，考虑在已知断点日期做分样本稳定性检验（例如 Volcker 的 1979Q4、全球金融危机的
   2008Q3；中国可考虑 2008Q4 刺激计划、2015 年汇改、2020Q1 疫情等，以知识库为准）。

**范围说明：统计异常与经济异常。**这个 skill 负责统计关口。*经济*异常（价格之谜、符号错误的
响应、不合理的量级）属于第 5 阶段：补救步骤在 `skills/specification/SKILL.md` 的"合理性检查失败
后的迭代修改"一节。数字在统计上干净、在经济上却不对时，去那里，而不是这里。

## 输出格式

**研究日志中**，记录 `lib.diagnostics(...).to_log_dict()`，以及单独运行的附加检验和 agent 的建议：

```
diagnostics:
  residuals:                                  # 以变量名为键
    M1:
      ljung_box: {4: {stat, p_value}, 8: ..., 12: ...}   # 以滞后为键
      jarque_bera_stat, jarque_bera_pvalue
      arch_stat, arch_pvalue
      breusch_godfrey: {stat, p_value}        # 附加；仅在单独运行时
  stability: {max_eigenvalue_modulus, stable: bool, status}   # status：stationary | marginal (near unit root) | non-stationary / unstable
  lag_selection: {current_p, max_lag_search, aic_recommended, bic_recommended, hqic_recommended}
  portmanteau: {stat, p_value, lags}          # 附加；仅在单独运行时
  eigenvalues: list of complex numbers        # 附加；仅在单独运行时
  warnings:                                   # lib.diagnostics(...).warnings
    - "Autocorrelation detected in M1 equation at lag 4 (p=0.02)"
    - "ARCH effects in GNP deflator equation"
  recommendation: "考虑提高滞后阶数，或加入条件异方差"   # 由 agent 撰写；不是 lib 的字段
```

**报告中**，不要手工制表。`VARReport.add_standard_sections` 会把拟合的 `DiagnosticReport` 交给
报告层的适配器（`scripts/lib/report.py` 中的 `_build_diagnostics_dict_from_report`）处理。直接调用
`VARReport.add_diagnostics` 时，传入一个精简的视图，以变量名为键、Ljung-Box 滞后用数字：

```yaml
per_equation:
  M1:
    ljung_box:
      4: {p_value: 0.30}
      8: {p_value: 0.40}
    arch_lm: {p_value: 0.50}
    jarque_bera: {p_value: 0.60}
system:
  stability:
    max_eigenvalue_modulus: 0.90
    note: stationary
```

附加检验、警告和建议留在日志里；报告表格只显示这些字段。

## 提案 → 确认（交回第 5 阶段 / 第 4 阶段）

向用户展示结果时，先用平实语言说模型是否通过。诊断从不悄悄重新设定模型。遇到**严重**失败
（不稳定，或表明设定错误的严重自相关）时：

1. **用平实语言说明哪项检验没通过**，以及它在经济上为什么重要，例如"伴随矩阵有一个 1.02 的根，
   所以 VAR 是爆炸性的，脉冲响应不会消失。"
2. **提出一个具体的补救办法并说明理由**，从常用手段中选（+1 阶滞后、调整顺序 / 加一个变量、
   收紧先验、缩短样本），例如"我建议加第 5 阶滞后；滞后 4 处的 Ljung-Box 失败说明有未建模的
   自身动态。"
3. **等用户确认或修改**，再回到第 4 阶段重新估计。（主控的 5 次自动迭代额度只覆盖实现 / 数据错误
   的修正和事先规定的统计规则；像这样经济上实质性的修改，每一次都要确认。）

对于**轻微**的警告（轻度非正态、边缘显著的 ARCH），说明情况并建议继续；不要阻塞。无论哪种情况，
都通过 research-log skill 记录这个标记及其处置。绝不在不提出选择的情况下自动重新设定。这是把
设计原则 3（主动建议，人工确认）应用于诊断。
