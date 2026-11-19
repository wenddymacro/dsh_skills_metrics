* TWFE：单方离婚法对离婚率的影响，加入失业率控制
version 18
clear all
set more off
use divorce_panel, clear
merge m:m state year using controls
drop _merge
reghdfe div_rate udl unemp, absorb(state year) vce(cluster state)
