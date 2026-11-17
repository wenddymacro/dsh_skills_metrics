# sfcmodeler · DSH 插件

把 [SFCmodeler](https://github.com/slevey087/SFCmodeler)（Sam Levey 的轻量级后凯恩斯存量流量一致模型求解器，
Python，基于 SymPy 和 pandas）做成 [DeepSeek Harness](https://github.com/deepseek-ai/deepseek-harness) 插件。
安装后，会话的 skill 目录里会多出 **`sfc-modeler`**：你用自然语言描述模型或冲击，agent 写出模型文件、求解、
施加冲击、核对会计恒等式，并给出中文摘要和图。

**本插件不是 SFCmodeler 作者的官方发布，也未经其认可或审阅。**

## 功能

- **写模型**：方程直接写成 `C << alpha1*YD + alpha2*V(-1)`、`d(V) << YD - C`；部门和资产多时，
  可以先写资产负债表和交易流量矩阵（`Sector` / `Asset` / `Transaction` / `TFmatrix`），由矩阵生成预算约束方程。
- **求解与冲击**：`scripts/sfc_run.py` 先预热到稳态，再在指定期改变参数（`G=25@5`、`Rbar+=0.01@5`、`G*=1.1@10`），
  自动跑一遍无冲击的基线，输出差值。
- **会计核对**：每期计算交易流量矩阵的行和、列和，以及资产负债表、冗余方程的残差，不为 0 就标“不通过”。
- **输出**：`results.csv`、`baseline.csv`、`diff.csv`、`checks.csv`、`plot_*.png`、`summary.md`。
- **示例**：Godley & Lavoie《Monetary Economics》的 SIM（第 3 章）、PC（第 4 章）、LP（第 5 章），以及 PC 的矩阵写法。
  方程与上游 notebook 一致（上游已与 pysolve3 逐期核对）；测试确认 SIM 稳态 Y = 100、PC 稳态 Y ≈ 106.49，
  矩阵写法与手写版本逐期完全相同。
- **中文化**：skill 说明、API 速查、脚本提示和摘要全部为简体中文；代码和标识符保留英文。

## 依赖

- DeepSeek Harness ≥ 0.2.1-rc.1
- 本机 Python 3.10 及以上，以及 `numpy`、`pandas`、`sympy`、`scipy`、`matplotlib`、`tqdm`、`tabulate`。
  SFCmodeler 本身随插件附带（上游提交 `0e6a2c0`，未修改），**不需要** `pip install SFCmodeler`
  （上游的 PyPI 包目前还不能用）。第一次使用时 agent 会运行 `sfc_doctor.py` 检查，缺什么把安装命令给你看，
  经你同意再安装。

## 安装

**桌面版**：打开「插件 → 添加插件」，填入下面的地址，点击「安装」，再点击「立即启用」。`#` 后面是提交号，下面是目前最新的版本；要装别的版本，换成对应的提交号。

```text
github:wenddymacro/dsh_skills_metrics#07237d3cf0b72639b5c0d346047e035af8cc7ebc&path:/sfcmodeler
```

**命令行**（CLI 管理的 profile）：

```bash
dsh plugin --profile <profile> add "github:wenddymacro/dsh_skills_metrics#07237d3cf0b72639b5c0d346047e035af8cc7ebc&path:/sfcmodeler"
```

从本地 checkout 安装（便于开发）：

```bash
dsh plugin --profile <profile> add "link:/abs/path/to/dsh_skills_metrics/sfcmodeler"
```

如果把已安装的插件换成另一个来源或版本，需要重启 DeepSeek Harness，新代码才会生效。

## 使用

直接用自然语言提问，例如：

> 用 Godley-Lavoie 的模型 SIM，把政府支出从 20 提高到 25，画出 GDP 和家庭现金的动态路径。

> 在模型 PC 里把利率从 2.5% 提到 3.5%，对产出和家庭财富有什么影响？为什么利率上升反而提高了产出？

> 帮我写一个三部门（家庭、企业、政府）的 SFC 模型，企业向家庭借款投资，先给我看交易流量矩阵。

也可以在终端直接运行（`<插件目录>` 是插件安装位置）：

```bash
python3 <插件目录>/skills/sfc-modeler/scripts/sfc_doctor.py
python3 <插件目录>/skills/sfc-modeler/scripts/sfc_run.py <插件目录>/skills/sfc-modeler/examples/pc.py --describe
python3 <插件目录>/skills/sfc-modeler/scripts/sfc_run.py <插件目录>/skills/sfc-modeler/examples/pc.py \
    --warmup 500 --periods 40 --shock Rbar=0.035@5 --plot Y,C --plot V
```

模型文件的写法、全部选项和常见错误见 [`skills/sfc-modeler/SKILL.md`](skills/sfc-modeler/SKILL.md) 和
[`skills/sfc-modeler/reference.md`](skills/sfc-modeler/reference.md)。

## 结构

```
sfcmodeler/
├── package.json            # dsh.bundle 声明，不打包任何依赖
├── cordis.patch.yml        # 挂载本包的插件
├── index.js                # 用 dsh 自带的 skill-filesystem provider 挂载 skills/
├── locale/{en,zh}.json     # 插件管理器中显示的标题与描述
├── icon.svg
├── LICENSE, NOTICE         # 上游的 Apache-2.0 许可和改动说明
├── test.mjs                # node --test test.mjs
└── skills/sfc-modeler/
    ├── SKILL.md            # 工作流程（中文）
    ├── reference.md        # SFCmodeler API 速查
    ├── scripts/            # sfc_doctor.py、sfc_run.py
    ├── examples/           # sim.py、pc.py、pc_matrices.py、lp.py
    └── vendor/             # 上游 SFCmodeler 源码与 LICENSE（未修改）
```

## 测试

```bash
cd sfcmodeler
node --test test.mjs                                   # 插件外壳测试；找不到依赖齐全的 Python 时跳过集成测试
SFC_PYTHON=/path/to/python node --test test.mjs        # 指定 Python，运行四个示例的端到端测试
```

## 许可

Apache License 2.0。SFCmodeler © Sam Levey，见 [LICENSE](LICENSE) 和 [NOTICE](NOTICE)。
