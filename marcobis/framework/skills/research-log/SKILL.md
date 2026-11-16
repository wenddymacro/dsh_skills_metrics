---
name: research-log
description: >
  自动记录计量分析工作流中的每个决策、每次迭代及其理由。MaRCo@BIS 套件中任何其他 skill 完成一个
  阶段时，或用户要求审计轨迹、可复现日志或会话摘要时使用。
---

# 研究日志

## 目的

为分析保留完整的、带时间戳的记录，保证可复现。这份日志会成为已发表论文复现附录的基础。

## 记录什么

主控的每个阶段都写一条记录。每条记录包含：

```
log_entry:
  timestamp: ISO 8601
  stage: "knowledge_base_init" | "intake_triage" | "model_selection" |
         "specification" | "data_retrieval" | "data_disposition" |
         "estimation" | "diagnostics" | "sensibility_check" |
         "revision" | "final_results" | "tool_review" | "disposition"
         # 在估计之前暂停的会话，仍然以一条 "disposition" 记录结束
         # （decision: continue），其 next_steps 记录从哪里继续。
  iteration: integer（首次尝试为 1，每次修改递增）
  inputs: 本阶段收到的内容摘要
  outputs: 本阶段产出的内容摘要
  decisions:
    - description: 决定了什么
      rationale: 为什么（经济或统计上的理由）
      alternatives_considered: 还有哪些可选做法
      knowledge_source: user | dictionary | knowledge_base | parametric | data_driven
                        # 依据的是 specification skill 来源优先顺序中的哪一层
                        # （CLAUDE.md 规则 3）
      human_confirmed: bool
  flags: 提出的任何警告或顾虑
  code_hash: 所用脚本的 SHA-256（可选；总要记录脚本路径；方便时也记录哈希，例如
             hashlib.sha256(Path(__file__).read_bytes()).hexdigest()）
```

使用国家统计局数据时，在数据获取阶段的记录里写明面板的 `vintage`（来自
`data/nbs_*/metadata.yaml`）和所用的清洗步骤（累计值换算、1 月填补、定基指数链接），因为它们
会影响结果。

## 存储

- **会话期间：**把各阶段的记录追加到运行 `outputs/` 目录中 `session_research_log.json` 的
  `entries` 数组里（结构见下）。
- **文件名分层：**复现 / 应用脚本会把一个*运行级*的 `research_log.json`（单次执行的来源记录）
  写进它们的 `outputs/`，重跑时会被替换。这个文件名只留给脚本的运行来源记录；会话决策绝不写进去。
- **会话记录不能重新生成：**`session_research_log.json`、`research_log.md` 和 `run_state.json`
  放在已 gitignore 的 `outputs/` 目录里，重跑也不会重建。删除 `outputs/` 之前先把它们复制出来
  （见主控第 7 阶段的"丢弃"选项）。
- **跨会话延续：**后来的会话接着做一项处置为"继续迭代"的工作时，*扩展*已有的日志，而不是从头
  开始：追加新会话的阶段记录，把之前的处置保留在 `disposition_history` 数组中（最新的处置为准），
  并延续 `version_history` 的编号（恢复的会话的第一个新设定是 v(n+1)，不是 v1）。之前会话已确认
  的决策视为*已定*：重新确认，不要重新决定；任何真正被重新打开的决策，都作为一条 `revision`
  记录，并写明触发原因。
- **版本追踪：**每次修改都生成一个新版本。旧版本从不删除。会话日志是一个对象，包含阶段记录
  `entries`、`disposition_history`、`version_history` 和任何 `branches`：

  ```json
  {
    "entries": [...],
    "disposition_history": [...],
    "version_history": [
      {
        "version": "v1",
        "created": "2026-04-11T10:30:00Z",
        "status": "superseded by v2",
        "changed_in_next": ["加入汇率变量"],
        "stages": [...]
      },
      {
        "version": "v2",
        "created": "2026-04-11T11:15:00Z",
        "parent": "v1",
        "status": "current",
        "changes_from_parent": ["把 NEER 加入内生变量",
                                 "更新 Cholesky 顺序"],
        "stages": [...]
      }
    ],
    "branches": {
      "main": "v2",
      "robustness_8lags": "v2-alt1"
    }
  }
  ```

- **完成时：**生成一份人类可读的 Markdown 摘要（`research_log.md`），可以作为附录或补充材料。
  包含一节版本历史，说明试过什么、改了什么、为什么改。
- **代码存档：**可运行的脚本放在其层级目录下（`scripts/<tier>/<id>/replicate.py`），*不*在日志
  目录中复制一份。在日志中记录脚本路径和每个版本的内容哈希，只保存版本之间的差异，绝不保存脚本的
  平行副本。
- **生成差异：**向用户展示一次修改时，agent 写出一份人类可读的版本间差异，突出设定、结果和解释
  上的变化。

## 运行状态文件（`run_state.json`）

研究日志是*记录*；`run_state.json` 是*指针*：一个极小的、机器可读的运行进度标记，设计目标是
经得起上下文压缩、中断和话题转换。主控的
[运行完成契约](../orchestrator/SKILL.md#运行完成契约)在结束任何一段工作之前读取它；本节规定
它的结构。

### 位置

与会话研究日志放在一起，位于运行同目录的 outputs 中：
`scripts/<tier>/<id>/outputs/run_state.json`，与 `outputs/` 中的其他内容一样被 gitignore。
每次运行一个文件。

### 结构

```json
{
  "run_id": "eu_commodity_spillover",
  "script_dir": "scripts/applications/eu_commodity_spillover/",
  "mode": "C",
  "current_stage": 5,
  "stages_completed": [1, 2, 3, 4],
  "status": "open",
  "disposition": null,
  "next_action": "向用户给出脉冲响应的合理性结论",
  "updated_at": "2026-07-04T09:12:00Z"
}
```

- `current_stage` / `stages_completed` 使用日志的数字阶段编号（0a/0b 步骤并入第 1 阶段，与
  Markdown 报告格式一致）。
- 第 7 阶段记录处置之前，`status` 为 `"open"`，之后为 `"closed"`。每种处置都会关闭这个文件，
  包括 `continue`（恢复的会话会重新打开它：`status: "open"`，并按上面的跨会话延续规则追加到同一份
  研究日志）。
- 处置决定后，`disposition` 与日志中的 `disposition.decision` 一致。
- `next_action` 是一句话：下一轮该做什么。保持更新：恢复的会话首先依据它行动。

### 生命周期

| 时刻 | 写入 |
|---|---|
| 第 1 阶段：模式已确认，工作目录已存在 | 创建，`status: "open"`、`current_stage: 1` |
| 每个阶段关口（与该阶段日志记录的追加同时） | 更新 `current_stage`、`stages_completed`、`next_action`、`updated_at` |
| 第 7 阶段：处置已记录 | 设 `status: "closed"`，填写 `disposition` |

### 读取时机

- **会话开始 / 上下文压缩之后：**对恢复的运行，做任何其他事之前先读它；`next_action` 说明从哪里
  接着做。
- **在结束任何一段工作的回复之前：**如果 `status` 为 `"open"` 且 `current_stage < 7`，指出待办的
  阶段：继续推进，或提出一个明确的、会被记录的推迟。绝不让一次运行沉寂。
- **第 7 阶段开始时：**在提出处置之前，列出已完成的内容。

## 工具提升队列

主控第 7 阶段的工具审查子步骤（见
[`skills/orchestrator/SKILL.md`](../orchestrator/SKILL.md#工具审查子步骤)）会产出"标记待提升"的
候选：本次会话 `replicate.py` 中写的、看起来可以复用但还没出现第二个调用者的内联辅助函数。它们
被追加到这里管理的一个跨会话队列中。

### 存储

`skills/research-log/tools_to_promote.yaml`：skill 根目录下的一个 YAML 文件，跨会话保存被标记的
候选。它被 gitignore。

### 结构

```yaml
candidates:
  - function: extract_cholesky_shock
    first_seen:
      session: "<date>-<run-id>"
      location: scripts/applications/<id>/replicate.py
      commit: "abc1234"
    appearances:
      - session: "<date>-<run-id>"
        location: scripts/applications/<id>/replicate.py
        commit: "abc1234"
      - session: "<later-date>-<run-id>"
        location: scripts/applications/<other-id>/replicate.py
        commit: "def5678"
    proposed_lib_home: scripts/lib/var.py
    proposed_signature: |
      def extract_cholesky_shock(fit: VARFit, shock_var: str) -> pd.Series:
          """Recover the structural shock for ``shock_var`` from a fitted VAR."""
          ...
    status: "queued"   # queued | promoted | rejected
    rationale: "通用的结构冲击提取；已有 2 个调用者，可放入 lib.var"
    notes: ""
```

### 合并触发

当第 7 阶段的工具审查发现某个候选的名称 + 签名与队列中已有的条目相符时，agent 把它标为**合并
机会**，建议现在就提升，而不是再标记一次。默认门槛是"第二个调用者"：签名相符的函数有 N ≥ 2 个
调用者时，建议提升。

"签名相符"的判断是保守的：名称相同、参数名相同、位置参数个数相同。如果名称相近但参数有出入
（例如 `extract_cholesky_shock(fit, shock_var)` 与 `extract_chol_shock(fit, var_name, sign=+1)`），
agent 指出不一致之处，并询问在提升之前是否要统一接口。

### 查询时机

主控在以下时刻查询 `tools_to_promote.yaml`：

- **第 7 阶段开始时：**提示"你有 N 个之前会话排队的候选，其中有没有与今天脚本里的辅助函数相符的？"
- **第 4 阶段开始时：**建议用户可能想直接作为基础函数用在生成的 `replicate.py` 中的可复用候选，
  而不是把同样的辅助函数再内联写一遍。（这是主动的合并步骤，能拦住"我正要写第三份
  `extract_cholesky_shock`"的情况。）

### 生命周期

- **排队中（queued）。**已标记，尚未提升。一直留在文件里，直到被提升或被明确拒绝。
- **已提升（promoted）。**函数已加入 lib。更新状态；条目保留历史记录（何时提升、由哪个会话、
  哪个提交）。
- **已拒绝（rejected）。**明确标记为"不提升，永远保持临时"，例如用户认定该函数虽然签名看起来
  通用，但实际专属于某篇论文，或该函数的逻辑更适合作为子 skill 而不是 lib 基础函数。保留状态，
  以免 agent 在以后的会话中再次提议。

### 何时审查队列本身

在任何开发会话（用户在改造框架本身；见 CLAUDE.md 第 1 步）开始时，agent 可以选择性地列出队列
内容（*"你有 N 个之前会话排队的工具候选，最该提升的是：……"*），免得推迟的合并在多次会话中被
遗忘。这是提示，不是必需步骤。

## Markdown 报告格式

```markdown
# 研究日志：[分析标题]

## 会话元数据
- 日期：……
- 工具版本：……
- 语言：Python 3.x / R 4.x
- 数据版本：……（例如 nbs_m vintage 2026-11-15）

（阶段编号与主控一致：0a/0b 步骤（知识库初始化，然后受理与分流）并入第 1 阶段的日志记录；
1 = 各模式的入口流程，2 = 设定，3 = 数据，4 = 估计，5 = 合理性，6 = 结果，7 = 处置。）

## 第 1 阶段：受理、分流与入口流程
[模式（A/B/C）、字典匹配（如有）、模型选择结果]

## 第 2 阶段：设定
[决策的文字摘要]

## 第 3 阶段：数据获取
[变量对应表、变换、注意到的差异]

## 第 4 阶段：估计（第 1 次迭代）
[模型细节、主要结果]

## 第 5 阶段：合理性检查（第 1 次迭代）
[哪些通过、哪些没通过、改了什么]

……

## 第 6 阶段：结果与报告
[最终结果：被接受的设定和主要发现的摘要]

## 第 7 阶段：处置与归档
[仅归档 / 保存为应用 / 提升为经典 / 继续迭代 / 丢弃：
所选选项 + 理由；工具提升标记（如有）]

## 附录：代码清单
[或指向 scripts/ 目录]
```

## 其他 skill 怎样使用

agent 按上面定义的 `log_entry` 结构把记录追加到会话日志，并用 `VARReport.add_research_log`
把日志附到报告中。

research-log skill 负责序列化和格式化。其他 skill 不需要直接管理日志文件。
