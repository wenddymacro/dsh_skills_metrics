---
name: sfc-modeler
description: >-
  搭建、求解和冲击后凯恩斯主义存量流量一致（stock-flow consistent, SFC）模型：用随附的
  Python 包 SFCmodeler（基于 SymPy 和 pandas）把行为方程和会计恒等式写成代码，逐期求解，
  从稳态出发施加政府支出、税率、利率、资产价格等参数冲击，与基线比较，核对交易流量矩阵和
  资产负债表的行列和是否为零，输出 CSV、图和中文摘要。自带 Godley & Lavoie《Monetary
  Economics》的 SIM、PC、LP 模型和“矩阵写法”示例。用户提到 SFC 模型、存量流量一致、
  Godley-Lavoie、后凯恩斯模型、交易流量矩阵 / 资产负债表矩阵、模型 SIM / PC / LP、
  政府支出乘数或财政赤字的存量后果、“帮我写一个 SFC 模型”时使用。
---

# SFC 存量流量一致模型

本 skill 随附上游 SFCmodeler（Sam Levey，Apache-2.0，<https://github.com/slevey087/SFCmodeler>，
提交 `0e6a2c0`）的源码，不需要 `pip install SFCmodeler`。它只是一个**求解器**：方程、参数和
初始存量都由你（和用户）决定；模型的经济含义要向用户讲清楚，不要把模拟结果说成预测。

资源都在本 skill 的目录（加载 skill 时报告的 base directory，下文写作 `<skill-dir>`）：

| 路径 | 内容 |
|---|---|
| `scripts/sfc_doctor.py` | 检查 Python 和依赖，缺什么就打印安装命令（不会自动安装） |
| `scripts/sfc_run.py` | 加载模型文件 → 预热到稳态 → 施加冲击 → 与基线比较 → 核对恒等式 → 输出 CSV / PNG / 摘要 |
| `examples/sim.py` | G&L 第 3 章 SIM：只有政府货币 |
| `examples/pc.py` | G&L 第 4 章 PC：国债、中央银行、投资组合选择 |
| `examples/pc_matrices.py` | PC 的矩阵写法：用 `Sector` / `Asset` / `TFmatrix` 生成方程和核对式 |
| `examples/lp.py` | G&L 第 5 章 LP：长期债券、资本利得、预期 |
| `reference.md` | SFCmodeler API 速查和常见错误 |
| `vendor/SFCmodeler/` | 上游源码（勿改） |

## 工作流程

### 1. 检查环境（每个会话第一次使用时）

```sh
python3 <skill-dir>/scripts/sfc_doctor.py
```

退出码 0 表示就绪。缺依赖时脚本会打印 `pip install` 命令：**把命令给用户看，征得同意后再运行**。
如果 pip 报 `externally-managed-environment`，按脚本提示建虚拟环境，之后所有脚本都用该虚拟环境的
`python` 运行。需要 Python ≥ 3.10。

### 2. 明确模型

先和用户确认，再写代码：

- **部门**（家庭、企业、政府、中央银行、银行……）和**资产**（现金、存款、国债、贷款、股票……），
  即资产负债表矩阵的行和列；
- **交易**（消费、工资、税收、利息、红利……），即交易流量矩阵；
- 每个内生变量由哪条**行为方程**或**恒等式**决定，哪些是外生**参数**；
- 哪条恒等式是**冗余**的（G&L 的“缺失方程”，如 `Hh = Hs`）：它不进入方程组，留作核对；
- 时间频率和期数（默认年度，从 2000 年开始）。

用户只说“复现 G&L 的模型 X”时，先看 `examples/` 里有没有；有的话直接用。

### 3. 写模型文件

在用户的工作目录（不要写进 `<skill-dir>`）新建 `xxx_model.py`，照 `examples/sim.py` 的结构：

```python
from SFCmodeler import Parameter, SFCmodel, Variable, d

PLOTS = [["Y", "C"], ["V"]]          # 可选：默认要画的变量组

def build():                          # 必需：返回 SFCmodel
    global C, Y, V, G, ...            # 需要在 checks() 里用到的项声明为全局
    Variable.default_value = 0        # 所有内生变量的初始值；个别的在构造时给第三个参数
    C = Variable("C", "消费")
    G = Parameter("G", "政府支出", 20)
    ...
    return SFCmodel([
        C << alpha1 * YD + alpha2 * V(-1),   # 左边只能是一个变量；V(-1) 是上一期
        d(V) << YD - C,                      # d(V) << x 等价于 V << V(-1) + x
        ...
    ], redundant_equation=Hh << Hs)

def checks(model):                    # 可选但强烈建议：每项都应恒为 0
    return {"家庭预算": YD - C - d(V), "货币市场": Hs - Hh}
```

要点（详见 `reference.md`）：

- 方程数必须等于内生变量数，每个 `Variable` 恰好出现在一条方程的左边；不满足时 `SFCmodel(...)` 直接报错。
- 只有 `Variable` 会被求解；不出现在任何方程左边的量要声明成 `Parameter`。
- 名称里可以用 LaTeX（`Variable("B_{cb}")`），但命令行里引用时要写原样 `B_{cb}`；为方便起见，**优先用纯字母数字名称**。
- 部门多、资产多时，用 `pc_matrices.py` 的写法：先定义 `Sector`、`Asset`、`Transaction`，
  再用 `TFmatrix(...).sector_zero_expression(部门)` 加 `solve_for` 生成预算约束方程，
  `checks()` 直接返回矩阵的全部行和、列和，最不容易漏项。

### 4. 先看结构，再求解

```sh
python3 <skill-dir>/scripts/sfc_run.py xxx_model.py --describe
```

打印方程、变量、参数和**缺失的初始值**。确认无误后求解：

```sh
# 从初始值直接跑 50 期
python3 <skill-dir>/scripts/sfc_run.py xxx_model.py --periods 50

# 先预热到稳态（最多 500 期），再跑 40 期，第 5 期把 G 提高到 25，同时自动跑一遍无冲击的基线
python3 <skill-dir>/scripts/sfc_run.py xxx_model.py --warmup 500 --periods 40 --shock G=25@5 --plot Y,C --plot V

# 冲击可以叠加，也可以用 += 或 *=；--set 在求解前改参数或初始值
python3 <skill-dir>/scripts/sfc_run.py xxx_model.py --set theta=0.25 --warmup 500 --periods 40 \
    --shock "Rbar+=0.01@5" --shock "G*=1.1@10"
```

| 选项 | 作用 |
|---|---|
| `--describe` | 只打印模型结构，不求解 |
| `--set 名称=值` | 求解前覆盖参数或初始值（可重复，也可 `+=`、`*=`） |
| `--warmup N` | 先求解最多 N 期直到稳态（`--steady-rtol`，默认 1e-6）；冲击期从稳态之后算起 |
| `--periods N` | 预热之后再求解 N 期（默认 20） |
| `--shock 名称=值@k` | 在第 k 期把参数改为该值（只能是 `Parameter`）；有冲击时自动输出基线和差值 |
| `--plot A,B` | 每个 `--plot` 一张图，冲击情形实线、基线虚线、冲击期竖虚线 |
| `--out 目录` | 输出目录，默认 `./sfc_output/<模型文件名>/` |
| `--check-tol` | 恒等式残差的相对容差（默认 1e-6，乘以结果中的最大绝对值） |

输出：`results.csv`（每期全部当期变量和参数）、有冲击时的 `baseline.csv` 和 `diff.csv`（冲击减基线，
只含内生变量）、`checks.csv`（每条恒等式每期的残差）、`plot_*.png`、`summary.md`（同时打印到终端）。

退出码：0 成功；2 参数或模型文件有误（看 `错误：` 后的说明）；3 求解器不收敛。

### 5. 核对与报告

- **先看恒等式核对表**。任何一行“不通过”都说明模型记账有漏洞（漏了一笔交易、符号写反、
  存量变化与流量不一致），**必须先修正，不要报告结果**。初始期不参与核对。
- 冗余方程不成立时求解器会给警告；常见原因是初始存量彼此不一致（例如四舍五入）。
- 预热未到达稳态时摘要会写明；可以增大 `--warmup`，或检查模型本身是否有稳态（增长模型要用
  `Variable(..., growth=True)` 标记按增长率判断收敛的变量）。
- 向用户报告：冲击是什么、在哪一期；关键变量的冲击前水平、期末水平和相对基线的变化；
  动态特征（立即响应、超调、收敛速度）；并给出图片路径。用 G&L 的经济直觉解释，例如
  SIM 中政府支出增加的长期乘数是 1/θ，PC 中利率上升通过利息收入提高产出。
- 结果依赖参数校准。用户的参数来自哪里（书中、文献、自己估计）要在报告里注明。

## 常见问题

- **“Variables and equations do not match”**：某个变量没有方程，或某个方程左边是参数。用 `--describe` 对照。
- **“Initial values missing for [...]”**：有项没有初始值（默认 NaN）。设 `Variable.default_value = 0`，
  或在构造时给初始值，或 `--set 名称=值`。
- **求解器不收敛（退出码 3）**：多半是初始值让分母为 0（如 `1/Pbl` 而 `Pbl=0`），给相关变量合理的
  初始值；含 `Min` / `Max` / `if_true` 的折点模型上游会自动尝试 Jacobi 迭代。
- **想改上游行为**：不要改 `vendor/`；在模型文件里写辅助函数即可。

## 进一步

更大的模型（如 G&L 第 11 章 GROWTH，上百个方程）也能写，但要分块：先写企业、家庭、政府、银行各自的
方程块，每加一块都 `--describe` 和短跑核对一次。上游文档：<https://slevey087.github.io/SFCmodeler/>。
