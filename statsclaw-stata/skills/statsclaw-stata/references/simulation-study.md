# 仿真研究（蒙特卡洛）要点

供 planner 写 sim-spec.md、simulator 写仿真代码、tester 验证仿真结果、reviewer 审查时参考。

## 两种工作流

- **工作流 3（仿真 + 代码）**：新估计量，同时要有限样本证据。planner 写三份规格：spec.md（估计量实现）、test-spec.md（单元测试 + "仿真验证"一节）、sim-spec.md（DGP、场景网格、指标、验收标准）。builder 和 simulator 写入范围不重叠时可以同时进行，都完成后由 tester 跑完整仿真。
- **工作流 4（仅仿真）**：估计量已存在。planner 写 sim-spec.md 和 test-spec.md，simulator 写仿真代码，tester 跑完整仿真并验证。不派 builder。

## sim-spec.md 的七部分

1. **DGP 定义**：模型结构（如 Y = Xβ + ε）；每个参数的符号、真值、类型；误差分布（基准 + 稳健性备选，如 N(0,σ²)、t(3)、中心化 χ²(1)、异方差）；协变量分布和相关结构；要扫描的样本量。
2. **估计量接口**：函数名、所在包或模块、必需参数和类型、返回值结构（点估计、标准误、置信区间、p 值）。**只写怎么调用，不写内部怎么算**：simulator 把估计量当黑箱。
3. **场景网格**：各维度及取值、场景总数、每个场景的重复次数 R、总运行次数。
4. **性能指标**：偏误、相对偏误、标准差、RMSE、MAE、中位数偏误、95% 置信区间覆盖率、平均区间长度、size（原假设下拒绝率）、power、SE 比（估计 SE 均值 / 估计值经验标准差）、失败率，以及自定义指标。
5. **验收标准**：每条都有精确阈值和适用样本量，例如：

   | 标准 | 阈值 | 适用 N |
   |---|---|---|
   | 相对偏误 | < 5% | ≥ 500 |
   | 95% CI 覆盖率 | ∈ [0.93, 0.97] | ≥ 500 |
   | size（α = 0.05） | ∈ [0.03, 0.07] | ≥ 500 |
   | SE 比 | ∈ [0.95, 1.05] | ≥ 500 |
   | RMSE 收敛速度 | log-log 斜率 ∈ [−0.6, −0.4] | 全部 |
   | 失败率 | < 1% | 全部 |

6. **种子策略**：主种子；RNG（默认 `set rng mt64`；分块并行用 `set rng mt64s` 加 `set rngstream #`，每块一个流号）；每个场景如何取种子或流号。
7. **输出格式**：结果表的列、图的种类（偏误 / RMSE 随 N 变化、覆盖率带蒙特卡洛误差带、SE 比、估计值密度），PDF 和 PNG 各一份。

test-spec.md 里的"仿真验证"一节写的是**同一组验收标准**，但写成断言（"N ≥ 500 时覆盖率在 [0.93, 0.97] 内"）。planner 负责两边一致。

## 蒙特卡洛误差

比例类指标（覆盖率、size、power）：`se = sqrt(p(1−p)/R)`。均值类指标（偏误）：`se = sd(估计值)/sqrt(R)`。报告时说明偏离目标是否超过蒙特卡洛误差。R = 2000 时，名义 95% 覆盖率的蒙特卡洛标准误约 0.005。

## 规则

- **如实报告**：不挑有利场景，不挑种子，不删不利结果。
- **不放宽标准**：simulator 和 tester 都不能改阈值、减重复次数、换种子来"通过"。阈值看起来不合理时，由 tester 发 BLOCK 路由给 planner。
- **可复现**：同一种子重跑必须得到完全相同的结果；tester 至少重跑一个场景核对。
- **估计耗时**：simulator 在冒烟运行后估计完整仿真的总耗时，超过 1 小时要在 simulation.md 里写明，由 leader 告诉用户并确认是否缩小网格（缩小网格要由 planner 改规格，不能由 tester 自行减少）。
- **失败要记录**：每次重复用错误处理包住，失败计数，按场景报告失败率（包括 0%）。
- **并行**：Stata 单进程内没有通用并行循环。需要提速时把场景网格分块，每块一个 do-file、一个 `rngstream`，用多个批处理进程同时跑（`run_stata.sh` 后台运行），最后合并结果；或把内层计算写进 Mata。

## 审查时看什么

- 偏误是否随 N 收敛到 0，RMSE 是否大致按 1/√N 下降，覆盖率是否接近名义水平，SE 比是否接近 1。
- 单元测试和仿真是否讲同一个故事：单元测试点估计对、仿真覆盖率差，多半是标准误公式有问题；单元测试对、仿真有偏，多半是 DGP 有问题。
- 可疑现象：覆盖率恰好等于名义水平（检验可能没有区分力）、结果对种子敏感、刚好卡在阈值边上。
- 网格里的每个场景是否都跑了。

## Stata 写法

两种主循环任选其一，sim-spec.md 里写明用哪种：

**`simulate`**（简单、单个场景）：

```stata
program define onerep, rclass
    syntax [, n(integer 500) beta(real 0.5)]
    drop _all
    set obs `n'
    generate double x = rnormal()
    generate double y = `beta' * x + rnormal()
    capture noisily mycmd y x
    if _rc {
        return scalar failed = 1
        exit
    }
    return scalar failed = 0
    return scalar b  = _b[x]
    return scalar se = _se[x]
end

set rng mt64
set seed 20261121
simulate failed=r(failed) b=r(b) se=r(se), reps(2000) nodots: onerep, n(500) beta(0.5)
```

**`postfile`**（多场景网格、需要累计更多信息时）：

```stata
local R = 2000
tempname h
postfile `h' int(scenario rep) double(n b se failed) using "sim/out/results.dta", replace
local s = 0
foreach n of numlist 100 200 500 1000 {
    local ++s
    set seed `=20261121 + `s''
    forvalues r = 1/`R' {
        quietly onerep, n(`n')
        post `h' (`s') (`r') (`n') (r(b)) (r(se)) (r(failed))
    }
}
postclose `h'
```

然后读结果数据集，`collapse` 或手算各指标：

```stata
use "sim/out/results.dta", clear
local truth = 0.5
generate double cover = abs(b - `truth') <= invnormal(0.975) * se if !failed
generate double err2  = (b - `truth')^2 if !failed
collapse (mean) meanb=b cover mse=err2 failrate=failed meanse=se (sd) sd=b (count) nok=b, by(n)
generate double bias    = meanb - `truth'
generate double rmse    = sqrt(mse)
generate double seratio = meanse / sd
generate double mcse_cover = sqrt(cover * (1 - cover) / nok)
```

注意：

- 失败的重复（`capture` 到错误）要记成失败，`b`、`se` 设为缺失，不要从数据集里删掉。
- 偏误、RMSE 只用成功的重复计算，失败率单独报告。
- 结果数据集存 `.dta`，表格用 `esttab`/`putexcel`/`file write` 输出，图用 `twoway` 导出 PDF 和 PNG。
- Stata 循环慢：冒烟运行后按单次耗时 × 场景数 × R 估计总耗时。
