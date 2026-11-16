# 应用

这一层存放**应用实例**：*用*框架做的、超出经典复现范围的分析：经典设定的变体（新样本、新经济体）、
针对本地数据的改编，以及比较性或方法性的研究。每个目录都是一份独立、可重跑的研究：读 README，运行
`replicate.py`，得到产出。

## 起点

这个目录初始为空，在使用中逐渐填满：每次第 7 阶段选择"保存为应用"，都会在这里建一个目录。目录的
结构和标准可以参照经典复现，例如
[`scripts/replications/uhlig_2005_sign_restrictions/`](../replications/uhlig_2005_sign_restrictions/)
（一个经过核验的字典条目端到端运行，带有记录在案的 FRED 替代数据），或
[`scripts/replications/gali_1999_technology_var/`](../replications/gali_1999_technology_var/)
（一个完全可复现的端到端示例，只需按 `data/fred_qd/UPDATE.md` 下载一次预置的 FRED-QD 面板）。

## 工作放在这里还是 `scripts/replications/`

| 目录 | 放什么 |
|---|---|
| [`scripts/replications/<id>/`](../replications/) | 经典复现，公共示例库。每个都对应一个已对照论文核对的字典条目。 |
| `scripts/applications/<id>/` | 你自己的分析：变体、本地改编、比较研究（包括用国家统计局数据做的中国分析）。如果有对应的字典条目，通常附带一条设定偏离说明。 |

## 新目录怎样产生：第 7 阶段处置

一次运行完成后，主控的[第 7 阶段（处置与归档）](../../skills/orchestrator/SKILL.md)会询问如何处理
刚生成的代码。**"保存为应用"**是成功的模式 B 和模式 C 运行的默认选项，它在这一层创建一个目录：运行的
README、配置和脚本保存在这里。生成的产出可以再生；`outputs/` 中的会话记录不能（见下面"保留什么、
再生什么"）。

## 目录约定（与复现相同的结构）

```
applications/
└── <id>/
    ├── README.md            问题、设定 + 偏离、结果、注意事项、运行方法
    ├── config.yaml          设定选择（如有字典条目，与之对应）
    ├── replicate.py         薄的编排脚本；调用 scripts/lib/
    ├── paper_targets.yaml   （可选）用于验证的论文数值
    └── outputs/             生成的报告 + 数值快照（gitignore）
```

id 应当描述这项分析：`uhlig_2005_updated_us`、`fiscal_lp_state_dependence`、`cn_monetary_bvar`
等。使用 snake_case。

## 保留什么、再生什么

- **保留**（如果你的副本使用版本管理，就提交）：`README.md`、`config.yaml`、`replicate.py`（以及
  `paper_targets.yaml`，如有）。这是你的智力成果，可以跨机器、跨会话恢复。
- **可再生**：`outputs/` 中生成的文件（报告、数值快照、运行级的 `research_log.json`），由脚本 + 数据
  重建。自带的 [.gitignore](../../.gitignore) 已经排除了嵌套的 `outputs/` 目录，不需要额外设置。
- **不可再生（删除 `outputs/` 之前先复制出来）**：agent 写在那里的会话记录
  （`session_research_log.json`、可选的 `research_log.md` 和 `run_state.json`）。它们保存了对话中的
  决策、关口和续接状态，任何重跑都无法重建；而且因为 `outputs/` 不纳入版本管理，它们不会和你的其他
  工作一起提交。

## 主控的行为

模式 A 的查找会搜索示例库的两个层级：

1. [`scripts/replications/<id>/`](../replications/)：经典（排在前面）。
2. `scripts/applications/<id>/`：你过去的工作（以"你做过类似的，要从那里开始吗？"的形式提出）。

干净的经典匹配优先。个人应用作为用户可以选择的建议出现，不是默认选项。

## 提升为经典

如果一个应用成熟为忠实于原文、经过严格核验的工作（例如你完全复现了一篇经典论文），就提升它：把目录
从 `scripts/applications/<id>/` 移到 `scripts/replications/<id>/`，并更新字典条目的核验记录（见
[模型字典](../../skills/model-dictionary/SKILL.md)）。这很少见；大多数应用一直是应用。
