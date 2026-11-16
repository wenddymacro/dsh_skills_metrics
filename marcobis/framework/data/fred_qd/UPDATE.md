# 更新 FRED-QD

`dataset.csv` 不随框架分发；首次使用时，按下面的下载步骤操作一次（在 `data/fred_qd/` 目录下运行）。
把你下载的版本（文件日期或页面上写的版本名）和你的副本记在一起：结果依赖版本，而 loader 只记录你
告诉它的信息。

## 已知的序列问题

**准备金（`NONBORRES`、`TOTRESNS`）：**不做调整的话，不适合 1990 年代以前的准备金市场分析。现在的
FRED 序列不包含扩展信贷（论文时代的惯例是 NBR + 扩展信贷），并且带有未调整的断点，即 1984 年
Continental Illinois 事件引起的波动（±13%，多个标准差），以及 1990 年 12 月 / 1992 年 4 月的准备金
要求变化。固定准备金市场矩的复现（CEE 1996/1999 一类）会因为版本原因、而不是方法原因与已发表的数值
产生偏差；记录这种偏差，而不是重新调参，或者暂存一个经过断点调整的历史序列。

## 更新频率

每季度更新，在 GDP 初步估计发布后不久（通常在 1 月、4 月、7 月、10 月下旬）。

## 手工更新

1. 打开 https://www.stlouisfed.org/research/economists/mccracken/fred-databases
2. 在"FRED-QD: Quarterly Data"下，下载 `current.csv`，保存为 `data/staging/fred_qd_current.csv`
   （已 gitignore）。
3. 运行下面的清洗脚本，去掉**两行**元数据（因子标记 + 变换编码），写出 `dataset.csv`、
   `transform_codes.csv` 和 `factor_flags.csv`。**不要**把原始的 `current.csv` 直接保存为
   `dataset.csv`，因为元数据行会让 `lib.load_dataset` 出错。
4. 在 `../registry.yaml` 中更新版本和日期范围。

## 清洗脚本

```python
import pandas as pd

# 网站拦截脚本下载；请在浏览器里下载 current.csv。
raw = pd.read_csv("../staging/fred_qd_current.csv")  # 原始下载
# 第 0 行 = 因子标记，第 1 行 = 变换编码，数据从第 2 行开始
factors = raw.iloc[0]
transform_codes = raw.iloc[1]
data = raw.iloc[2:].copy()
# 直接用解析后的日期设为索引 -- 在 pandas >= 3 下把日期写回字符串列会出错
data = data.set_index(pd.to_datetime(data.iloc[:, 0])).drop(columns=data.columns[0])
data.index.name = 'date'
data = data.apply(pd.to_numeric, errors='coerce')
data.to_csv("dataset.csv")
transform_codes.to_csv("transform_codes.csv")
factors.to_csv("factor_flags.csv")
```

## 说明

- FRED-QD 约有 245 个季度变量（数量随版本变化）。
- 原始 CSV 有**两行**元数据：因子标记（第 0 行）和变换编码（第 1 行）。
- 复现 Sims (1980) 和 CEE (1999) 时，直接从 FRED-QD 取变量，保证季度对齐，无需聚合。
- 主要变量对应：GDPCTPI（GDP 平减指数）、PCECTPI（PCE 价格指数）、M1REAL（实际 M1）、GDPC1（实际 GDP）。
- 变换编码与 FRED-MD 的约定相同。
- 参考文献：McCracken and Ng (2020)。
