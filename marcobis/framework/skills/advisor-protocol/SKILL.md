---
name: advisor-protocol
description: >
  与具体模型无关的升级规程，用于复杂的数学推理、推导核验和理论验证。执行任务的 agent 遇到论文中
  密集的数学内容、陌生的识别方案、不标准的先验推导，或者对"把数学正确地转成代码"把握不足时使用。
  本 skill 把问题转给一个推理能力更强的模型；具体的服务商和模型可以配置，不写死。
---

# 顾问规程

## 目的

执行任务的 agent 负责常规工作流。当数学内容超出它的把握时，它请一个能力更强的推理模型在继续之前
检查工作，就像研究人员遇到棘手推导时请教资深同事一样。

## 何时升级

执行任务的 agent 在以下情况下调用顾问：

1. **陌生的推导。**论文引入了 agent 无法有把握地核验的记号、分布假设或代数步骤。
2. **新的识别方案。**带复杂惩罚函数的符号约束、带不等式约束的叙事识别，或集合识别模型。
3. **不标准的先验。**`scripts/lib/bvar.py` 模块 docstring 或 `CONVENTIONS.md` 没有涵盖的任何先验
   结构。
4. **分布理论。**涉及非共轭情形、对冗余参数积分，或渐近近似的后验推导。
5. **含糊的数学记号。**论文的记号前后不一致或依赖上下文，agent 不确定正确的理解。
6. **交叉核对实现。**写完一个复杂公式的代码后，agent 可以请顾问核验代码与数学是否一致。

**以下情况不要升级：**常规矩阵代数、标准 OLS/GLS、文档完备的 Minnesota 先验计算、基本的时间
序列变换，或已核验参考文档中已有的任何内容。

## 顾问配置

顾问默认关闭。每次调用之前，先读工作区根目录 `config.yaml` 中的 `advisor.enabled`。如果不是
`true`，就不要调用顾问：告诉用户这一步通常需要升级，然后在没有顾问的情况下继续，并建议手工核对
推导或启用顾问。

顾问在工作区根目录 `config.yaml` 的 `advisor:` 下配置（`enabled`、服务商、模型、接口地址、
`api_key_env`、可选的备用服务商，以及设置：`max_attempts`、`timeout_seconds`、
`log_all_exchanges`、`require_human_review`）。那里写的模型只是示例；要设置成用户能用的模型。由
用户或管理员设置一次；agent 在运行时读取。

agent 通过配置的服务商 API 发送查询；代码库本身不实现顾问调用。

## 升级流程

### 第 1 步：准备查询

执行任务的 agent 为顾问构造一个结构化的提示：

```
CONTEXT:
I am implementing [model/method] from [paper reference].
The executing environment is [Python/R/Julia].

MATHEMATICAL CONTENT:
[Extract the relevant equations, definitions, and notation from the paper.
Include surrounding context so the advisor understands the setup.]

SPECIFIC QUESTION:
[One of:]
- "Verify that the following derivation is correct: [steps]"
- "Translate this mathematical expression into pseudocode: [expression]"
- "This paper uses notation X for Y. Please confirm my interpretation: [interpretation]"
- "I have implemented this formula as [code]. Verify it matches the mathematics."
- "Derive the posterior distribution for [parameter] given [prior] and [likelihood]."

CONSTRAINTS:
- Provide step-by-step reasoning.
- Flag any assumptions that are implicit in the paper but should be made explicit.
- If the derivation has multiple valid interpretations, list them.
- Express the final result in explicit matrix notation with dimensions annotated.
```

（提示模板保留英文，便于各家模型理解；也可以改用中文提问。）

### 第 2 步：调用顾问

通过配置的服务商 API 以标准请求发送查询，除了 API 格式转换之外不写服务商专属的逻辑。主服务商失败
且设置了备用服务商时，改用备用服务商。没有任何服务商响应时，告诉用户在继续之前手工核对数学内容。

### 第 3 步：处理回复

1. 解析顾问的回复。
2. 提取：经过核验的推导步骤、伪代码、指出的假设，以及任何其他可能的理解。
3. **交给人审阅**（如果 `require_human_review` 为 true）。审阅发生在调用之后、使用回复之前。
4. 通过 research-log skill 记录完整的交互。

### 第 4 步：纳入工作流

人确认顾问的产出之后：

1. 把核验过的推导保存为参考文档，放在相关 skill 的 `references/` 目录（首次使用时创建；例如
   `<skill-name>/references/verified_xyz_derivation.md`），或者放在需要它的 lib 模块旁边
   （例如 `scripts/lib/references/verified_xyz_derivation.md`）。
2. 用伪代码实现公式。
3. 参考文档会保留下来，以后运行同一方法时不必再次升级。

这样随着时间推移，会积累起一个不断增长的、经过核验的数学内容库。

## 成本管理

相对于常规执行，顾问调用很昂贵。每次会话，agent 在研究日志中记录顾问调用次数、每次调用的 token
数，以及按服务商公开价格估算的成本。如果在意成本，用户可以：

- 要求 agent 每次调用顾问之前先征得用户同意（这是调用之前的明确步骤；`require_human_review`
  是在调用之后审阅回复，所以省不了成本）
- 用本地模型做顾问，不花钱但审阅质量可能较低
- 预先在 `references/` 中放入核验过的内容，减少以后的升级

## 机构部署的考虑

央行和研究机构可能有：

- **物理隔离的网络。**用本地部署的模型做顾问。
- **数据保密约束。**顾问提示中绝不能包含专有数据，只能包含已发表论文或工作论文中的数学内容。本
  skill 要求 agent 只发送公式和推导，绝不发送数据集或专有数据。这是一条政策，不是技术过滤。
- **获批供应商名单。**可配置的服务商机制能满足这一点：配置中只设置获批的服务商。
- **审计要求。**agent 在研究日志中记录每一次顾问交互，包括时间戳、提示、回复和人工确认状态。
