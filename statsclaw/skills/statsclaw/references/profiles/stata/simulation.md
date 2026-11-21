# Stata 仿真写法

通用的仿真设计（sim-spec.md 七部分、蒙特卡洛误差、如实报告等规则）见 `<SKILL>/references/simulation-study.md`。本文件只写 Stata 里怎么实现。

## 种子与并行

- RNG 默认 `set rng mt64`；每个场景按 sim-spec.md 的规则 `set seed`。
- Stata 单进程内没有通用的并行循环。需要提速时把场景网格分块：`set rng mt64s`，每块一个 `set rngstream #`、一个 do-file，用多个 `run_stata.sh` 后台进程同时跑，最后 `append` 合并；或者把内层计算写进 Mata。
- 仿真 do-file 通过参数控制规模（`args R scenarios`，用 `run_stata.sh sim/sim_main.do 50 1/2` 传入），缺省为 sim-spec.md 的完整 R 和全部场景，冒烟运行和 tester 的完整运行用同一个文件。
- 开头 `adopath ++` 指向项目 ado 目录、`discard`、`which <cmd>`，确保调用的是项目里的版本。

## 主循环

两种写法任选其一，sim-spec.md 里写明用哪种：

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
