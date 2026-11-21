# Stata 验证方法

tester 依据本文件运行检查；planner 写 test-spec.md 时据此给出可执行的场景和容差；builder 写自己的单元测试（认证脚本）时也用这套写法。

## 1. 运行 Stata

一律用 skill 自带的 `scripts/run_stata.sh`（路径在派发提示里给出，下文记作 `<RUN>`），**在项目根目录**执行：

```bash
bash <RUN> --version                 # 本机 Stata 版本
bash <RUN> --which-stata             # 将使用的 Stata 可执行文件
bash <RUN> --tail 40 path/to/file.do # 批处理运行
```

它以批处理模式运行 do-file，把 `<file>.log` 放在 do-file 旁边，打印第一个 `r(###)` 错误码及前文，以及共线、singleton、不收敛、方差矩阵奇异、完全预测等警告；有错误时退出码为 1。找不到 Stata 时退出码为 2：如实记录，结论 BLOCK，路由给 leader（请用户安装或设置环境变量 `STATA_BIN`）。

每个检查用的 do-file 开头固定写：

```stata
version 16
clear all
set more off
set varabbrev off
adopath ++ "<项目里放 ado 的目录，相对路径>"
discard
```

- `adopath ++` 让本次运行**优先用项目里的 ado**，而不是本机已安装的旧版本；`discard` 清掉内存里已加载的程序。
- 每个脚本里先 `which <cmd>`，确认找到的是项目里的文件，把输出记进 audit.md。
- 批处理每次都是新的 Stata 进程，不会继承上一次的状态。

## 2. 认证脚本（cert script）

Stata 官方测试命令用的写法。放在 tester 自己的目录（`<运行目录>/tester/`）；builder 的单元测试放在项目约定的位置（常见 `cert/`、`test/`、`tests/`）。

```stata
cscript "mycmd: basic OLS equivalence" adofile mycmd
// cscript 会 clear all、设置 linesize，并在 log 里标出被测 ado 的版本

sysuse auto, clear

* 场景 1：与基准命令一致
regress price mpg weight
tempname b0 V0
matrix `b0' = e(b)
matrix `V0' = e(V)
mycmd price mpg weight
assert mreldif(e(b), `b0') < 1e-10
assert mreldif(e(V), `V0') < 1e-10
assert e(N) == 74
assert "`e(cmd)'" == "mycmd"

* 场景 2：非法输入返回指定错误码
rcof "mycmd price" == 102          // too few variables
rcof "mycmd price mpg if 0" == 2000
rcof "mycmd price mpg, k(-1)" == 198

* 场景 3：缺失值被正确排除
replace mpg = . in 1/5
mycmd price mpg weight
assert e(N) == 69

* 场景 4：不改动用户数据
sysuse auto, clear
datasignature set
mycmd price mpg weight
datasignature confirm
```

常用工具：

| 工具 | 用途 |
|---|---|
| `assert <表达式>` | 失败即报错 r(9) |
| `reldif(a, b)` | 标量相对差 \|a−b\|/(\|b\|+1) |
| `mreldif(A, B)` | 矩阵最大相对差 |
| `rcof "命令" == #` | 断言命令以指定错误码失败 |
| `confirm variable / scalar / matrix` | 断言对象存在 |
| `datasignature set / confirm` | 断言数据未被改动 |
| `savedresults save / compare` | 保存并比较整组 e() 或 r() 结果 |
| `_assert_streq` 等 | 注意不同 Stata 版本可用性不同，优先用 `assert` |

**容差**：照抄 test-spec.md，用 `assert mreldif(...) < tol` 的形式写在脚本里，audit.md 里列出每个容差。不要用 `capture assert` 吞掉单个断言。为了让一个场景失败后其余场景还能跑，可以把**整个场景**放进 `capture noisily { ... }`，紧接着 `display "SCENARIO|S1|rc=" _rc`；`_rc` 非 0 即该场景失败，必须如实计入 audit.md。

## 3. 基准对比

能和已有命令对照的一定要对照，这是最强的证据：

| 被测内容 | 可对照的基准 |
|---|---|
| OLS / 稳健 / 聚类标准误 | `regress, vce(robust)` / `vce(cluster id)` |
| 面板固定效应 | `xtreg, fe`、`areg`、`reghdfe` |
| 工具变量 | `ivregress 2sls`、`ivreg2`、`ivreghdfe` |
| 极大似然 | `ml` 手写同一似然、`logit`、`probit`、`poisson`、`glm` |
| 边际效应 | `margins` |
| 自助法 | `bootstrap` 前缀（固定种子） |
| 论文结果 | 论文中的表格数值（容差按报告精度定，如 3 位小数 → `abs(a−b) < 5e-4`） |
| 解析解 | 特殊情形的闭式结果 |

第三方命令不在本机时：记录 `which` 的输出，结论里注明这一基准未能执行，不能当作通过。

## 4. 修改前后对比

需要"修改前"的数值时，不动项目工作区：

```bash
# git 项目
mkdir -p <运行目录>/tester/before
git archive <基线commit> | tar -x -C <运行目录>/tester/before
# 非 git 项目：用 <运行目录>/baseline/ 里的旧文件
```

另写一个 do-file，把 `adopath ++` 指向 `before/` 里的 ado 目录，跑同样的场景，结果存成数据集或矩阵，再与新版本对比。

## 5. 包装检查（命令包）

```bash
python3 <SCRIPTS>/stata_pkg_check.py <项目根目录>
```

`stata_pkg_check.py`（与 run_stata.sh 同目录）静态检查：每个公开 ado 有同名 program 和 `*!` 版本行、program 里有 `version`、有帮助文件、eclass 命令设置了 `e(cmd)`、注释里没有会吞代码的 `/*`、没有写死的 `set seed`、没有 `merge m:m`；`.pkg` 列出的文件都存在、公开命令都被列入；`stata.toc` 指向存在的 pkg。ERROR 视为 BLOCK，WARN 写进 audit.md 由 reviewer 判断。本机没有 Python 时，按同样清单人工检查并注明。

然后实际安装一次（不影响本机已装的版本）：

```stata
version 16
clear all
local here = c(pwd)
local plus "`c(tmpdir)'/statsclaw_plus"
capture mkdir "`plus'"
sysdir set PLUS "`plus'"
net install <pkgname>, from("`here'") replace
which <cmd>
help <cmd>
```

批处理模式下 `help` 不打开窗口，但帮助文件有 SMCL 语法错误时会报错。也可以用 `smcl2txt` 或 `translate <cmd>.sthlp <tmp>.txt, replace` 检查能否正常转换。

## 6. 复现项目

- 跑 `master.do`（或用户指定的入口），整个链条无 `r(###)` 错误。
- 关键结果（系数、标准误、N）与基准（论文、上一次的结果、用户给的数值）对比，写进 Per-Test 表。
- 相同种子重跑一次，结果完全相同。

## 7. 环境信息

audit.md 里记录：`c(stata_version)`、`c(edition_real)`（MP/SE/BE）、`c(os)`、`c(processors)`，以及用到的第三方命令 `which` 出来的版本行。
