* 生成演示用的 controls.dta：州-年失业率（随机数），并故意让 Alaska（state==1）
* 的每个州-年重复一次、unemp 加 3，复现"换了新版控制变量后 N 和系数都变了"。
* 在放有 divorce_panel.dta 的目录下运行：stata-mp -b do make_controls.do
use divorce_panel, clear
keep state year
set seed 1
gen double unemp = 5 + runiform()
expand 2 if state==1, gen(dup)
replace unemp = unemp + 3 if dup
drop dup
save controls, replace
