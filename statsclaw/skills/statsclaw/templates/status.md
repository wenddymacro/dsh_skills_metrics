# 运行状态

```
Request ID: [request-id]
项目: [项目名]
目标路径: [绝对路径]
语言 profile: [profile]
工作流: [1–7]
运行模式: [团队 / 子代理 / 串行]
当前状态: PLANNED
下一步: [动作]
基线: [git commit 哈希 / baseline/ 目录 / 无]
最后更新: [YYYY-MM-DD HH:MM]
```

## 状态机

```
NEW → PLANNED → SPEC_READY → PIPELINES_COMPLETE → DOCUMENTED → REVIEW_PASSED → DONE
```

中途状态：`HOLD`（等用户回答）、`BLOCKED`（tester 判定失败）、`STOPPED`（reviewer 不放行）。

## 产物台账

| 产物 | 负责角色 | 线 | 状态 | 完成时间 |
| --- | --- | --- | --- | --- |
| request.md | leader | — | pending | |
| impact.md | leader | — | pending | |
| comprehension.md | planner | 理解 | pending | |
| spec.md | planner | → 代码 | pending | |
| test-spec.md | planner | → 测试 | pending | |
| sim-spec.md | planner | → 仿真 | pending | |
| implementation.md | builder | 代码 | pending | |
| simulation.md | simulator | 仿真 | pending | |
| audit.md | tester | 测试 | pending | |
| ARCHITECTURE.md | scriber | 记录 | pending | |
| log-entry.md | scriber | 记录 | pending | |
| docs.md | scriber | 记录 | pending | |
| review.md | reviewer | 汇合 | pending | |

## 隔离核对

| 检查 | 结果 |
| --- | --- |
| builder 只拿到 spec.md | pending |
| tester 只拿到 test-spec.md | pending |
| simulator 只拿到 sim-spec.md | pending |
| reviewer 拿到全部产物 | pending |

## 派发记录

| 子级名 | 角色 | 次数 | 结果 | 备注 |
| --- | --- | --- | --- | --- |

## 未决风险

_无。_

## 阻塞原因

_未阻塞。_

只有 leader 可以修改本文件；每次状态变化立即写入。
