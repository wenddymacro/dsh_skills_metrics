# 更新 FRED-MD

`dataset.csv` 不随框架分发；首次使用时，按下面的下载步骤操作一次（在 `data/fred_md/` 目录下运行）。
把你下载的版本（文件日期或页面上写的版本名）和你的副本记在一起：结果依赖版本，而 loader 只记录你
告诉它的信息。

## 更新频率

每月更新，在圣路易斯联储发布新版本后不久（通常在每月第一周内）。

## 手工更新

1. 打开 https://www.stlouisfed.org/research/economists/mccracken/fred-databases
2. 在"FRED-MD: Monthly Data"下，下载 `current.csv`，保存为 `data/staging/fred_md_current.csv`
   （已 gitignore）。
3. 运行下面的清洗脚本，去掉元数据行，写出 `dataset.csv` + `transform_codes.csv`。**不要**把原始的
   `current.csv` 直接保存为 `dataset.csv`；其中的变换编码行会让 `lib.load_dataset` 出错（第一行不是
   日期 → 截取样本时报 TypeError）。
4. 在 `../registry.yaml` 中更新版本和日期范围。

## 清洗脚本

```python
import pandas as pd

# 网站拦截脚本下载；请在浏览器里下载 current.csv。
raw = pd.read_csv("../staging/fred_md_current.csv")  # 原始下载
transform_codes = raw.iloc[0]
data = raw.iloc[1:].copy()
# 直接用解析后的日期设为索引 -- 在 pandas >= 3 下把日期写回字符串列会出错
data = data.set_index(pd.to_datetime(data.iloc[:, 0])).drop(columns=data.columns[0])
data.index.name = 'date'
data = data.apply(pd.to_numeric, errors='coerce')
data.to_csv("dataset.csv")
transform_codes.to_csv("transform_codes.csv")
```

## 说明

- FRED-MD 约有 126 个月度变量（数量随版本变化）。
- 原始 CSV 的第一行是变换编码。
- 变换编码：1=水平，2=Δ，3=Δ²，4=log，5=Δlog，6=Δ²log，7=Δ(p/p(-1)-1)。
- 参考文献：McCracken and Ng (2016)。
