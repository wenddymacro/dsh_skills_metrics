# Stata 命令开发约定

builder 写代码、reviewer 审代码时依据本文件。项目已有的风格与本文件冲突时，以项目风格为准，并在 implementation.md 里说明。

## 1. 项目类型

| 类型 | 标志 | 交付物 |
|---|---|---|
| **命令包** | `*.ado`、`*.sthlp`，可能有 `*.pkg`、`stata.toc`、`*.mata`、`l*.mlib` | 可以 `net install` 的命令 |
| **复现 / 分析项目** | 只有 `*.do`，通常有 `master.do` | 能从头跑通、结果可复现的 do-file 链 |

命令包按本文件全部规则做；复现项目只适用第 2、6、7、8 节，验证以"`master.do` 跑通、关键数值与基准一致"为准。

## 2. 文件与命名

- 一个公开命令一个 `<cmd>.ado`，文件名与 `program` 名相同，全小写；配套 `<cmd>.sthlp`。
- 内部子程序：放在同一个 ado 文件里、主程序之后（`program _<cmd>_xxx`），或单独的 `_<cmd>_xxx.ado`。以下划线开头的视为私有，不需要帮助文件。
- 新增后估计命令：`<cmd>_p.ado`（predict）、`<cmd>_estat.ado`（estat）。
- Mata 代码：小量放在 ado 文件末尾的 `mata:` … `end` 块里；量大时放 `<cmd>.mata`，编译成 `l<cmd>.mlib`（`lmbuild`，Stata 15+；要写进 pkg）。
- 第一行是版本注释：`*! version 1.0.0  21nov2026`（`*!` 开头，`which <cmd>` 会显示）。改动后递增版本号并更新日期。

## 3. 程序骨架

```stata
*! version 1.0.0  21nov2026
program define mycmd, eclass sortpreserve byable(recall)
    version 16
    syntax varlist(min=2 numeric fv ts) [if] [in] [pweight fweight aweight] ///
        [, Level(cilevel) vce(passthru) noCONStant *]

    marksample touse
    // 处理 vce(), 权重, 选项校验 ...
    gettoken depvar indepvars : varlist
    _fv_check_depvar `depvar'

    quietly count if `touse'
    if r(N) == 0 error 2000

    tempname b V
    tempvar resid
    // 计算 ...

    ereturn post `b' `V', esample(`touse') obs(`=r(N)') depname(`depvar')
    ereturn local cmd "mycmd"
    ereturn local cmdline `"mycmd `0'"'
    ereturn local vce "`vcetype'"
    ereturn local predict "mycmd_p"
    ereturn scalar N = ...
    Display, level(`level')
end

program Display
    syntax [, Level(cilevel)]
    ereturn display, level(`level')
end
```

要点：

- **`version` 写在 program 内部**，取项目支持的最低 Stata 版本（默认 16），不要写高于用户本机的版本。
- **`syntax`** 负责解析和基本校验；选项缩写用大写字母标出（`Level`）。`fv` / `ts` 只在确实支持因子变量 / 时间序列算子时才写。
- **`marksample touse`** 处理 `if`、`in`、权重和缺失；后续所有计算都限定 `` if `touse' ``。额外用到的变量用 `` markout `touse' var ``。
- **临时对象全部用** `tempvar`、`tempname`、`tempfile`，不在数据集里留下变量、不覆盖用户的标量和矩阵。
- **`sortpreserve`**：程序里排过序就加，保证用户数据顺序不变；需要稳定排序用 `sort ..., stable`。
- **`preserve` / `restore`**：只在必须改动数据（`collapse`、`reshape`、`keep`）时用；尽量改用 `tempfile` 或 Mata。
- **eclass**：用 `ereturn post b V, esample() obs() depname()` 一次性提交；`b` 是 1×k 行向量，`V` 是 k×k 对称矩阵，行列名一致（`matrix colnames`）。必须设 `e(cmd)`、`e(cmdline)`；有标准误时设 `e(vce)`、`e(vcetype)`；支持 predict 时设 `e(predict)`。
- **rclass**：用 `return scalar`、`return local`、`return matrix`；不要在 rclass 程序里调用会清空 r() 的命令之后再读旧的 r()。
- **显示与计算分离**：重放（`mycmd` 不带参数时重新显示上次结果）用 `if replay() { ... }` 处理，`e(cmd)` 不对就 `error 301`。

## 4. 错误处理

- 用户输入错误用标准错误码退出，并给出可读的信息：
  ```stata
  if `k' < 1 {
      display as error "option k() must be a positive integer"
      exit 198
  }
  ```
  常用：198（语法 / 选项无效）、111（变量不存在）、109（类型不符）、2000（无观测）、2001（观测不足）、459（数据不符合要求）、430（不收敛）、301（上次估计结果不对）、503（矩阵维度不符）。
- `capture` 只包住**预期可能失败**的那一句，紧接着检查 `_rc`；不要用 `capture` 吞掉一大段代码。需要显示被包住命令的输出时用 `capture noisily`。
- 迭代算法必须有最大迭代次数和收敛容差选项（`iterate()`、`tolerance()`），不收敛时 `display as error` 并设 `e(converged) = 0`，由文档说明行为。

## 5. 数值与 Mata

- 新变量一律 `generate double`；矩阵运算在 Mata 里做。
- 解线性方程用 `cholsolve()`（正定）或 `qrsolve()` / `lusolve()`，不要显式求逆；必须求逆时用 `invsym()`（对称）并检查秩（`rank()`、`diag0cnt()`）。
- 数值比较用相对容差，不用 `==` 比较浮点数。
- Mata 函数显式声明类型（`real matrix`、`real colvector`），开头 `version 16`、`mata set matastrict on`。
- 用 `st_view()` / `st_data()` 读数据（只读 `touse` 子样本），`st_matrix()` / `st_numscalar()` 把结果送回 Stata。

## 6. 随机数

- 命令里**不写死 `set seed`**；需要随机的命令提供 `seed()` 选项（默认不设种子），有就在内部 `set seed`。
- do-file、认证脚本、仿真脚本里固定种子；默认 RNG 为 `mt64`。并行或分块仿真用 `set rng mt64s` 加 `set rngstream`。

## 7. 依赖

- 依赖 SSC / 第三方命令时，在程序开头检查并给出安装提示，**不要自动 `ssc install`**：
  ```stata
  capture which reghdfe
  if _rc {
      display as error "mycmd requires -reghdfe-; type {stata ssc install reghdfe}"
      exit 199
  }
  ```
- 新增依赖要写进 mailbox.md（类型 INTERFACE），并在帮助文件里说明。

## 8. 风格

- 缩进 4 个空格；长命令用 ` ///` 续行；注释用 `//` 或 `*`（行首）。
- **注释里不要出现 `/*`**（例如 `* 输出到 out/*`）：它会开启块注释，后面的代码被悄悄跳过。
- 不写 `cd`、绝对路径；do-file 用相对项目根目录的路径。
- 生产代码不留调试用的 `display`、`list`、`pause`；用 `` if "`debug'" != "" { ... } `` 包住。
- 不改用户的全局设置（`set more`、`set varabbrev` 等）；确需临时修改时记下原值并恢复。
