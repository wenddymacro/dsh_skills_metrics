---
name: stata-data-analysis
description: >-
  用 Stata 跑完整的实证分析流程：读数据 → 探索 → 清洗 → 回归 → 可发表的表格与图。
  先实际读数据给出 Pre-Flight 报告，再写编号 do-file（`analysis_<topic>/01_xxx.do`），
  批处理运行并逐条读 log 查错误码、共线、singleton、不收敛和样本量变化；用 reghdfe / esttab /
  coefplot 输出 .tex 与 .rtf 表、.pdf 与 .png 图，记录设定台账；按 DID / IV / RDD / Logit 等识别
  策略补齐必须的检查。用户说"分析这个数据"、"跑个回归"、"看看这个 dta/csv"、"做个完整的实证"、
  "出描述统计和回归表"、"用 Stata 做实证"，或给出 .dta / .csv / .xlsx 要实证结果时使用。
---

# Stata 数据分析工作流

用 Stata 端到端跑一个实证分析：加载、探索、估计、输出可直接放进论文或 Beamer 的表和图。

**输入：** 用户的请求 —— 数据路径（如 `divorce_panel.dta`）或分析目标（如"用 TWFE 估计单方离婚法对离婚率的影响，按州聚类"）。

---

## 约定

- **目录：** 每个主题一个文件夹 `analysis_<topic>/`，do-file 编号命名 `01_xxx.do`、`02_xxx.do`；所有输出放 `analysis_<topic>/out/`。
- **运行方式：** 工作目录是当前任务的项目根目录（数据所在的工作区），do-file 里一律用**相对路径**，不写 `cd "/Users/..."`。
- **运行 Stata：** 用本 skill 自带的 `scripts/run_stata.sh`（在本 skill 的资源目录下，即加载 skill 时给出的 base directory），在项目根目录执行：
  ```bash
  bash <skill目录>/scripts/run_stata.sh analysis_<topic>/NN_name.do
  ```
  它会自动找到本机 Stata（找不到时设置环境变量 `STATA_BIN`，例如 `/Applications/StataNow/StataMP.app/Contents/MacOS/stata-mp`），以批处理模式运行，把批处理 log `NN_name.log` 放在 do-file 旁边（不会堆在项目根目录），并打印：log 路径、第一个 `r(###)` 错误码及其前文、共线 / singleton / 不收敛 / 奇异方差矩阵 / 完全预测等警告、log 末尾若干行。有错误时退出码为 1。
  `run_stata.sh --version` 查看本机 Stata 版本；`--tail N` 控制打印的末尾行数。do-file 路径不能含空格。
  do-file 内部另开 `log using "analysis_<topic>/out/NN_name.log", replace text` 作为正式日志。
- **跑完必须读 log**：看 `run_stata.sh` 的输出，必要时再 `grep -n "^r(" <log>` 和打开正式日志，不能只看"运行结束"就报告成功。
- **注释用中文**，变量名、命令、标签（label）用英文。
- **注释里不要出现 `/*`、`*/`**（例如写路径 `out/*` 或 `diagnostics/*`）：即使在 `*` 注释行里，`/*` 也会开启块注释，悄悄跳过后面整段代码，不报任何错。
- **Beamer 提示：** 回归命令写进 `.tex` 幻灯片时，`#`（如 `i.state#c.year`）要写成 `\#`，或者 frame 加 `[fragile]`。

---

## 工作流程

### Phase 0：Pre-Flight 报告（写代码前必须先做）

先用 Stata 实际读一遍数据（`describe`、`codebook, compact`、`misstable summarize`），再在回复中给出：

```markdown
## Pre-Flight 报告

**数据：** [路径]
- 变量（来自 describe，不要凭空猜）：[列表]
- 观测数：[N]；面板维度：[个体变量 × 时间变量，是否平衡]
- 关键类型：[如 outcome=double, treatment=byte 0/1, state=带值标签的数值 / 字符串]
- 缺失：[关键变量缺失比例]
- 唯一标识：[`isid id year` 是否通过]

**任务理解：** [一句话复述用户要什么]

**计划：** [3–5 条 do-file 结构]

**需要的外部命令：** [reghdfe / ftools / estout / coefplot / csdid ... 已装或需 ssc install]
```

读不到文件、格式打不开、关键变量不存在 → 停下来问用户，不要继续。

### Phase 1：Setup 与数据加载

1. do-file 头部注释：标题、数据来源、内容、输入、输出、运行命令。
2. 开头固定为（`version` 写本机 Stata 的主版本，用 `run_stata.sh --version` 查；下面以 18 为例）：
   ```stata
   version 18
   clear all
   set more off
   capture log close
   set seed 20261111          // YYYYMMDD，只设一次
   log using "analysis_<topic>/out/NN_name.log", replace text
   ```
3. 检查并按需安装外部命令（`capture which reghdfe; if _rc ssc install reghdfe`），**但安装前告诉用户**。
4. 加载数据后立刻做基本断言：
   ```stata
   isid id year                       // 面板唯一键
   assert inlist(treat, 0, 1)         // 处理变量取值
   ```

### Phase 2：探索性分析（EDA）

- **描述统计：** `summarize, detail`；`tabstat ..., stat(n mean sd min p50 max)`
- **面板结构：** `xtset`、`xtdescribe`、`xtsum`
- **缺失：** `misstable summarize`、`misstable patterns`
- **分布与关系：** `histogram`、`twoway scatter`、`pwcorr, sig`
- **时间趋势：** 面板数据画分组均值随时间变化（`collapse` 后 `twoway line`）
- **处理/对照比较：** 处理前均值对比（`ttest` 或 `balancetable`/`iebaltab`）
- **DID 类数据额外：** 处理时点分布（首次处理年份 `tab`）、从未处理组、样本首年即已处理组

诊断图存到 `analysis_<topic>/out/diagnostics/`（先 `capture mkdir`）。

### Phase 3：主回归

- **命令选择：** 面板/多维固定效应用 `reghdfe`；截面用 `regress`；离散因变量用 `logit`/`probit`（报告边际效应 `margins, dydx(*)`）；IV 用 `ivreghdfe`/`ivregress 2sls`（报告第一阶段 F）。
- **标准误：** 聚类到处理发生变化的层级，并在注释里**写明理由**；聚类数少于 ~40 时提示可用 wild cluster bootstrap（`boottest`）。
- **逐步加设定：** 从最简单的开始，逐步加控制变量/固定效应/趋势项，每个都 `eststo`。
- **效应大小：** 除了原始系数，报告相对于因变量均值（或标准差）的大小：`estadd scalar ymean = r(mean)`。
- **单例与共线：** 留意 `reghdfe` 删掉的 singleton 和被 omitted 的变量，出现时在报告里说明。

#### 设定台账（每个跑过的设定都记，不管留没留）

每估计一个设定（包括放弃的、报错的），往 `quality_reports/spec-ledger.md` 追加一行。目的是让"你还试过什么"有据可查，不是限制尝试。

- **只追加，不修改、不删除。** 更正就新加一行。
- **状态** 填 `kept` / `dropped` / `failed`；非 kept 的写明原因。
- 设定里的 `|` 写成 `\|`；含 Stata 局部宏反引号（`` `x' ``）的设定用双反引号包裹：``` `` reg y `controls' `` ```。

```bash
LEDGER=quality_reports/spec-ledger.md
mkdir -p quality_reports
[ -f "$LEDGER" ] || printf '%s\n' "# Specification ledger" "" \
  "每个估计过的设定一行，保留或放弃都记，跑一个记一个。不修改旧行，更正另起一行。" "" \
  "| Date | Do-file:line | Outcome | Specification | Sample | Status | Why | Estimate |" \
  "|---|---|---|---|---|---|---|---|" > "$LEDGER"
printf '| %s ' "$(date +%F)" >> "$LEDGER"
cat >> "$LEDGER" <<'EOF'
| analysis_divorce/02_divorce_twfe.do:85 | div_rate | `reghdfe div_rate udl, absorb(state year) vce(cluster state)` | 1956-1988, 51 states | kept | 主设定 | 0.123 (0.081) |
EOF
```

### Phase 4：可发表的输出

**表格（`esttab`）：**
- 同时导出 `.tex`（论文/Beamer 用，`booktabs`）和 `.rtf`（Word 用）
- 包含：系数、括号内标准误、显著性星号、N、R²（within R² 用 `r2_within`）、固定效应与聚类说明行（`estadd local fe "Yes"`）、因变量均值
- 用 `label` 显示变量名，`mtitles` 标模型名，`addnotes` 写聚类层级与星号含义

```stata
esttab m1 m2 m3 using "analysis_<topic>/out/table2_regression.tex", replace ///
    booktabs label se star(* 0.10 ** 0.05 *** 0.01) b(3) se(3) ///
    keep(treat) stats(N r2_within ymean fe_unit fe_time, ///
        labels("Observations" "Within R$^2$" "Mean of Dep. Var." "Unit FE" "Year FE") ///
        fmt(0 3 3 0 0)) ///
    mtitles("(1)" "(2)" "(3)") nonotes ///
    addnotes("Standard errors clustered by state in parentheses." ///
             "* p<0.10, ** p<0.05, *** p<0.01")
esttab m1 m2 m3 using "analysis_<topic>/out/table2_regression.rtf", replace ///
    label se star(* 0.10 ** 0.05 *** 0.01) b(3) se(3)
```

**图（`graph`/`coefplot`）：**
- 统一风格：`set scheme s2color` 或项目指定 scheme（Stata 18 可用 `stcolor`）
- 坐标轴标题写清含义和单位
- 同时导出 `.pdf`（Beamer）和 `.png`（预览），宽度显式指定：
  ```stata
  graph export "analysis_<topic>/out/fig_event_study.pdf", replace
  graph export "analysis_<topic>/out/fig_event_study.png", replace width(2000)
  ```

### Phase 5：保存与自查

1. 关键中间数据存 `analysis_<topic>/out/*.dta`（`compress` 后 `save, replace`）；估计结果用 `estimates save` 存 `.ster`，方便以后出表不用重跑。
2. `log close`，然后读 log：
   - `grep -n "^r(" log` —— 任何错误码都要处理
   - 检查 `(omitted because of collinearity)`、`singleton observations dropped`、`convergence not achieved`、`variance matrix is nonsymmetric or highly singular`
   - 核对每个回归的 N 是否与预期一致（样本有没有悄悄变小）
3. 对生成的 do-file 自查一遍：相对路径、没有硬编码的样本限制数字（用 `local` 定义）、种子只设一次、每个 `preserve` 都有对应 `restore`。

---

## Do-file 模板

```stata
*=====================================================================
* [标题]
* 数据：[来源]
* 内容：描述统计 → 主回归 → 稳健性 → 出表出图
* 输入：[数据文件]
* 输出：analysis_<topic>/out/[表、图、log]
* 运行：stata-mp -b do analysis_<topic>/NN_name.do
*=====================================================================
version 18
clear all
set more off
capture log close
set seed 20261111
capture mkdir "analysis_<topic>/out"
log using "analysis_<topic>/out/NN_name.log", replace text

* 样本参数（不要散落在代码里）
local y        "outcome"
local d        "treat"
local controls "x1 x2 x3"
local t0 1990
local t1 2010

*---------------------------------------------------------------------
* 1 数据加载与检查
*---------------------------------------------------------------------
use "data.dta", clear
isid id year
keep if inrange(year, `t0', `t1')

*---------------------------------------------------------------------
* 2 描述统计
*---------------------------------------------------------------------

*---------------------------------------------------------------------
* 3 主回归
*---------------------------------------------------------------------

*---------------------------------------------------------------------
* 4 表与图
*---------------------------------------------------------------------

log close
```

---

## 方法相关的额外检查（按识别策略）

| 方法 | 必须额外报告/检查 |
|---|---|
| TWFE / DID | 处理时点分布；交错处理时提示 TWFE 偏误，补 Goodman-Bacon 分解（`bacondecomp`）与稳健估计量（`csdid`、`did_imputation`、`jwdid` 或 Stata 18 `xthdidregress`）；事件研究图 + 处理前系数联合检验 |
| IV | 第一阶段系数与 F（`ivreghdfe` 报告的 KP F）；弱工具变量稳健推断（`weakiv`）；简约式 |
| RDD | `rdrobust` 主估计；`rdplot`；带宽敏感性；密度检验 `rddensity`；协变量平衡 |
| Logit/Probit | 报告平均边际效应，不只报原始系数；完全预测/分离提示 |
| 少聚类 | `boottest` wild cluster bootstrap p 值 |

只做用户要求的方法；上表是"做了这个方法就别漏了这些检查"，不是要全部跑一遍。

---

## 重要原则

- **照做，不猜。** 用户指定了回归，就跑那个回归；想加别的设定先说明。
- **先看数据再回归。** 描述统计先于回归输出。
- **查问题：** 共线、异常值、完全预测、样本量变化。
- **相对路径。** 一律相对项目根目录。
- **不硬编码。** 样本区间、控制变量组用 `local`/`global` 定义。
- **报告只说 log 里真实出现的数字。** 不凭记忆或估算填结果。

## 长时间运行（bootstrap、模拟、大样本）

预计超过几分钟的 do-file：如果当前环境的 shell 工具支持后台运行，就后台运行 `run_stata.sh`，再隔一段时间查看日志里的关键行，例如：

```bash
grep -nE "^r\(|Number of obs|end of do-file" analysis_<topic>/out/NN_name.log | tail -20
```

给命令设置超过预计运行时间的超时；不要用短间隔的 `sleep` 反复轮询。不支持后台运行时，先告诉用户预计耗时再前台运行。

## 相关

- 数字不对、结果复现不了 → 用 `stata-diagnose` skill（同仓库的 `statadiagnose` 插件）。

## 来源

改编自 Pedro H. C. Sant'Anna 的 [claude-code-my-workflow](https://github.com/pedrohcgs/claude-code-my-workflow) 中的 `/data-analysis`（R 版，MIT 许可，许可原文见本目录 `UPSTREAM-LICENSE.txt`）。
