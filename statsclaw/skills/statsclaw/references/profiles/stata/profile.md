# 语言包：Stata

本目录（`<SKILL>/references/profiles/stata/`）是 Stata 的语言包。组长派发时把本文件路径交给每个角色；每个角色先读"通用部分"，再读"各角色须知"里自己那一节和它列出的文件。

## 文件

| 文件 | 内容 |
|---|---|
| `profile.md` | 本文件：识别、开工检查、写入范围、验证命令、各角色须知、发布检查 |
| `maintainer.md` | **维护者的 Stata 规范**（填写后优先级高于本目录其他文件） |
| `conventions.md` | ado / Mata 编码约定：程序骨架、eclass/rclass、错误码、数值、随机数、依赖、风格 |
| `testing.md` | 验证方法：run_stata.sh、认证脚本、基准命令对照、修改前后对比、包装检查、复现项目 |
| `helpfile-and-packaging.md` | SMCL 帮助文件骨架、`.pkg` / `stata.toc`、发布清单 |
| `pitfalls.md` | 27 条 Stata 静默错误 |
| `simulation.md` | 仿真的 Stata 写法（`simulate` / `postfile`、种子、分块并行） |
| `run_stata.sh` | 找到本机 Stata，批处理运行 do-file，报告 `r(###)` 和静默错误警告 |
| `stata_pkg_check.py` | 命令包静态检查（Python 标准库） |
| `templates/` | `cert_template.do`、`helpfile.sthlp`、`package.pkg` |

## 识别

| 项目类型 | 标志 | 交付物 |
|---|---|---|
| **命令包** | `*.ado`、`*.sthlp`，可能有 `*.pkg`、`stata.toc`、`*.mata`、`l*.mlib` | 可以 `net install` 的命令 |
| **复现 / 分析项目** | 只有 `*.do`，通常有 `master.do` | 能从头跑通、结果可复现的 do-file 链 |

空目录且用户要写新命令时按命令包处理。

## 开工检查（组长做）

1. `bash <本目录>/run_stata.sh --version`。找不到 Stata 时告诉用户：规划可以照常进行，验证需要 Stata 16 及以上版本，请安装或设置 `STATA_BIN`（如 `/Applications/StataNow/StataMP.app/Contents/MacOS/stata-mp`）。
2. 记下项目里现有的 `version` 语句：新代码的目标 `version` 取项目已有的最低版本，没有就用 16，且不高于本机版本。写进 request.md。
3. 记下 ado 所在目录、认证脚本目录（如 `cert/`）、是否有 `.pkg` / `stata.toc`，写进 `.statsclaw/context.md`。

## 写入范围建议

| 角色 | 典型写入范围 |
|---|---|
| builder | `.ado`、`.mata`、`l*.mlib`、认证脚本目录（如 `cert/`）、`.pkg` 中的 `f` 文件清单行 |
| simulator | 仿真目录（如 `sim/`、`simulations/`） |
| scriber | `.sthlp`、README、示例 do-file、`.pkg` 中的 `d` 说明行 |

## 验证命令

| 阶段 | 命令 |
|---|---|
| 运行 do-file | `bash <本目录>/run_stata.sh --tail 40 path/file.do`（在项目根目录执行） |
| 静态检查 | `python3 <本目录>/stata_pkg_check.py <项目根目录>` |
| 认证脚本 | 项目已有的 `cert/*.do` 和 tester 自己写的脚本，逐个用 run_stata.sh 运行 |
| 安装检查 | 临时 PLUS 目录里 `net install`，见 testing.md 第 5 节 |
| 复现项目 | 运行 `master.do`，核对关键数值 |

`run_stata.sh` 退出码：0 无错误，1 有 `r(###)` 错误，2 参数错误或找不到 Stata。它还会列出共线、singleton、不收敛、方差矩阵奇异、完全预测等警告。

## 依赖

需要 `reghdfe`、`ivreg2`、`estout` 等第三方命令时，**任何角色都不自动 `ssc install`**：记录缺哪个、为什么需要，交给组长问用户。

---

## 各角色须知

### planner

读：`conventions.md`、`testing.md`、`pitfalls.md`；仿真流程加 `simulation.md`。

- spec.md 的 API 部分写成 **Stata 命令接口**：完整的 `syntax` 行（varlist 要求、`if`/`in`、支持的权重、每个选项的名字、缩写、类型和默认值、是否允许 `fv`/`ts`）；eclass / rclass；是否 `byable`、是否支持重放；**全部 e() / r() 返回值**（名字、类型、含义，b 和 V 的行列名规则）；每种非法输入的错误码和信息（198、102、111、2000、2001、459、430 等）；依赖；目标 `version`；哪些放 Mata；需要的后估计命令；新增文件要进 `.pkg`。
- test-spec.md 的场景写成**可执行的断言**：数值用 `mreldif()` / `reldif()` 加容差，错误码用 `rcof "命令" == #`，数据不变用 `datasignature`；数据优先用 `sysuse` / `webuse`，或带种子的生成方法。
- 每个场景尽量指定**基准命令**（`regress`、`xtreg, fe`、`ivregress 2sls`、`reghdfe`、`margins`、论文表格、解析解），见 testing.md 第 3 节。
- 从 `pitfalls.md` 挑出与本任务相关的条目，每条写一个场景（缺失值、权重、排序、共线、singleton、不收敛、改动用户数据、调用了本机旧版 ado 等）。
- test-spec.md 里可以写命令的语法和返回值名字（这是接口，不是实现）。
- 文档流程的 spec.md 写清要改的 sthlp 章节、Stored results 要列哪些返回值。

### builder

读：`conventions.md`（必须遵守）、`pitfalls.md`（逐条避开）、`testing.md` 和 `templates/cert_template.do`（写自己的认证脚本用）。

- 第一行 `*! version X.Y.Z  DDmonYYYY`，改动后递增；program 内写目标 `version`；`syntax` 与 spec.md 一字不差。
- `marksample touse` 后所有计算都限定在 touse 样本；临时对象全用 `tempvar` / `tempname` / `tempfile`；排过序加 `sortpreserve`；`generate double`；矩阵运算放 Mata，用 `cholsolve` / `qrsolve`，检查秩。
- eclass 用 `ereturn post b V, esample(...)`，设 `e(cmd)`、`e(cmdline)` 和 spec.md 列出的全部返回值；错误码按 spec.md `exit #`，先 `display as error`。
- 不写死 `set seed`（用 `seed()` 选项）；注释里不出现 `/*`；不写 `cd` 和绝对路径；新增文件写进 `.pkg` 的 `f` 行。
- 认证脚本放项目的认证脚本目录（如 `cert/cert_<cmd>.do`），按模板写：开头 `adopath ++` 项目 ado 目录、`discard`、`which`；每条新改代码路径至少一个数值断言；spec.md 的每个错误码 `rcof` 一次；缺失值、`if`/`in`、每种支持的权重、`datasignature confirm` 各测一次。
- 冒烟检查：只用 run_stata.sh 跑自己的认证脚本，再跑一次 `stata_pkg_check.py` 并修掉 ERROR。不做安装检查。
- implementation.md 写明新版本号、语法和返回值的变化、认证脚本位置和冒烟结果。

### tester

读：`testing.md`（按它的方法做）、`pitfalls.md`、`templates/cert_template.do`。

- 每个脚本开头 `adopath ++` 项目 ado 目录、`discard`、`which <cmd>`，确认测的是项目里的版本，记录 `*!` 版本行。
- 命令包先跑 `stata_pkg_check.py`：ERROR 计为失败，WARN 写进 audit.md。
- 自己的认证脚本放 `<运行目录>/tester/`，把 test-spec.md 每个场景写成 `assert` / `rcof` / `datasignature confirm`；数值结果用 `display "RESULT|场景|指标|" %21.15g 实际 "|" %21.15g 期望 "|容差"` 打进 log。为保证每个场景都跑到，可以把**整个场景**放进 `capture noisily { ... }` 并立即记录 `_rc`，非 0 即该场景失败（这不是吞错，必须如实计入）；绝不 `capture assert`。
- 项目已有的认证脚本全部重跑，作为回归检查。
- 基准命令逐个对照（系数、标准误、N、关键返回值）；基准命令本机没有时注明未执行，不能当作通过。
- 修改前后对比：`git archive <基线> | tar -x -C <运行目录>/tester/before/`（非 git 项目用 `baseline/`），另写脚本 `adopath ++` 指向它。不在项目工作区里 stash 或 checkout。
- 安装检查只装进临时 PLUS 目录（testing.md 第 5 节），不覆盖用户已安装的命令。
- run_stata.sh 报出与场景相关的共线、不收敛、singleton 等警告，而 test-spec.md 没说明这是预期行为时，计为失败。
- 失败路由：数值、错误码、返回值、改动用户数据、回归失败、pkg 清单问题 → builder；帮助文件 SMCL 错误、例子跑不通、版本注释不一致 → scriber；缺 Stata、缺第三方命令 → leader。
- audit.md 的环境信息：`c(stata_version)`、`c(edition_real)`、`c(os)`、`c(processors)`、第三方命令的 `which` 版本行。

### simulator

读：`simulation.md`、`conventions.md`（随机数、`generate double`、注释规则）。

- 单次重复写成 rclass 程序，参数从选项传入；命令调用用 `capture noisily` 包住，失败时 `return scalar failed = 1`。
- 主循环按 sim-spec.md 选 `simulate` 或 `postfile`；`args R scenarios` 控制规模；原始结果存 `sim/out/results.dta`；汇总另写一个 do-file。
- 冒烟运行用 `run_stata.sh sim/sim_main.do 50 <部分场景>`；simulation.md 写明 tester 运行完整仿真和汇总的确切命令。

### scriber

读：`helpfile-and-packaging.md`（帮助文件和打包按它做）、`templates/helpfile.sthlp`、`templates/package.pkg`。

- sthlp 以模板为骨架，Syntax 与 `syntax` 行一字不差；**Stored results 与 ado 实际设置的 e() / r() 一一对应**；Examples 实际跑一遍；Author 的姓名和联系方式只能来自用户或 maintainer.md，不要编造。
- sthlp 版本注释与 ado 的 `*!` 一致；pkg 的 `Distribution-Date` 更新为今天；`.pkg` 的 `d` 说明行由你写，`f` 文件清单行归 builder。
- 用 run_stata.sh 跑 `translate <cmd>.sthlp <临时文件>.txt, translator(smcl2txt) replace`，确认 SMCL 能转换。
- 复现项目按 helpfile-and-packaging.md 第 4 节更新 README。

### reviewer

读：本目录全部 `.md`；可以只读地运行 `stata_pkg_check.py` 核对。

- 对照 `conventions.md` 和 `pitfalls.md` 逐条看改动的 ado / Mata：`*!` 已递增；`version` 不高于目标；`syntax` 与 spec.md 一致；`marksample` / `tempvar` / `sortpreserve`；`ereturn post` 带 `esample()`，返回值齐全、b 与 V 行列名一致；错误码被 rcof 测过；没有写死 `set seed`、`merge m:m`、注释里的 `/*`、`cd`、绝对路径、自动 `ssc install`。
- pitfalls.md 中相关的条目 test-spec.md 都有场景、audit.md 都跑了；缺了 → STOP 路由 planner（场景不足）或 tester（没跑）。
- tester 的每个脚本都 `adopath ++` 并 `which` 核对了版本；没有 → STOP 路由 tester。
- 容差审计时额外查：`capture assert`；`capture noisily` 包住场景却没记录 `_rc`。
- 帮助文件：Syntax、Stored results 与实际一致，例子跑过，SMCL 能转换 → 否则 STOP 路由 scriber。
- 版本同步：ado `*!`、sthlp 版本注释、pkg `Distribution-Date` 一致；新增文件都在 pkg 里。

---

## 发布检查（工作流 8）

组长写的 test-spec.md 包含 testing.md 第 5 节的全部项目：`stata_pkg_check.py` 无 ERROR；临时 PLUS 目录 `net install` 成功、`which` 显示新版本；帮助文件能转换、例子能跑；三处版本号一致；README 写明安装方式。之后派 reviewer。提交 SSC 需要用户自己联系 SSC 维护者，插件只准备文件。
