# 代码库

MaRCo@BIS 框架可复用的 Python 基础函数。[`../replications/`](../replications/) 下的所有复现脚本，
以及 `skills/` 下定义的、由主控驱动的工作流都导入它。

设计规则：凡是 `statsmodels`、`scipy` 或 `numpy` 能覆盖的步骤（OLS VAR 拟合、状态空间平滑、
信息准则），库都直接调用它们。这些包没有提供的方法（贝叶斯 VAR 及其 Gibbs 抽样器、符号约束抽样、
proxy SVAR、FAVAR 旋转、BN 滤波等）在这里依据论文实现，并由测试固定下来。HTML 报告使用 `plotly`。

## 模块

| 模块 | 作用 |
|---|---|
| [`irf.py`](irf.py) | `IRFContainer` / `FEVDContainer`，即 [DEVELOPMENT.md](../../DEVELOPMENT.md#standardised-irf-structure) 中定义的标准化输出约定 |
| [`var.py`](var.py) | `fit_var()`（封装 `statsmodels.tsa.api.VAR`）、伴随形式、MA 表示、稳定性、滞后选择。`VARFit.parameter_draws()` 提供通用的不确定性接口 |
| [`bvar.py`](bvar.py) | `fit_minnesota_bvar()`（`exogenous_block=` 用于小型开放经济的区块外生性）、`MinnesotaPrior`、`BVARFit`（`VARFit` 的子类，带 NIW 后验抽样）；`fit_steady_state_bvar()` / `SteadyStatePrior`（Villani 2009 均值调整 / 稳态先验）；用于 GLP (2015) 超参数选择的 `log_marginal_data_density()` 和 `optimize_minnesota_hyperparameters()`。可以直接接入 `cholesky_irf()` 和 `long_run_irf()`（`bands="parameter_draws"`），以及 `sign_restricted_irf()`（`parameter_uncertainty=True`；该函数没有 `bands` 参数） |
| [`lp.py`](lp.py) | `lp_irf()`（Jordà 2005）、`lp_iv_irf()`（Stock-Watson 2018 LP-IV），带 HAC 区间 |
| [`identification.py`](identification.py) | `cholesky_irf()`、`sign_restricted_irf()`（符号 / 叙事 / 量级 / FEV 份额 / 高阶矩约束）、`zero_sign_restricted_irf()`（ARRW 2018）、`proxy_svar_irf()`（GK / Mertens-Ravn / Stock-Watson；`normalization="reliability"`）、`long_run_irf()`（Blanchard-Quah）、`heteroskedasticity_irf()`（Rigobon 2003）。根据拟合类型自动选择渐近或后验不确定性 |
| [`inference.py`](inference.py) | `asymptotic_mc_draws()`、`residual_bootstrap_draws()`、`draw_parameter_samples()` |
| [`filters.py`](filters.py) | `hp_filter()`、`hamilton_filter()`（Hamilton 2018）、`beveridge_nelson()`、`kmw_bn_filter()`（Kamber-Morley-Wong 2018：以目标信噪比约束重新估计 AR(p)）、`FilterResult` |
| [`connectedness.py`](connectedness.py) | `connectedness()`（Diebold-Yilmaz 2012）、`generalised_fevd()`、`rolling_connectedness()` |
| [`factors.py`](factors.py) | `fit_favar()`、`favar_irf()`（Bernanke-Boivin-Eliasz 2005 两步主成分 FAVAR，带慢 / 快变量旋转） |
| [`state_space.py`](state_space.py) | `StateSpaceModel`、`kalman_filter_smooth()`、`simulation_smoother()`（`statsmodels.tsa.statespace` 的薄封装），以及用于流量聚合的 `mariano_murasawa_weights()` |
| [`gibbs.py`](gibbs.py) | `draw_niw_posterior()`（正态-逆 Wishart 共轭抽样）、`draw_state_path()`（单次 Durbin-Koopman 模拟平滑抽样）。MF-VAR、TVP-VAR、DFM 的基础 |
| [`mfvar.py`](mfvar.py) | `fit_mfvar_bayesian()`（Schorfheide-Song 2015 / Bańbura-Modugno 2014 混频 BVAR，Gibbs 抽样）；`MFVARSpec`、`MFVARFit`（`VARFit` 的子类，识别函数可以直接使用） |
| [`tvp.py`](tvp.py) | `fit_tvp_var()`（时变系数，Σ 不变）；`fit_tvp_var_sv()`（TVP-VAR + 对角随机波动）；`fit_tvp_var_sv_primiceri()`（完整的 Primiceri 2005：β_t、A_t 和 h_t 都时变）；`TVPVARSpec`、`TVPVARFit` |
| [`nongaussian_svar.py`](nongaussian_svar.py) | `nongaussian_svar_irf()`（Lanne-Meitz-Saikkonen 2017）：FastICA 初始化 + 非高斯独立成分下的参数伪 MLE |
| [`panel.py`](panel.py) | 面板 VAR 估计量（Canova-Ciccarelli 2013）：混合、均值组、贝叶斯部分混合 / 分层、跨国堆叠 VAR（`fit_global_var`；不是 Dees 等人的 GVAR） |
| [`dating.py`](dating.py) | 经济周期定年：Harding-Pagan（季度）和简化的 Bry-Boschan 式月度方法（没有平滑步骤） |
| [`validation.py`](validation.py) | `compare_to_paper()` 把一次运行的产出与复现的 `paper_targets.yaml` 对照，打印冒烟测试解析的通过 / 不通过表 |
| [`stochastic_volatility.py`](stochastic_volatility.py) | Kim-Shephard-Chib (1998) 对 log χ²(1) 的 7 成分混合近似；用于单变量随机波动抽样的 `draw_log_h_path()`。可在 TVP-VAR-SV 和 Cogley-Sargent 类应用中复用 |
| [`dfm.py`](dfm.py) | `fit_dfm_bayesian()`（Gibbs 抽样的贝叶斯 DFM，允许任意缺失；替代 Bańbura-Modugno 2014 的 EM 估计量）；`DFMSpec`、`DFMFit`。原生处理参差边缘 / NaN 观测 |
| [`report.py`](report.py) | `VARReport`：带 Plotly 图表和诊断表的交互式 HTML 报告 |
| [`forecast.py`](forecast.py) | `iterated_forecast()`（任意 `VARFit` 子类的点预测和密度预测，可选参数不确定性路径模拟）、`rolling_forecasts()`（扩展 / 滚动窗口驱动器）、`forecast_score()`（按期限或变量的 MSE/RMSE/MAE）、`diebold_mariano()`（HAC 稳健的两两预测比较检验）、`ForecastContainer` |
| [`specs.py`](specs.py) | `Spec`（不可变 dataclass，含 `data`/`model`/`irf`/`forecast`/`metadata` 块，`update` 做深度合并）、`Spec.from_config(path)` / `Spec.from_replication(id)` 工厂方法、`lib.run(spec)`（对受支持的设定分派到拟合 + 识别 + 预测：var/bvar 拟合，配合 cholesky、符号约束、长期约束或 proxy-SVAR 识别；其他情况抛出 `NotImplementedError`）、`SpecResult` |
| [`diagnostics.py`](diagnostics.py) | `diagnostics(fit)`（一键生成残差 + 稳定性 + 滞后选择报告）、`DiagnosticReport`，带 `summary()`（人类可读）和 `to_log_dict()`（可 JSON 序列化）。逐变量做 Ljung-Box / Jarque-Bera / ARCH-LM 检验，把稳定性归类为平稳 / 近单位根边缘 / 非平稳，在 `1..max_lag_search` 上运行 AIC/BIC/HQIC 选择并标出与当前 `p` 的分歧。警告列表汇总了需要处理的问题 |
| [`sensitivity.py`](sensitivity.py) | `sensitivity(base_spec, grid, metric_fn=None)`（在 `lib.run` 上做超参数扫描；`"model.prior.lambda_1"` 这样的点路径网格键映射为深度合并的设定覆盖；多轴网格取笛卡尔积）、`SensitivityReport`，带 `.table` DataFrame、`.results` 列表和 `.best(by, ascending)` 辅助方法。默认指标提取 `max_eig`、`aic`、`bic`、`hqic`、`log_mdd`（适用时） |
| [`data/`](data/) | 两步模式：`load_dataset(source, series, start, end, vintage)` 返回结构上干净的原始数据，以及 `df.attrs` 中的来源元数据（source、vintage、frequency、url、loaded_at，逐序列的来源代码 + 来自 FRED-MD 编码的 recommended_transform）。`transform(df, transforms)` 做逐列变换，因为变换的决定属于模型。可用的变换：标准 FRED-MD 编码（`level`、`log`、`diff`、`log_diff`/`dlog`、`diff_log_diff`/`ddlog`、`pct_change`）以及缩放变体（`log_x_100`、`dlog_x_100`/`log_diff_pct`/`dlog_pct`、`dlog_x_400`/`dlog_ann_q`）。运行时 fetcher 有 FRED、国家统计局（`nbs`）、Global Macro Database（`gmd`）、DBnomics、ONS、BoE IADB，以及 `csv_file`/`external_archive`（`lib.fetch_data`，cache-on-fetch）；预置的 FRED-MD/QD 和国家统计局面板 CSV 仍是默认路径。`data/nbs_client.py` 是国家统计局"国家数据"平台的客户端（目录树、指标、取数、分段表拼接）。`data/gmd_client.py` 是 Global Macro Database 客户端，`load_gmd(countries, variables, start, end, version=, forecasts=, wide=)` 读取 239 国年度面板（fetcher `gmd`） |
| [`preprocess/`](preprocess/) | 复杂的预处理工具：跨列的操作，或封装较重第三方工具的操作。`deflate` / `nominalise`（价格平减换算）、`aggregate`（频率聚合，如 M→Q，可逐列选择流量 / 比率 / 存量方法）、`impute`（线性 / Kalman / 基于 Shumway-Stoffer 的 EM），以及 `china`（中国官方数据清洗：累计值转当期值、1–2 月合并处理、环比 / 同比链接定基指数、口径比例衔接）。未包含的内容、设计说明以及它在 `replicate.py` 中的位置见 [`preprocess/README.md`](preprocess/README.md)。趋势-周期滤波（HP、Hamilton、BN、KMW-BN）留在 `filters.py`；逐列的单变量变换留在 `data/transforms.py` |

## 模块依赖图（仅核心模块；模块加载时无环）

`A ──► B` 表示 B 在加载时导入 A。函数内部的导入不显示（`lp.py` 只在 `blp_irf` 内部导入
`var.py`；`report.py` 在函数内部导入 `irf` 和 `diagnostics` 的辅助函数）。

```
  var.py ──┬──► inference.py ──► identification.py ──► factors.py
           ├──► identification.py
           ├──► bvar.py
           ├──► connectedness.py
           └──► factors.py

  irf.py ──┬──► identification.py
           ├──► factors.py
           └──► lp.py

  state_space.py ──► gibbs.py

  filters.py, report.py, data/   ← 不导入上面任何模块
```

`data/` 子包不依赖其他 lib 模块（`data/fetchers/nbs.py` 在函数内部导入 `preprocess/china.py`，
二者都只依赖 numpy / pandas）。

MF-VAR 导入 `bvar`、`var` 和 `state_space`；TVP-VAR 导入 `var` 和 `state_space`；DFM 导入
`factors` 和 `state_space`。

每个模块加载时都没有循环依赖。可以在 DAG 的任意层添加新文件来扩展库；只要新模块遵守"只向下导入"
的规则，现有模块不需要改动。

`inference.py` 从 `var.py` 导入共用的 VAR 辅助函数（`_ensure_psd`、`_build_x_row`、
`extract_lag_matrices`、`ma_representation`），这样依赖图保持无环。

顶层导入：

```python
import lib   # scripts/ 在 sys.path 上

# 数据，分两步：先读原始数据，再做变换。
# 第 1 步：结构上干净的原始数据，来源元数据在 df.attrs 中。
raw = lib.load_dataset(
    source="fred_md",
    series={"indpro": "INDPRO", "cpi": "CPIAUCSL", "ffr": "FEDFUNDS"},
    start="1965-01", end="2003-12",
)
# raw.attrs 包含：source、frequency、vintage、url、loaded_at、
# sample_start_actual / sample_end_actual / n_obs，以及逐序列的：
# series[alias] = {source_code, recommended_transform（来自 FRED-MD 编码）}

# 中国数据同理，例如：
# raw = lib.load_dataset(source="nbs_m", series=["cpi_index", "m2", "ip_yoy"],
#                        start="2005-01", dropna=False)

# 第 2 步：按模型做变换（变换的选择属于模型）
data = lib.transform(raw, {"indpro": "log", "cpi": "log", "ffr": "level"})

# 模型 + 识别
fit = lib.fit_var(data, lags=4)
irf = lib.cholesky_irf(fit, horizon=40, bands="asymptotic_mc", n_draws=2000)

# 报告
report = lib.VARReport(title="…", subtitle="…")
report.add_irf(irf_point=irf.median,
               ci_68_lo=irf.lower_68, ci_68_hi=irf.upper_68,
               ci_90_lo=irf.lower_90, ci_90_hi=irf.upper_90,
               horizons=irf.horizons,
               var_names=…, shock_labels=…)
report.save("outputs/report.html")
irf.save_snapshot("outputs/numerical_results.json")
```

## 模块与复现的对应

下表列出每个模块服务于哪些经典复现。

| 模块 | 服务于 |
|---|---|
| `var.py` + `identification.py`（`cholesky_irf`） | Sims 1980、CEE 1996、CEE 1999、Kilian 2009 |
| `bvar.py` | Litterman 1986、BGR 2010 大型 BVAR、GLP 2015 超参数优化、Lenza-Primiceri 2022（观测缩放） |
| `lp.py` | Jordà 2005、Stock-Watson 2018 LP-IV、Auerbach-Gorodnichenko 2012 |
| `identification.py`（`proxy_svar_irf`） | Gertler-Karadi 2015、Mertens-Ravn 2013、Romer-Romer 2004 |
| `identification.py`（`long_run_irf`） | Blanchard-Quah 1989、Galí 1999 |
| `identification.py`（`sign_restricted_irf`，含叙事和高阶矩约束，以及 `zero_sign_restricted_irf`） | Uhlig 2005、Antolín-Díaz-Rubio-Ramírez 2018、Andrade-Ferroni-Melosi 2023 |
| `identification.py`（`heteroskedasticity_irf`） | Rigobon 2003 |
| `nongaussian_svar.py` | Lanne-Meitz-Saikkonen 2017 |
| `filters.py` | Hamilton 2018、Kamber-Morley-Wong 2018 BNF，以及 HP / Beveridge-Nelson |
| `forecast.py`（`conditional_forecast`） | Bańbura-Giannone-Lenza 2015；各复现中的预测评价 |
| `connectedness.py` | Diebold-Yilmaz 2012 |
| `factors.py` | BBE 2005 FAVAR |
| `dfm.py` | Bańbura-Modugno 2014 DFM |
| `mfvar.py` | Schorfheide-Song 2015 |
| `tvp.py` + `stochastic_volatility.py` | Primiceri 2005 |
| `panel.py` | Canova-Ciccarelli 2013 |
| `dating.py` | 经济周期定年工具（没有专门的复现） |
| `specs.py` / `diagnostics.py` / `sensitivity.py` / `validation.py` | 通用：声明式运行、残差诊断、超参数扫描、论文目标验证 |
| `data/nbs_client.py` + `preprocess/china.py` | 国家统计局面板（`nbs_m` / `nbs_q` / `nbs_a`）；没有对应的论文复现 |

## 版本

库本身没有单独的版本号：它随压缩包发布一起管理版本（版本见 `CITATION.cff`）。要重新得到完全相同的
数字，使用同一个发布版本和同样的数据文件；FRED-MD/QD CSV 单独下载，每个版本都会修订；国家统计局
面板的版本是下载日期（见各面板的 `metadata.yaml`）。

## 测试

单元测试在 `tests/` 中（1,000 多个，每个 lib 模块一个测试模块，另有约定 / 数据生成过程还原 / 覆盖率
/ 文档一致性几层；见 `tests/README.md`；国家统计局部分见 `tests/test_nbs.py`）。每个模块都应当有：

* 一个标准的正确性检查（例如对 `var.py`，与 `statsmodels.tsa.api.VAR` 的差分测试，以及固定约定的
  Lütkepohl 教科书基准）。
* 通过复现冒烟测试（`--runslow`）获得的端到端覆盖：运行每个复现，只要有一个 `paper_targets.yaml`
  目标不通过就失败。
