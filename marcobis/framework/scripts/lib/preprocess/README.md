# lib.preprocess

不属于数据读取层（它是*结构性*的）、也不属于 `lib.transform`（它是*逐列单变量*的）的复杂预处理操作。
把它们分离出来，任何下游模型都能复用，不必重复写逻辑。

## 操作

| 函数 | 用途 | 方法 |
|---|---|---|
| `deflate(nominal, deflator, base_period=None)` | 名义 → 实际 | 相除 + 可选的基期重定 |
| `nominalise(real, deflator, base_period=None)` | 实际 → 名义 | 相乘 + 可选的基期重定；`deflate` 的逆运算，`sims_1980_var`、`cee_1996_flow_of_funds`、`cee_1999_monetary_svar`、`glp_2015_prior_selection` 使用 |
| `aggregate(df, target_freq, method)` | 频率聚合（如 M → Q） | `sum`（流量）、`mean`（比率）、`end`/`start`（存量）、`min`/`max`/`median`/`std`；可以逐列指定方法 |
| `impute(df, method, lags=..., em_iter=...)` | 填补缺失值 | `ffill`、`linear`、通过 VAR(p) 状态空间的 **Kalman 平滑**（复用 [`lib.state_space`](../state_space.py)）；缺失严重时可选 **EM 迭代**（Shumway-Stoffer 1982）。覆盖参差边缘的即时预测和面板缺口 |
| `china.*`（`lib.preprocess.china`） | 中国官方数据清洗 | `cumulative_to_period`（年内累计值 → 当月 / 当季值，处理 1–2 月合并公布）、`fill_january`（补齐未单独公布的 1 月 / 1–2 月增长率）、`chain_index`（环比连乘、同比补齐，构造定基指数）、`index_to_rate`（"上年同期=100" → 百分比）、`splice_ratio`（口径变化时的重叠期比例衔接）、`regularize`（补齐日历） |

**未包含：**频率分解（Chow-Lin、Denton）、季节调整、异常值检测和缩尾、标准化、同比差分和移动平均。
有季调后的来源序列时优先用它，或者直接调用 `statsmodels`（X-13、STL）；因子模型内部会做标准化
（`lib.factors`、`lib.dfm`）。中国数据多数未经季调，季调方法要在设定阶段与用户商定（见 nbs-data
skill）。

## 不在范围内（已在别处覆盖）

- **趋势-周期滤波**：HP、Hamilton、BN、KMW-BN → 在 [`lib.filters`](../filters.py)
- **逐列单变量变换**（`log`、`diff`、`log_diff`……）→ 在 [`lib.transform`](../data/transforms.py)
- **识别旋转、脉冲响应计算** → 在 [`lib.identification`](../identification.py)

## 设计原则

1. **无状态函数。**每个函数输入数据、输出数据，没有隐藏状态。
2. **保留元数据。**如果输入是带 `df.attrs`（来自 `lib.load_dataset` 的来源信息）的 DataFrame，保留它，
   并追加一条 `preprocess_applied` 记录，让研究日志能追溯做过什么。
3. **使用成熟的软件包。**封装经过充分测试的实现（`statsmodels`、`scipy`），而不是重新实现。

## 它在 `replicate.py` 中的位置

```python
# 1. 读取带来源元数据的原始数据
raw = lib.load_dataset(source="fred_md", series={...}, start=..., end=...)

# 2. 预处理（平减、聚合、插补）；每个操作返回一个 Series，
#    作为新列加到表里
data = raw.copy()
data["m1"] = lib.preprocess.nominalise(raw["m1_real"], raw["deflator"])
# （按需加入更多预处理步骤）

# 3. 对模型变量做逐列变换
data = lib.transform(data[["m1", "gdp"]], {"m1": "log", "gdp": "log_diff_pct"})

# 4. 拟合 + 识别
fit = lib.fit_var(data, lags=4)
irf = lib.cholesky_irf(fit, ...)
```

流程顺序很重要：预处理的结果会进入变换层（例如 nominalise 得到名义 M1，然后再取对数）。
