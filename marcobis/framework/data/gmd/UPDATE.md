# Global Macro Database（GMD）

来源：<https://www.globalmacrodata.com/>（GitHub：KMueller-Lab/Global-Macro-Database）

> Müller, K., Xu, C., Lehbib, M., & Chen, Z. (2025). *The Global Macro Database: A New
> International Macroeconomic Dataset.* NBER Working Paper 33714. <https://doi.org/10.3386/w33714>

**许可：学术用途免费，其他用途需要作者书面许可**（<https://www.globalmacrodata.com/license.html>）。
因此数据不随框架分发，由用户运行下面的命令下载到本机；用到 GMD 的成果要引用上面的论文。

## 内容

- **国家 × 年份**的年度面板：239 个国家 / 地区，最早到 1086 年（多数国家的主要变量从 19 世纪或
  1950 年以后开始），整合 160 多个历史和现行来源（IMF IFS / WEO、WDI、OECD、BIS、JST、Mitchell、
  各国统计机构……），按优先级拼接并做比例衔接（chain-linking）。
- 约 80 个变量：名义 / 实际 GDP 和人均 GDP、消费（居民 / 政府）、投资、固定资本形成、进出口、
  经常账户（本币、美元、占 GDP 比重三种口径）；CPI、通胀、GDP 平减指数、名义 / 实际房价；
  短期 / 长期利率、政策利率、M0–M4；对美元汇率、实际有效汇率；一般政府和中央政府的收入、支出、
  税收、赤字、债务；人口、失业率；银行 / 主权债务 / 货币危机虚拟变量。完整列表：
  `python3 scripts/tools/gmd_tool.py vars`。
- **预测值**：当年以后约 5 年的值来自 IMF WEO 等来源的预测，由 `forecast_<变量>` = 1 标记。
  `lib.load_gmd` 和 `gmd_tool.py extract` **默认把预测年份置为缺失**；需要时加 `forecasts=True`
  / `--forecasts`。
- 每季度发布一个版本（`2026_09` 这样的编号），旧版本一直可以下载，方便复现。

## 下载

在工作区根目录：

```bash
python3 scripts/tools/gmd_tool.py versions                  # 查看可用版本
python3 scripts/tools/gmd_tool.py update                    # 下载最新版本（约 30 MB）
python3 scripts/tools/gmd_tool.py update --version 2026_06  # 固定某个版本
```

生成的文件（都已 gitignore）：

| 文件 | 内容 |
|---|---|
| `cache/GMD_<版本>.csv` | 整个版本的面板（长表，每行一个国家-年份） |
| `cache/raw/<变量>_<版本>.csv` | 用 `gmd_tool.py raw` 取过的单变量各来源原始值 |
| `metadata.yaml` | 版本号、下载时间、行数、国家数、年份范围、变量列表、引用 |
| `varlist.csv` | 变量、单位、定义 |
| `countries.csv` | ISO3、国家名、收入组、首末年份 |

同一个版本只下载一次；已发布的版本文件不会再修改。

## 读取

```python
import lib

# 宽表：DatetimeIndex（每年 1 月 1 日，与 nbs_a 相同），列名 <变量>_<ISO3>
df = lib.load_gmd(["CHN", "USA", "JPN"], ["rGDP", "CPI", "strate"], start=1960)

# 长表（ISO3, countryname, year, 变量…），面板 VAR / 面板回归用
panel = lib.load_gmd(["CHN", "USA", "DEU", "JPN", "GBR"], ["rGDP", "infl"], wide=False)

# 固定版本（研究日志里要记录版本号；df.attrs["gmd_version"]）
df = lib.load_gmd("CHN", "rGDP", version="2026_09")

# 与其他来源合并时，用 cache-on-fetch fetcher
lib.fetch_data(api="gmd", series={"gdp_chn": "CHN:rGDP", "cpi_usa": "USA:CPI@2026_09"},
               dataset_id="global_annual")
```

`lib.load_dataset(source="gmd", ...)` 不可用（GMD 不是单一时间序列宽表），会提示改用 `load_gmd`。

## 使用注意

1. **年度频率。** 只有年度数据。月度 / 季度分析用 FRED、国家统计局 `nbs_m` / `nbs_q` 或 DBnomics。
2. **单位。** 多数水平量是"百万本币"（`millions of LC`），跨国比较用 `_USD` 或 `_GDP` 口径；
   `rGDP_USD` 用 Atlas 法换算。CPI、HPI、REER 是 2015 = 100 的指数。
3. **拼接。** 长序列由多个来源按比例衔接，来源切换处可能有水平断点或口径变化。
   `gmd_tool.py raw <变量> --country <ISO3>` 可以查看每个来源的原始值、`source` 列（该年采用的来源）
   和 `source_change` 标记；做长样本研究时要检查断点。
4. **缺口。** 早期样本常有间断（如中国 rGDP 1661–2025 年只有 143 个观测值）。先用
   `gmd_tool.py coverage CHN USA --vars rGDP CPI` 看每个序列的起止年份和缺口数，再定样本。
5. **修订。** 新版本会修订历史值并增加来源；同一研究自始至终用同一版本，并在研究日志里记下版本号。
