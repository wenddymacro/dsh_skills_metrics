* cert_<cmd>.do -- certification script template for StatsClaw (Stata).
* Run from the project root:  bash <RUN> --tail 40 <dir>/cert_<cmd>.do
* Every tolerance below must be copied from test-spec.md; never widen it.

version 16
clear all
set more off
set varabbrev off
adopath ++ "."                 // project directory holding the ado files (edit if they live in a subfolder)
discard

cscript "<cmd>: <what this script certifies>" adofile <cmd>
which <cmd>

local tol_b = 1e-10            // from test-spec.md
local tol_V = 1e-10            // from test-spec.md

* --- Scenario 1: agrees with a benchmark command --------------------------------
sysuse auto, clear
regress price mpg weight
tempname b0 V0
matrix `b0' = e(b)
matrix `V0' = e(V)
<cmd> price mpg weight
assert mreldif(e(b), `b0') < `tol_b'
assert mreldif(e(V), `V0') < `tol_V'
assert e(N) == 74
assert "`e(cmd)'" == "<cmd>"
display "RESULT|S1|b|" %21.15g _b[mpg] "|" %21.15g `b0'[1,1] "|`tol_b'"

* --- Scenario 2: invalid input fails with the documented error code ------------
rcof "<cmd> price" == 102
rcof "<cmd> price mpg if 0" == 2000

* --- Scenario 3: missing values are excluded ------------------------------------
sysuse auto, clear
replace mpg = . in 1/5
<cmd> price mpg weight
assert e(N) == 69

* --- Scenario 4: the user's data are left untouched -----------------------------
sysuse auto, clear
datasignature set
<cmd> price mpg weight
datasignature confirm

* --- Scenario 5: same seed, same result (commands with randomness) ------------
* <cmd> price mpg, seed(123)
* scalar r1 = _b[mpg]
* <cmd> price mpg, seed(123)
* assert _b[mpg] == r1

display "CERT PASSED"
