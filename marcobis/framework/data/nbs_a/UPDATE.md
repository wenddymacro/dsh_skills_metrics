# 更新国家统计局年度面板（nbs_a）

在**工作区根目录**运行：

```bash
python3 scripts/tools/nbs_update.py --panel nbs_a
```

生成的文件、加减序列和出错处理与月度面板相同，见 [`../nbs_m/UPDATE.md`](../nbs_m/UPDATE.md)。

## 更新频率

年度数据在次年年初公布初步数，《中国统计年鉴》（通常在当年 9–10 月）公布后会有修订，GDP 等还会随经济普查
回溯修订。建议在统计年鉴发布后更新，用于正式结果之前再更新一次。

## 年度面板的内容

| 分组 | 列 |
|---|---|
| 生产法核算 | `gdp`、`gni`、`gdp_primary` / `gdp_secondary` / `gdp_tertiary`、`gdp_pc`、`gdp_index`（上年=100） |
| 支出法核算 | `gdp_exp`、`consumption`、`hh_consumption`、`gov_consumption`、`capital_formation`、`gfcf`、`inventory_change`、`net_exports` |
| 人口与就业 | `population`、`urban_population`、`employment`、`registered_unemployment`、`avg_wage`、`real_wage_index` |
| 价格 | `cpi_yoy`、`ppi_yoy`、`fai_price_yoy`（上年=100），以及官方定基指数 `cpi_1978`（1978=100）、`ppi_1985`（1985=100） |
| 财政、外贸、金融、投资 | `fiscal_revenue`、`fiscal_expenditure`、`exports_cny` / `imports_cny`、`exports_usd` / `imports_usd`、`usdcny`、`m2`、`m1`、`tsf_flow`、`fx_reserves`、`fai_total`、`re_investment` |
| 派生 | `real_gdp_growth`、`cpi_inflation`、`gdp_deflator_yoy` |

## 年度面板的特点

- **日期约定**：当年 1 月 1 日。
- **官方定基指数**：年度数据有官方的定基价格指数（CPI 1978=100、PPI 1985=100），不需要像月度面板那样
  自己链接。
- **登记失业率**：`registered_unemployment` 是城镇登记失业率（平台上只到 2021 年），口径与月度面板的调查
  失业率不同，变动很小，一般不适合作为劳动力市场松紧的度量。
- **汇率**：`usdcny` 是 100 美元合人民币元数（年平均价），换算成"1 美元合人民币"要除以 100。
- **社会融资规模**：`tsf_flow` 是年度增量（流量），不是存量。
- **样本起点**：各序列起点不同（国民经济核算、人口、财政、外贸等多数从 1950 年代初开始，汇率和登记失业率从 1978 年，货币供应量
  从 1990 年，社会融资规模从 2002 年开始），见 `series_info.csv`。
