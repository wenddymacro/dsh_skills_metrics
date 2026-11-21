# 运行目录与产物格式

```text
<项目>/.statsclaw/                 # 已写入 .git/info/exclude，不进版本控制
├── context.md                     # 项目名、profile、常用命令、长期注意事项（leader 维护）
├── CHANGELOG.md                   # 每次运行一行：日期、request-id、摘要、结论（leader 维护）
├── HANDOFF.md                     # 最新的交接说明（leader 从 log-entry.md 摘录）
└── runs/<request-id>/
    ├── request.md                 # leader
    ├── impact.md                  # leader
    ├── status.md                  # leader（唯一可写者）
    ├── baseline/                  # leader，非 git 项目时保存修改前的文件
    ├── comprehension.md           # planner
    ├── spec.md                    # planner → builder（文档流程中 → scriber）
    ├── test-spec.md               # planner → tester
    ├── sim-spec.md                # planner → simulator（仿真流程）
    ├── implementation.md          # builder（文档流程中由 scriber 写）
    ├── simulation.md              # simulator
    ├── tester/                    # tester 自己的检查脚本和输出
    ├── audit.md                   # tester
    ├── ARCHITECTURE.md            # scriber
    ├── log-entry.md               # scriber
    ├── docs.md                    # scriber
    ├── review.md                  # reviewer
    └── mailbox.md                 # 所有角色追加写；不删改别人写的内容
```

## leader 写的文件

**request.md**：用户原话（照抄）；任务范围；验收标准（可检验的句子）；目标项目绝对路径；profile；工作流编号和运行模式；基线（commit 哈希和未提交改动列表，或 `baseline/`）；上传文件的绝对路径列表。

**impact.md**：受影响的文件和函数（附一句理由）；风险点（数值稳定性、公开 API、向后兼容、性能）；需要的角色；**每个写入角色的写入范围**（builder：ado、Mata、认证脚本目录如 `cert/`；simulator：仿真目录如 `sim/`、`simulations/`；scriber：`.sthlp`、README、示例 do-file）。写入范围互不重叠。

**status.md**：见 `templates/status.md`。

## mailbox.md 的写法

每条一段，开头写 `[时间] [角色] [类型]`，类型为：`HANDOFF`（交接说明）、`HOLD_REQUEST`（要问用户的问题）、`BLOCK`（失败和路由）、`INTERFACE`（接口变化，如新导出函数、签名变化）、`NOTE`（范围外发现的问题）。只追加，不修改已有内容。

## 角色产物要点

各角色手册里有完整要求，这里列出别人会依赖的部分：

| 产物 | 必须包含 |
|---|---|
| comprehension.md | 读过的全部材料；一段话复述需求；全部公式的重述和符号表；问过的问题和用户回答；结论 `FULLY UNDERSTOOD` / `UNDERSTOOD WITH ASSUMPTIONS`（逐条列出假设）/ `UNSPECIFIABLE`；HOLD 轮数 |
| spec.md | 符号表、算法步骤、输入校验、输出约定、数值约束、API（函数签名、参数、默认值）、语言相关说明；**不含**测试用例和期望输出 |
| test-spec.md | 行为约定、测试场景（输入、期望输出、容差）、边界情形、回归用例、性质不变式、外部基准、验证命令；仿真流程加"仿真验证"一节；**不含**实现细节 |
| sim-spec.md | 见 `simulation-study.md` 的七部分 |
| implementation.md | 改动文件列表及说明、改了什么、写了哪些单元测试、设计选择及理由、已知局限 |
| simulation.md | 设计摘要、代码文件、冒烟运行结果、验收标准初评、耗时估计、结论 `SIMULATED` 或 `HOLD` |
| audit.md | Per-Test 结果表、修改前后对比表（修 bug / 改算法 / 重构时必需）、实际运行的命令和输出、边界情形结果、仿真结果表（仿真流程）、环境信息、结论 `PASS` / `BLOCK` 及失败路由表 |
| log-entry.md | 见 `templates/log-entry.md` |
| docs.md | 改了哪些文档、为什么、示例是否实际运行过 |
| review.md | 隔离核对、规格交叉比对、收敛分析、容差核对、逐项检查清单、结论 `PASS` / `PASS WITH NOTE` / `STOP` 及路由 |

## 最后回答的第一行

子级的最后回答以一个词开头，leader 据此处理：

- planner：`DONE` 或 `HOLD`
- builder / simulator / scriber：`DONE` 或 `HOLD`
- tester：`PASS` 或 `BLOCK`
- reviewer：`PASS`、`PASS WITH NOTE` 或 `STOP`
