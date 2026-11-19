---
name: stata-diagnose
description: >-
  用"定义症状 → 复现 → 最小化 → 列假设 → 插桩定位 → 修复"的流程，找出 Stata 实证结果出错或
  报错的根本原因，而不是乱试乱改：先钉住期望与实际，稳定复现，剪出最小可复现例子（MWE），
  列出并收敛候选原因，用二分插桩定位到具体行，在根源处做最小修复并加一条防护断言，写诊断报告。
  针对 Stata 常见的静默错误：字符串 / 数值类型与 float 精度、缺失值 `.` 比较、merge m:m 与重复键、
  聚类与权重类型、共线被 omitted、singleton、不收敛、排序与种子、ado 和 Stata 版本差异。用户说
  "回归结果不对"、"这个数怎么变了"、"do-file 报错"、"复现不出来"、"昨天还能跑"、"这个系数看着
  不对"、"帮我 debug Stata"时使用；用户说"只诊断不改"或加 `--no-fix` 时只诊断、不改文件。
---

# /stata-diagnose —— 找出错误结果的根本原因

找出一个分析为什么报错、算错、或对不上，用结构化的排查流程，而不是零散地改。

纪律只有两条：**复现之前不改代码；说清原因之前不修。** 一个"症状消失了但说不出为什么"的修改，就是把错误数字洗进发表表格的方式。

## 什么时候用

- 回归系数/标准误/N 和预期不一样，或者什么都没改却变了
- do-file 报错，但 `r(xxx)` 指向的不是真正原因
- 结果复现不了：换机器、换 Stata 版本、更新 ado 后数字变了
- 讲义/论文里的数字和重跑出来的对不上

**只针对一个症状：一个错数字或一次失败的运行。** 没有具体症状的代码审查不是这个 skill 的事。

运行 Stata：用本 skill 自带的 `scripts/run_stata.sh`（在本 skill 的资源目录下，即加载 skill 时给出的 base directory），在项目根目录执行：
```bash
bash <skill目录>/scripts/run_stata.sh <file>.do
```
它会自动找到本机 Stata（找不到时设置环境变量 `STATA_BIN`），以批处理模式运行，把批处理 log `<file>.log` 放在 do-file 旁边，并打印 log 路径、第一个 `r(###)` 错误码及其前文、共线 / singleton / 不收敛 / 奇异方差矩阵 / 完全预测等警告和 log 末尾若干行；有错误时退出码为 1。`run_stata.sh --version` 查看本机 Stata 版本。
跑完一定读 log，必要时 `grep -n "^r(" <file>.log` 找错误码。

---

## Step 0 —— 先复述"约定"，再动手

提出任何修改前，用 3–5 条说明，然后**停下等用户确认**：

1. 这段代码/这个回归本来应该做什么（数据单位、样本、设定）
2. 用户说哪里坏了
3. 用户的场景是否在约定范围内（调用方式不对，不算被调用代码的 bug）
4. 正确的行为应该是什么
5. 什么证据能判定

---

## Phase 0 —— 钉住症状（期望 vs. 实际）

- **期望：** 认为正确的值，以及**依据**（上次运行的 log、论文表格、手算、理论符号）
- **实际：** 现在得到的值或报错，**原样复制**（完整错误信息，不要转述）
- **容差：** 按期望值的来源定：
  - 同机器上次运行 → 机器精度 + 显示位数
  - 已发表表格 → 四舍五入 + 约 1e-3
  - 手算 → 约 0.01
  - 理论预测 → 经济显著性范围，不是小数位

不追 1e-12 的浮点噪声，也不放过 5% 的差距。说不出期望和实际 → 这是"理解"问题不是"诊断"问题，先问清楚。

## Phase 1 —— 稳定复现

1. 固定所有不确定性：`version`、`set seed`、`set sortseed`（Stata 18 起 `sort` 并列时顺序随机，`bysort ... : gen x = _n` 这类代码会受影响）、工作目录。
2. 记录环境：
   ```stata
   about
   version
   which reghdfe
   which ftools
   which esttab
   ado dir
   ```
3. 连续跑两次最小单元，确认**每次都**出同样的错。时有时无本身就是一个假设（种子没设、`sort` 并列、`merge` 后顺序依赖），带入 Phase 3。

## Phase 2 —— 缩小到最小可复现例子（MWE）

- **数据：** `keep if` 到最少的个体/年份/变量仍能复现；必要时 `preserve` + `keep` + `save mwe.dta`
- **代码：** 把 do-file 剪到"从输入到错误输出"的最短路径，症状没了也不影响的部分全注释掉
- 每删一段症状还在 → 信息；删一段症状消失 → 更强的信号。都记下来。

MWE 本身就是交付物，即使最后修复很简单。

## Phase 3 —— 列假设（先全列出来，再排序）

先写出候选原因清单，再逐个测。下面这些在 Stata 里**都不报错**，只会悄悄算错：

- **类型**
  - 数值被读成字符串（`destring` 失败或带逗号、空格）
  - `float` 精度不够：大 ID、年份×1000、金额，`gen` 默认是 float → 用 `double`
  - 日期是字符串或 `%td`/`%tm` 混用
- **缺失值**
  - `.` 在 Stata 里是**正无穷**：`gen high = (x > 100)` 会把缺失记成 1；`if x > 100` 会把缺失选进来 → 用 `if x > 100 & !missing(x)`
  - 扩展缺失 `.a–.z` 被忽略
  - 不同回归的 N 不同：listwise deletion 让样本中途变了
- **merge 与数据形状**
  - `merge m:m` 几乎永远是错的（它不是笛卡尔积，而是按顺序配对）
  - 本该 `1:1` 的键其实有重复（`duplicates report id year`）
  - `_merge` 没检查、没 `assert`
  - 以为面板平衡其实不平衡；`reshape` 后丢了行
- **设定**
  - 聚类层级不对
  - 固定效应重复吸收（`absorb(state)` 又放了 `i.state`）
  - `L.`/`F.` 算子在 `xtset` 时间不连续时产生缺失
  - 交互项写成 `i.a#i.b` 但漏了主效应，或 `c.`/`i.` 前缀用错
  - 因子变量的基准组和预期不同
- **坏控制**：控制了处理后才发生的变量、中介变量或处理的后代。表现：加入某个控制后系数往"不该去的方向"移动或不合理地变小。
- **数值与收敛**
  - `(omitted because of collinearity)`：关键变量被删掉了
  - `reghdfe` 删掉了 singleton，样本变小
  - `convergence not achieved`、`not concave`、`backed up`
  - `variance matrix is nonsymmetric or highly singular`
  - Logit/Probit 完全分离（`note: x != 0 predicts success perfectly`）
- **权重**：`[fw]` `[pw]` `[aw]` `[iw]` 用混（标准误完全不同）；权重有缺失或为 0 被悄悄删掉；`collapse` 时没带权重
- **样本**：`keep if`/`drop if` 放在变换之前还是之后；异常值规则前后不一致；`by` 组内 `_n`/`_N` 依赖排序
- **注释吞代码**：注释里的 `/*`（如 `* 输出到 out/*`）开启块注释，后面的命令全被跳过，log 里看不到它们的输出，也没有错误码
- **环境**：`reghdfe` 新旧版本（6.x vs. 新版）默认值不同；`ssc` 包更新；Stata 版本（`version` 语句没写）；字符编码（中文变量标签、`unicode translate`）

真正难判断时，如果当前环境支持子代理，可以对排名靠前的几个假设各开一个子代理，在 MWE 上各自尝试证实自己负责的假设，然后汇报；不支持时就按排名逐个验证。

### Phase 3b —— 收敛假设（别把猜测洗成结论）

每个假设汇报 `{假设, 支持证据, 反对证据, 置信度, 一句话结论}`，然后：

- **一个明显胜出**（高置信、其他被否定）→ 进 Phase 4 确认机制
- **前两名接近**（相差 ~20 个百分点以内）→ 不选，用 Phase 4 的插桩区分
- **都不到 ~50%** → 报告不确定性，问用户；不要凭抛硬币改代码

## Phase 4 —— 插桩定位（二分，而不是盯着看）

- **二分流程：** 在数据流中点检查中间值，判断问题在上游还是下游，重复。`log2(n)` 步找到出问题的那一行。
- **二分历史：** "昨天还能跑" → 和最后一次正确的 log/do-file 对比（`diff` 两个版本），找出引入问题的改动。
- **在每一步插诊断命令：**
  ```stata
  count                                   // 每个变换前后的观测数
  describe x                              // 类型（str? float? double?）
  misstable summarize x y z               // 缺失模式
  tab group, missing                      // 类别有没有悄悄消失
  duplicates report id year               // 键是否唯一
  isid id year                            // 不唯一直接报错
  tab _merge                              // merge 结果
  summarize w, detail                     // 权重：范围、是否有 0/缺失
  pwcorr x1 x2 x3                         // 意外的共线
  ereturn list                            // e(N), e(converged), e(rank), e(N_clust)
  display e(N) "  " e(N_clust) "  " e(converged)
  ```
  **观测数突然下降、类别消失、相关性跳升、权重变稀疏、`e(converged)==0` 的那一步，就是出事的地方。**

Phase 4 结束时给出一句话根本原因：具体哪一行/哪一步，什么机制。

## Phase 5 —— 修复与验证（并加防护）

**置信门槛（防洗白规则）：** 根本原因没被点名、机制没讲清，就不改。Phase 3b 是接近平局时，按 `--no-fix` 处理：列出候选，问用户。

未加 `--no-fix`、用户也没说只诊断时：

1. 在**根源处**做**最小**修改，不在下游打补丁掩盖（修好 merge 的键，而不是事后 `duplicates drop`）
2. 重跑 MWE，确认 `实际 == 期望`（在 Phase 0 容差内）
3. 重跑**完整** do-file 及依赖它的后续 do-file，确认没有别的数字被带着变了；如果结果进了讲义/论文的表，一并核对
4. 加一条**防护断言**，防止同类错误再发生：

   | 错误类型 | 一行防护 |
   |---|---|
   | 类型 | `confirm numeric variable x`；需要精度的 `gen double` |
   | 缺失值比较 | `assert !missing(x)`；比较时写 `& !missing(x)` |
   | merge | `merge 1:1 id year using f, assert(match)` 或 `isid id year` 放在 merge 前 |
   | 样本变化 | 回归后 `assert e(N) == N_expected`（事先 `scalar N_expected = ...`） |
   | 权重 | `assert w > 0 & !missing(w)` |
   | 收敛 | `assert e(converged) == 1` 再用估计结果 |
   | 排序依赖 | `sort id year, stable` 或 `set sortseed` |
   | 环境 | do-file 第一行写 `version`（本机主版本，如 `version 18`）；记录 `which reghdfe` 版本 |

   只建议这一条防护，不顺手装一整套测试。

加 `--no-fix`（或用户说只诊断、不改）时：点名根本原因、写好报告后停止，不改任何源文件。

---

## 示例

改了一版数据后，TWFE 系数从 0.123 变成 0.087，设定没动。

```stata
* Phase 1 —— 复现：同一 do-file 连跑两次，都是 0.087。稳定。

* Phase 2 —— MWE：只留 1956–1965、5 个州仍能复现。
*            剪到：use → merge 控制变量 → reghdfe。merge 之后问题还在。

* Phase 4 —— 插桩：merge 前后观测数
use divorce_panel, clear
count                                   // 1683（51 州 × 33 年，符合预期）
merge m:m state year using controls     // 原作者写成了 m:m（用 1:1 会直接报错）
count                                   // 1716  <-- 多了 33 行！
preserve
    use controls, clear
    duplicates report state year        // controls 里有一个州的 state-year 出现两次
restore

* 根本原因：新版 controls.dta 里有一个州出现两次（州代码改过名），
* merge m:m 不报错，按顺序配对，这个州的每一年都多出一行，
* 回归里这个州的权重翻倍。

* Phase 5 —— 在根源修：把 controls.dta 的重复州代码统一，而不是事后 duplicates drop
* 重跑：系数回到 0.123；后续事件研究 do-file 也重跑核对，没有别的数字变。

* 防护：merge 前确认键唯一，并用 1:1 + assert
use controls, clear
isid state year
use divorce_panel, clear
merge 1:1 state year using controls, assert(match master)
```

## 报告

写到 `quality_reports/diagnoses/YYYY-MM-DD_<slug>.md`（先 `mkdir -p quality_reports/diagnoses`）。报告里可能有真实数据和路径，只在项目内部用。内容：

- **症状：** 期望 vs. 实际（+ 容差）
- **MWE：** 最小的数据和代码
- **根本原因：** 具体行/步骤 + 机制
- **修复：** 实际改动（`--no-fix` 时为建议改动）
- **验证：** MWE 与完整重跑结果
- **防护：** 能提前抓住它的那条断言

聊天里先用一句话说根本原因，再给摘要。

## 先审查、再修复

1. **审查（只读）：** 列一张表 `严重性 | 文件:行 | 问题 | 我实际跑过的证据 | 建议修改`。没通过运行验证的标 **UNVERIFIED**。不改任何东西。
2. **修复：** 只修用户选中的行。

`--no-fix` 只做第 1 步。

## 结束条件

| 结果 | 做法 |
|---|---|
| 根本原因已点名（高置信），已修复并验证 | 报告原因 + 改动 + 防护 |
| `--no-fix` | 点名原因、写报告，不改源文件 |
| Phase 0 卡住（说不出期望值） | 停下，问期望值 |
| Phase 1 卡住（复现不了/结果随机） | 把"不确定性"本身作为结论报告，说明如何让分析可复现；不盲改 |
| Phase 3b 接近平局或都 <50% | 列出竞争假设，问用户；不改 |

## 不做的事

- 没有具体症状的代码审查
- 一次性核对整篇论文所有数字
- 搭测试框架
- 提交/备份文件

## 相关

- 从头做一个分析 → `stata-data-analysis` skill（同仓库的 `statadataanalysis` 插件）

## 来源

改编自 Pedro H. C. Sant'Anna 的 [claude-code-my-workflow](https://github.com/pedrohcgs/claude-code-my-workflow) 中的 `/diagnose`（MIT 许可，许可原文见本目录 `UPSTREAM-LICENSE.txt`）。
