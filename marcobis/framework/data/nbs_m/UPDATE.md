# 更新国家统计局月度面板（nbs_m）

`dataset.csv` 不随框架分发。第一次使用时，以及以后每次要更新时，在**工作区根目录**运行：

```bash
python3 scripts/tools/nbs_update.py --panel nbs_m
```

脚本只依赖 numpy、pandas、PyYAML，用标准库联网，不需要 API key。它逐个下载 `panel.yaml`
中定义的序列，每行打印 ✓ 或 ✗，最后输出一段 JSON 汇总。月度面板 32 个序列加 5 个派生序列；服务器响应正常时
几分钟可以完成，服务器繁忙时可能要十几分钟。

## 更新频率

国家统计局通常在每月中旬发布上月的价格、生产、需求数据，月末发布 PMI。建议在每月 20 日之后
更新一次。NBS 会修订历史数据，所以每次都全量重新下载，不做增量更新。

## 生成的文件

| 文件 | 内容 |
|---|---|
| `dataset.csv` | 清洗后的数据 + 派生序列。`lib.load_dataset(source="nbs_m", ...)` 读这个文件 |
| `raw.csv` | 只做了分段拼接、未清洗的原始数据，用来核对清洗步骤 |
| `series_info.csv` | 每列的中文名、分组、单位、清洗步骤、建议变换（FRED 编码）、是否季调、样本起止、样本内缺失期数 |
| `transform_codes.csv` | FRED-MD 格式的建议变换编码，`lib.load_dataset` 会读进 `df.attrs` |
| `metadata.yaml` | 版本（下载日期）、每个序列的来源目录 / 分段表 / 指标键、重叠期冲突、定基指数核对（`chain_check`）、失败的序列 |

## 清洗规则

见 `panel.yaml` 开头的字段说明，以及 `scripts/lib/preprocess/china.py` 的 docstring。要点：

- **分段表拼接**：同一指标的多张时段表（如 CPI 的"(-2015)""(2016-2020)""(2021-2025)""(2026-)"）
  按指标编码拼接；重叠期取较新的表，冲突写进 `metadata.yaml` 的 `overlap_conflicts`。
- **累计值转当月值**（`cumulative_to_period`）：1–2 月合并公布的年份，把合计平均拆到 1、2 月。
- **累计值口径检查**（`monotone: true`）：打开后，某年已公布的累计值只要出现下降，就把这一年的
  当月值整年记缺失，年份写进 `metadata.yaml` 的 `nonmonotone_years`，运行时打印一行 `!` 提示。
  目前只对 `fiscal_expenditure` 打开（见下一节）。
- **1 月增长率填补**（`fill_january`）：1 月未公布的增长率序列，用 1–2 月累计同比（即 2 月值）
  填补，填补的日期记在 `metadata.yaml`。
- **定基价格指数**（`chain_index`）：环比连乘，环比缺失的早期用同比回推，基期 2020=100。

除 PMI 外，序列都**未经季节调整**。

## 财政支出的口径问题

国家数据平台"财政/国家财政预算支出"表（`fiscal_expenditure`）前后口径不一：

- **累计值**：2020 年及以前，1—11 月的"累计值"多为**当月值**，只有 12 月是全年数，而且各年
  做法不同（2010、2011 年连 12 月也是当月值；2019 年是混合的）。月度加总与年度数（`nbs_a`
  的 `fiscal_expenditure`）有的年份相差上万亿元。直接差分会得到 90 多个负的当月支出。
  `monotone: true` 检测把 1998—2020 年整年记缺失，**可用样本从 2021 年 1 月开始**。
  2021 年起累计值逐月单调，12 月值与年度数一致。
- **2021 年 1—2 月**：累计值 19720 亿元，约为 2022 年同期（38227 亿元）的一半，3 月又跳到
  58703 亿元，疑似也不是完整的 1—2 月累计。检测抓不到这种情况（数值仍然单调），换算出的
  2021 年 1、2、3 月当月值使用前要核对；做同比时 2022 年 1—3 月也会受影响。
- **累计增长**（同表指标键 `81e3e9710c06441999390e78dfc5e84a_12`，面板未收录）：2018 年及以前
  多为当月增速，2019 年起才是平稳的累计增速，12 月值与年度增速一致。自己取这个指标时，
  只用 2019 年及以后。

"财政/国家财政预算收入"表（`fiscal_revenue`）各年累计值都正常，不受影响。

核对方法：

```bash
python3 scripts/tools/nbs_update.py --panel nbs_m --only fiscal_expenditure
```

然后看 `raw.csv` 中各年 1—11 月是否单调、`metadata.yaml` 中 `fiscal_expenditure` 的
`nonmonotone_years`。

## 加减序列

编辑 `panel.yaml`。找目录和指标键：

```bash
python3 scripts/tools/nbs_tool.py browse 月度 "工业"
python3 scripts/tools/nbs_tool.py search 月度 粗钢
python3 scripts/tools/nbs_tool.py indicators 月度 "工业/工业主要产品产量/粗钢"
```

然后只更新新加的列（其他列保留）：

```bash
python3 scripts/tools/nbs_update.py --panel nbs_m --only steel
```

## 出错时

- **某个序列 ✗"找不到目录"**：NBS 调整了目录名称。用 `nbs_tool.py browse` 逐级找到新路径，
  改 `panel.yaml`。目录缓存过期时加 `--refresh-catalog`。
- **"人机验证页" / `NBSBlockedError`**：请求过密，网站防火墙暂时限制了本机 IP（通常几个小时）。
  脚本已自动停止，已有的面板文件不受影响。过几个小时再运行；一次只运行一个下载进程，不要尝试
  绕过验证。
- **HTTP 403 / 超时**：网站防火墙或网络问题。在浏览器里打开 https://data.stats.gov.cn/ 确认
  能访问，稍后再试。不要提高请求频率。
- **定基指数 `chain_check` 偏差较大**（例如超过 0.3 个百分点）：说明同比、环比在某段时间不一致
  （常见于口径调整的年份），使用前检查 `raw.csv`。

## 参考

- 国家数据：https://data.stats.gov.cn/
- 统计制度和指标解释：国家统计局官网"统计数据 → 指标解释"栏目
