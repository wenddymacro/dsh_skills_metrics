# SFCmodeler API 速查

基于随附的上游版本（提交 `0e6a2c0`）。所有名称都从包顶层导入：

```python
from SFCmodeler import (SFCmodel, Variable, Parameter, Random, d, lag, if_true, solve_for,
                        Sector, Asset, Transaction, BSmatrix, TFmatrix, RVmatrix, ModelResults)
```

## 项（Term）

| 写法 | 含义 |
|---|---|
| `Variable("Y", "说明", 初始值)` | 内生变量，每期由方程求解。`growth=True` 表示判断稳态时看增长率而不是水平 |
| `Parameter("theta", "说明", 0.2)` | 外生参数，求解器不改动；冲击就是改它 |
| `Random("eps", "说明", distribution=scipy.stats.norm(0, 1))` | 每期重新抽样的随机项；`Random.set_seed(42)` 固定种子 |
| `Variable.default_value = 0` | 之后新建的变量的默认初始值（不设则为 NaN，求解时报缺初始值） |
| `Y(-1)`、`Y(-2)` | 滞后一期、两期；只能是非正整数 |
| `Y.hat` | 一个新变量及其方程：百分比增长率 `100*(Y - Y(-1))/Y(-1)` |

同名的项是同一个 SymPy 符号：在两个函数里分别 `Variable("Y")` 得到的是同一个对象。

## 方程

| 写法 | 含义 |
|---|---|
| `Y << C + G` | 方程 Y = C + G（`<<` 是等号，左边只能是一个 `Variable`） |
| `d(V) << YD - C` | 等价于 `V << V(-1) + YD - C` |
| `d(Y)` 出现在右边 | 表达式 `Y - Y(-1)` |
| `lag(expr, n)` | 把表达式里所有项都滞后 n 期 |
| `if_true(cond)` | 条件成立为 1，否则为 0，例如 `if_true(ER > 1 - BANDb)` |
| `sp.Min`、`sp.Max`、`sp.exp`、`sp.log` | 任意 SymPy 函数都可以用（`import sympy as sp`） |
| `solve_for(零表达式, 变量)` | 把“应为 0 的表达式”解成该变量的方程，常配合矩阵使用 |

## 模型

```python
model = SFCmodel(equations, redundant_equation=None, start_period="2000", freq="Y")
```

- `freq` 取 pandas 周期频率：`"Y"` 年、`"Q"` 季、`"M"` 月。
- `model[theta] = 0.25`：只有初始期时设初始值；已求解过则开出新的一期并在该期起生效（即冲击）。
- `model[:] = {theta: 0.25, G: 20}`：一次设多个。
- `model[Y]`：最近一期的值（未求解时取上一期）。
- `model.solve(n)`：再求解 n 期；`model.solve(500, steady=True)` 到达稳态即停，
  也可传 `steady={"rtol": 1e-6, "atol": 1e-9, "ignore": []}`。
- `model.check_steady_state(detail=True)`：列出已收敛和未收敛的变量。
- `model.check_redundant_equation()`：最近一期冗余方程两边的值。
- `model.inventory()`：全部项的说明和初始值表。
- `model.data`：`ModelResults`，可以用项或表达式取列：`model.data[[Y, C(-1), alpha1*Y]]`；
  `model.data.df` 是底层 DataFrame（列是 SymPy 符号，含滞后列）。

求解算法：每期用 `scipy.optimize.root`（带解析雅可比、按上一期取值缩放残差）；失败时去掉雅可比再试，
再失败则交替做 Jacobi 迭代和 `root`。仍失败抛 `RuntimeError`。

## 矩阵（可选，用来生成方程和核对式）

```python
Households = Sector(NW=V, name="家庭")          # NW：该部门的净值变量（可省略）
Government = Sector(name="政府")

Bills = Asset(
    issuer=Government,                            # 负债方；实物资产为 None
    demands={Households: Bh, CB: Bcb},            # 各部门的需求 / 持有量
    supplies={Households: Bh},                    # 各部门的供给量（可省略）
    total_supply=Bs,                              # 总供给变量（可省略，默认为供给之和）
    price=1,                                      # 价格，可以是变量（如 Pbl）
    payout=lambda q: R(-1) * q(-1),               # 每单位的利息 / 红利
    name="国债",
)

tf = TFmatrix(sectors=[...], transactions=[Transaction({Households: -C, Production: C}), ...],
              assets=[Money, Bills])              # 给出 assets 时自动加上利息行和存量变化行
bs = BSmatrix(sectors=[...], assets=[...])
rv = RVmatrix(sectors=[...], assets=[...])       # 重估值矩阵：价格变化带来的资本利得
```

| 方法 | 返回的零表达式 |
|---|---|
| `tf.sector_zero_expression(部门)` / `tf.sector_zero_expressions()` | 交易流量矩阵的列和（部门预算约束） |
| `tf.transaction_zero_expressions()`、`Transaction.zero_expression()` | 行和（每笔交易的支出 = 收入） |
| `Asset.market_zero_expression()` | 总供给 − 各部门持有量 |
| `Asset.sector_zero_expression(部门)` | 某部门的供给 − 需求 |
| `bs.sector_zero_expression(部门)` | 资产 − 负债 − 净值 |
| `Sector.wealth_zero_expression(tf, rv)` / `rv.sector_zero_expressions(tf)` | 净值变化 = 储蓄 + 资本利得 |

用法：`solve_for(tf.sector_zero_expression(Government), Bs)` 生成政府预算约束方程；
把这些零表达式放进模型文件的 `checks()`，`sfc_run.py` 会逐期计算残差。

## 常见错误

| 现象 | 原因与处理 |
|---|---|
| `Variables and equations do not match` | 有变量没有方程，或方程左边写了参数；`--describe` 对照方程和变量列表 |
| `Each variable can only appear on the LHS of one equation` | 同一变量被两条方程决定；把其中一条改成冗余方程或删掉 |
| `Initial values missing for [...]` | 设 `Variable.default_value = 0`，或构造时给初始值，或 `--set` |
| `Solver failed for period ...` | 初始值导致除以 0 / 对数取非正数；或参数让模型无解。先缩短期数排查 |
| `Redundant equation violated` | 初始存量不一致（常见于书中四舍五入的数值），或某笔交易漏记 |
| 预热不收敛 | 模型没有稳态（增长模型要标 `growth=True`），或容差太严（`--steady-rtol`） |
| 恒等式核对不通过 | 记账错误：漏了一笔交易、符号写反、价格没乘上。先修正再报告结果 |
