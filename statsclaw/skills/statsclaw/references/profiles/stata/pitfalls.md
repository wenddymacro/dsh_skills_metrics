# Stata 静默错误清单

下面这些在 Stata 里**通常不报错，只会悄悄算错**。builder 写代码时逐条避开；planner 把相关的写进 test-spec.md 的边界情形；tester 设计场景时专门去撞；reviewer 审代码时逐条对照。

| # | 类别 | 陷阱 | 防法 / 测法 |
|---|---|---|---|
| 1 | 缺失值 | `.` 比任何数都大：`if x > 100`、`gen h = (x > 100)` 会把缺失算进去 | 写 `& !missing(x)`；测试数据里放缺失值，核对 N |
| 2 | 缺失值 | 扩展缺失 `.a`–`.z` 被当作缺失排除 | 测试含扩展缺失的情形 |
| 3 | 缺失值 | 多个回归 N 不同：listwise 删除让样本中途改变 | 用同一个 `touse`；测试 e(N) |
| 4 | 精度 | `gen` 默认 float，大 ID、金额、累加结果失真 | 一律 `gen double`；测试大数值输入 |
| 5 | 精度 | 浮点数用 `==` 比较 | 用相对容差 |
| 6 | 类型 | 数值被读成字符串（带逗号、空格） | `confirm numeric variable`；`syntax varlist(numeric)` |
| 7 | 排序 | `by` 组内 `_n`、`_N` 依赖排序，结果随排序变化；排序不稳定 | `sort ..., stable`；`sortpreserve`；测试打乱顺序后结果不变 |
| 8 | 数据 | 命令改动了用户数据（留下变量、改了排序、删了观测） | `tempvar`、`sortpreserve`；测试 `datasignature confirm` |
| 9 | 宏 | `local` 名拼错或作用域不对，展开为空却不报错 | `set varabbrev off`；关键宏 `` assert "`x'" != "" `` |
| 10 | 宏 | 引号嵌套错误：含空格或引号的字符串用 `` `"…"' `` | 测试带空格的变量标签、路径 |
| 11 | 注释 | 注释里的 `/*`（如 `* 写到 out/*`）开启块注释，后面的代码全被跳过 | `stata_pkg_check.py` 会查；log 里检查预期输出都在 |
| 12 | 返回值 | rclass 程序里调用了别的 rclass 命令，覆盖了 r() | 先把 r() 存进 tempname；测试 r() 每一项 |
| 13 | 返回值 | e(b)、e(V) 行列名不一致，或 V 不对称 | `ereturn post` 前统一命名；测试 `mreldif(e(V), e(V)')` |
| 14 | 估计 | `(omitted because of collinearity)`：关键变量被删 | run_stata.sh 会标出；测试完全共线输入的行为 |
| 15 | 估计 | singleton 被删、样本变小 | 报告删了多少；测试含 singleton 的面板 |
| 16 | 估计 | `convergence not achieved`、`not concave`、`backed up` 仍给出结果 | 检查 `e(converged)`；测试难收敛的数据 |
| 17 | 估计 | 方差矩阵奇异或非对称 | 检查秩；测试近共线输入 |
| 18 | 估计 | Logit/Probit 完全分离，观测被删 | 报告并测试 |
| 19 | 权重 | `fw`、`pw`、`aw`、`iw` 含义不同，标准误完全不同；权重缺失或为 0 被悄悄删除 | 每种支持的权重都与基准命令对照 |
| 20 | 设定 | 固定效应重复吸收；因子变量基准组与预期不同；交互项漏主效应 | 与基准命令对照系数和 N |
| 21 | 时间序列 | `L.`、`F.` 在时间不连续时产生缺失 | 测试有缺口的面板 |
| 22 | merge | `merge m:m` 按顺序配对，几乎总是错的；`_merge` 没检查 | 用 1:1 / m:1 并 `assert _merge == 3` 或明确处理 |
| 23 | 随机数 | 命令里写死 `set seed`，或未设种子导致不可复现 | 提供 `seed()` 选项；测试同种子结果相同 |
| 24 | 版本 | 没写 `version`，新版 Stata 默认行为变化 | program 内写 `version 16`（或项目最低版本） |
| 25 | 依赖 | SSC 包新旧版本默认值不同（如 reghdfe 6.x 与新版） | 记录 `which` 版本；文档写明要求 |
| 26 | 编码 | 中文变量名、标签、路径的编码问题 | 测试含中文标签的数据（Stata 14+ 为 UTF-8） |
| 27 | 环境 | 本机已安装的旧版同名 ado 被优先调用；包自己从 PLUS 目录或当前目录 `run` 辅助程序，绕过 adopath | 辅助程序靠 adopath 自动加载或 `findfile`；测试脚本开头 `adopath ++ 项目目录`、`discard`、`which <cmd>, all`，本机装有旧版时用临时 PLUS 目录 |
