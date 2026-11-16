# 复现示例库

每篇论文一个目录。每个复现都是一个独立、可浏览的目录，作为公共参考：下载或点进一个目录，读设定，
运行 `replicate.py` 重新生成产出（大多数复现一分钟以内）；运行后完整的来源记录写在
`outputs/research_log.json`。

## 约定

```
replications/
└── <dictionary_id>/                  ← 与 skills/model-dictionary/entries/<id>.yaml 对应
    ├── README.md                     ← 论文引用、概述、预期结果
    ├── config.yaml                   ← 全部设定选择（与字典条目对应）
    ├── paper_targets.yaml            ← （建议）用于验证的声明性检查。
    │                                     注意：其中混有已发表的基准值、结构恒等式和
    │                                     由复现得出的量级；每个文件都标明了哪个是哪个，
    │                                     所以"N/N"表示"所有声明的检查都通过"，
    │                                     而不是"复现了 N 个已发表的数字"
    ├── replicate.py                  ← 薄脚本：读配置 -> 调用 lib -> 保存产出
    └── outputs/
        ├── report.html               ← 交互式 Plotly 报告
        ├── numerical_results.json    ← 脉冲响应快照，用于 IRF 方法（其他方法写自己的 CSV）
        ├── research_log.json         ← 完整来源 + 论文目标对照
        └── *.pdf / *.tex（可选）      ← 用于印刷的图和表
```

目录名与字典的 `id` 完全一致。在字典里搜索可以找到复现，在这个目录里搜索可以找到论文。

`replicate.py` 有意写得很薄（最多几百行）。重活在 [`scripts/lib/`](../lib/) 里。库改进时，每个复现都会
受益，而不用改动各篇论文的脚本。

各复现目录中的 README、配置和脚本保留英文原文。

## 论文目标验证（新复现建议使用）

每个复现应在 `paper_targets.yaml` 中声明论文报告的具体数字，然后在 `replicate.py` 末尾调用
`lib.compare_to_paper`。这种做法在**构建时**就能发现论文结果与我们结果的偏离，相当于
[`tests/test_conventions.py`](../../tests/test_conventions.py) 在库层面所做的事情在复现层面的对应。

`paper_targets.yaml` 示例：

```yaml
targets:
  - description: "Core CPI pass-through (peak)"
    location: "Section 2.2, US column"
    paper_value: 0.21
    paper_units: "percent, 10% energy commodity shock"
    our_key: "core_cpi_peak_per_10pct_shock"
    tolerance: 0.10
    tolerance_kind: "absolute"             # 或 "relative"

  - description: "Energy FEV at 2y horizon"
    location: "Footnote 5"
    paper_value: 0.19
    paper_units: "share (0-1)"
    our_key: "energy_fev_2y_share"
    tolerance: 0.50
    tolerance_kind: "relative"
```

在 `replicate.py` 中：

```python
import lib

our_results = {
    "core_cpi_peak_per_10pct_shock": float(...),
    "energy_fev_2y_share": float(...),
    # ...
}
report = lib.compare_to_paper(our_results, HERE / "paper_targets.yaml")
print(report.table())
# 保存以备溯源
log["paper_target_comparison"] = report.to_dict()
```

写这个 YAML 的过程，迫使你在宣布复现成功之前仔细读论文。通过 / 不通过一列让含糊的偏离变得明确，而不是
埋没在一张"替代"表里。

## 索引

**忠实程度。***论文设定*遵循论文的主要模型设计，并注明替代之处。*论文系统，修改方法*保留论文中各变量
的角色，但改变了模型、估计、识别或推断。*方法演示*在不同的系统或数据上演示论文的部分思想，或使用论文的
冲击序列；也可能对方法做了改动。表中列出主要的偏离之处。完整的差异和结果见各目录的 README。

**数据。**FRED-MD 和 FRED-QD 按 [`data/fred_md/UPDATE.md`](../../data/fred_md/UPDATE.md) 和
[`data/fred_qd/UPDATE.md`](../../data/fred_qd/UPDATE.md) 下载一次。标为"抓取"的来源在第一次运行时
自动下载。标为"必需"的文件需要你自己暂存；缺少时，脚本会退出并给出获取说明。

| 字典条目 | 目录 | 方法 | 对论文的忠实程度 | 数据 |
|---|---|---|---|---|
| [sims_1980_var](../../skills/model-dictionary/entries/sims_1980_var.yaml) | [`sims_1980_var/`](sims_1980_var/) | VAR + Cholesky | **论文设定**：样本从 1959 年开始；用 PPI（WPSID61）代替进口价格 | FRED-QD |
| [cee_1999_monetary_svar](../../skills/model-dictionary/entries/cee_1999_monetary_svar.yaml) | [`cee_1999_monetary_svar/`](cee_1999_monetary_svar/) | OLS VAR + Cholesky | **论文设定**：用 log PPIACO 代替平滑后的大宗商品价格变化；NONBORRES 不含扩展信贷 | FRED-QD |
| [cee_1996_flow_of_funds](../../skills/model-dictionary/entries/cee_1996_flow_of_funds.yaml) | [`cee_1996_flow_of_funds/`](cee_1996_flow_of_funds/) | OLS VAR + Cholesky，两种政策冲击度量（FF 和 −log NBR） | **论文设定**：只做第 II 节（资金流量部分不在范围内）；大宗商品用 PPIACO | FRED-QD |
| [uhlig_2005_sign_restrictions](../../skills/model-dictionary/entries/uhlig_2005_sign_restrictions.yaml) | [`uhlig_2005_sign_restrictions/`](uhlig_2005_sign_restrictions/) | 符号约束 VAR（纯符号方法） | **论文系统，修改方法**：用渐近参数抽样代替论文的弱先验后验；INDPRO、CPI 和 WPSID62 作代理 | FRED-MD |
| [kilian_2009_oil_svar](../../skills/model-dictionary/entries/kilian_2009_oil_svar.yaml) | [`kilian_2009_oil_svar/`](kilian_2009_oil_svar/) | 递归石油市场 SVAR（VAR(24) + Cholesky） | **论文设定**：Kilian 自己公开的数据；没有替代 | Kilian 公开的数据（抓取） |
| [jorda_2005_lp](../../skills/model-dictionary/entries/jorda_2005_lp.yaml) | [`jorda_2005_lp/`](jorda_2005_lp/) | 局部投影 | **方法演示**：用 CEE 式的 4 变量货币系统代替 Jordà 的 3 变量产出缺口系统 | FRED-QD |
| [litterman_1986_bvar](../../skills/model-dictionary/entries/litterman_1986_bvar.yaml) | [`litterman_1986_bvar/`](litterman_1986_bvar/) | BVAR + Minnesota | **论文设定**：FRED-QD 代理变量；样本 1959–2019，而不是 1948–1979 | FRED-QD |
| [bgr_2010_large_bvar](../../skills/model-dictionary/entries/bgr_2010_large_bvar.yaml) | [`bgr_2010_large_bvar/`](bgr_2010_large_bvar/) | 受 BGR 启发的收缩校准 | **方法演示**：17 变量的 FRED-MD 子集，而不是 131 个变量；用对数平均 MSE 校准代替论文的相对 MSFE 拟合 | FRED-MD |
| [romer_romer_2004_narrative_mp](../../skills/model-dictionary/entries/romer_romer_2004_narrative_mp.yaml) | [`romer_romer_2004_narrative_mp/`](romer_romer_2004_narrative_mp/) | Proxy-SVAR + 叙事冲击 | **方法演示**：把 RR 冲击作为 4 变量 VAR 中 proxy-SVAR 的工具变量，而不是论文的设计 | FRED-MD + 暂存的 RR 冲击文件（必需） |
| [auerbach_gorodnichenko_2012](../../skills/model-dictionary/entries/auerbach_gorodnichenko_2012.yaml) | [`auerbach_gorodnichenko_2012/`](auerbach_gorodnichenko_2012/) | 状态依存 LP | **论文系统，修改方法**：用状态依存局部投影代替论文的平滑转换 VAR | FRED-QD |
| [stock_watson_2018_lpiv](../../skills/model-dictionary/entries/stock_watson_2018_lpiv.yaml) | [`stock_watson_2018_lpiv/`](stock_watson_2018_lpiv/) | 缩放简约式 LP-IV | **方法演示**：用 Jarociński-Karadi 工具变量和 1990–2024 年样本，而不是 GK 期货意外 | FRED-MD + JK 冲击（抓取） |
| [gertler_karadi_2015_proxy_svar](../../skills/model-dictionary/entries/gertler_karadi_2015_proxy_svar.yaml) | [`gertler_karadi_2015_proxy_svar/`](gertler_karadi_2015_proxy_svar/) | Proxy-SVAR | **方法演示**：JK 工具变量，用 BAA-AAA 利差代替 EBP，1990–2024 年样本 | FRED-MD + JK 冲击（抓取） |
| [blanchard_quah_1989](../../skills/model-dictionary/entries/blanchard_quah_1989.yaml) | [`blanchard_quah_1989/`](blanchard_quah_1989/) | 长期约束识别 | **论文设定**：情形 (c)；用总失业率代替 20 岁以上男性失业率；用实际 GDP 代替 GNP | FRED-QD |
| [gali_1999_technology_var](../../skills/model-dictionary/entries/gali_1999_technology_var.yaml) | [`gali_1999_technology_var/`](gali_1999_technology_var/) | 长期约束识别（技术冲击） | **论文设定**：用非农企业工时代替雇员总工时；样本从 1959 年开始 | FRED-QD |
| [hamilton_2018_filter](../../skills/model-dictionary/entries/hamilton_2018_filter.yaml) | [`hamilton_2018_filter/`](hamilton_2018_filter/) | 趋势-周期滤波 | **论文设定**：FRED-QD 实际 GDP，1959–2024，而不是 1947–2016 | FRED-QD |
| [kamber_morley_wong_2018_bnf](../../skills/model-dictionary/entries/kamber_morley_wong_2018_bnf.yaml) | [`kamber_morley_wong_2018_bnf/`](kamber_morley_wong_2018_bnf/) | KMW BN 滤波（delta-bar = psi(1)^2 约束，闭式约束 OLS） | **论文系统，修改方法**：约束 OLS，没有论文的收缩先验；delta-bar 取 0.25（论文 0.24） | FRED-QD |
| [bbe_2005_favar](../../skills/model-dictionary/entries/bbe_2005_favar.yaml) | [`bbe_2005_favar/`](bbe_2005_favar/) | FAVAR（两步主成分） | **方法演示**：19 个 FRED-MD 序列，而不是论文的 120 序列面板 | FRED-MD |
| [glp_2015_prior_selection](../../skills/model-dictionary/entries/glp_2015_prior_selection.yaml) | [`glp_2015_prior_selection/`](glp_2015_prior_selection/) | 经验贝叶斯 BVAR 超参数选择 | **方法演示**：CEE 1999 的 7 变量 VAR，而不是 GLP 的 3/7/22 变量系统 | FRED-QD |
| [diebold_yilmaz_2012_connectedness](../../skills/model-dictionary/entries/diebold_yilmaz_2012_connectedness.yaml) | [`diebold_yilmaz_2012_connectedness/`](diebold_yilmaz_2012_connectedness/) | 广义 FEVD 溢出指数 | **方法演示**：1973–2024 年月度收益率和收益率变化的波动率代理，而不是 1999–2010 年日内极差波动率 | FRED-MD |
| [rigobon_2003_heteroskedasticity_id](../../skills/model-dictionary/entries/rigobon_2003_heteroskedasticity_id.yaml) | [`rigobon_2003_heteroskedasticity_id/`](rigobon_2003_heteroskedasticity_id/) | 异方差识别 | **方法演示**：美国工业生产、10 年期收益率和股票，用 NBER 划分制度，而不是新兴市场债券 | FRED-MD |
| [schorfheide_song_2015_mfvar](../../skills/model-dictionary/entries/schorfheide_song_2015_mfvar.yaml) | [`schorfheide_song_2015_mfvar/`](schorfheide_song_2015_mfvar/) | 混频 BVAR | **方法演示**：4 个增长率变量，而不是 11 个对数水平变量 | FRED-MD + FRED-QD |
| [primiceri_2005_tvpvar](../../skills/model-dictionary/entries/primiceri_2005_tvpvar.yaml) | [`primiceri_2005_tvpvar/`](primiceri_2005_tvpvar/) | 同方差 TVP-VAR | **论文系统，修改方法**：论文的三个变量和 Q 先验校准；协方差不变，所以没有时变的当期系数和随机波动 | FRED-QD |
| [banbura_modugno_2014_bdfm](../../skills/model-dictionary/entries/banbura_modugno_2014_bdfm.yaml) | [`banbura_modugno_2014_bdfm/`](banbura_modugno_2014_bdfm/) | 处理参差边缘的贝叶斯 DFM | **方法演示**：15 序列的美国 FRED-MD 面板和 Gibbs 抽样，而不是欧元区面板和 EM | FRED-MD |
| [mertens_ravn_2013_tax_proxy_svar](../../skills/model-dictionary/entries/mertens_ravn_2013_tax_proxy_svar.yaml) | [`mertens_ravn_2013_tax_proxy_svar/`](mertens_ravn_2013_tax_proxy_svar/) | 多工具变量 proxy SVAR（单位政策当期块） | **论文系统，修改方法**：作者存档的数据；用单位阵政策当期块代替论文的三角税收冲击分解 | 从作者 AER 存档暂存的文件（必需） |
| [antolin_diaz_rubio_ramirez_2018](../../skills/model-dictionary/entries/antolin_diaz_rubio_ramirez_2018.yaml) | [`antolin_diaz_rubio_ramirez_2018/`](antolin_diaz_rubio_ramirez_2018/) | 叙事符号约束（Type 1 + Type 2；仅拒绝抽样） | **方法演示**：4 变量货币 VAR，而不是论文的应用；没有 ADRR 的重要性加权 | FRED-MD |
| [canova_ciccarelli_2013_panel_var](../../skills/model-dictionary/entries/canova_ciccarelli_2013_panel_var.yaml) | [`canova_ciccarelli_2013_panel_var/`](canova_ciccarelli_2013_panel_var/) | 混合 / 均值组 / 堆叠 Minnesota VAR | **方法演示**：在 G4 面板上演示综述中的部分方法；综述本身没有实证基准 | FRED（由 `prepare_data.py` 构建） |
| [lanne_meitz_saikkonen_2017_nongaussian_svar](../../skills/model-dictionary/entries/lanne_meitz_saikkonen_2017_nongaussian_svar.yaml) | [`lanne_meitz_saikkonen_2017_nongaussian_svar/`](lanne_meitz_saikkonen_2017_nongaussian_svar/) | 非高斯 SVAR（FastICA + 近似 LMS 第 2 步 t-ML） | **方法演示**：3 变量月度美国 VAR，而不是 4 变量季度 KCFCI 系统 | FRED-MD |
| [andrade_ferroni_melosi_2023_higher_moments](../../skills/model-dictionary/entries/andrade_ferroni_melosi_2023_higher_moments.yaml) | [`andrade_ferroni_melosi_2023_higher_moments/`](andrade_ferroni_melosi_2023_higher_moments/) | 符号 + 样本峰度约束 | **方法演示**：4 变量货币 VAR；用样本矩和渐近抽样代替论文的稳健矩和后验 | FRED-MD |
| [banbura_giannone_lenza_2015_conditional_forecasts](../../skills/model-dictionary/entries/banbura_giannone_lenza_2015_conditional_forecasts.yaml) | [`banbura_giannone_lenza_2015_conditional_forecasts/`](banbura_giannone_lenza_2015_conditional_forecasts/) | 条件预测（Kalman，BGL 2015） | **方法演示**：美国 7 变量 CEE 式 BVAR，而不是 26 变量的欧元区面板 | FRED-QD |
| [lenza_primiceri_2022_covid_var](../../skills/model-dictionary/entries/lenza_primiceri_2022_covid_var.yaml) | [`lenza_primiceri_2022_covid_var/`](lenza_primiceri_2022_covid_var/) | 带固定 COVID 缩放的 BVAR（GLS） | **方法演示**：4 变量季度 BVAR，而不是论文的 7 变量月度示例 | FRED-QD |

用户自己的分析放在 [`scripts/applications/`](../applications/)；这个目录只放经典论文复现。所有复现都基于
美国（或欧元区）数据；用中国数据做的分析放在 `scripts/applications/`。

每个字典条目都有一个对应的复现目录。新论文通过模式 B 进入：起草条目，设定核验之后再把目录加到这里。
`gali_1999_technology_var/`（文字版 PDF）和 `cee_1996_flow_of_funds/`（纯图像扫描件）是这一流程的示例。

## 添加新的复现

1. 把 `sims_1980_var/` 作为模板复制到 `<your_id>/`。
2. 编辑 `config.yaml`，使之与字典条目一致。
3. 编辑 `replicate.py`，读取正确的数据并调用正确的库函数（`lib.fit_var`、`lib.cholesky_irf`、
   `lib.sign_restricted_irf`……）。
4. 运行；确认产出在经济上说得通。
5. 保留 `README.md`、`config.yaml`、`paper_targets.yaml` 和 `replicate.py`。`outputs/` 目录不纳入
   版本管理；其他人运行 `replicate.py` 即可重新生成（大多数复现一分钟以内），运行后来源记录写在
   `outputs/research_log.json`。

## 可复现性

`outputs/numerical_results.json` 是脉冲响应的四舍五入本地快照，可以在不同运行之间做 diff。与论文的
自动对照是 `paper_targets.yaml`：复现冒烟测试（`--runslow`）运行每个复现，只要有一个目标不通过就失败。

运行结果与发布版本（`CITATION.cff` 中的版本）和数据版本绑定；见
[`scripts/lib/README.md`](../lib/README.md#版本)。
