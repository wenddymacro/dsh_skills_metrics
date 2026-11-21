# statsclaw · DSH 插件

把 [StatsClaw](https://github.com/statsclaw/statsclaw) 的多角色统计软件开发团队做成 [DeepSeek Harness](https://github.com/deepseek-ai/deepseek-harness) 插件。适合"实现这篇论文的估计量"、"修这个 R 包的数值 bug"、"给新估计量做蒙特卡洛仿真"、"检查这个包能不能发布"这类统计软件包任务。

安装后会多出：

- **StatsClaw · 组长** preset：新建会话时选它。组长只负责规划、派发、核对和汇报，自己不写代码。它有一个专用派发工具 `statsclaw_dispatch`，只能派给下面六个角色。
- **六个角色 preset**：规划、编码、测试、仿真、文档、审查（`statsclaw-planner` … `statsclaw-reviewer`），由组长派发，一般不要直接选。每个角色的人设就是它的完整工作手册。
- **`statsclaw` skill**：组长协议。在普通会话里输入 `/statsclaw` 或说"用 StatsClaw 流程"也能用（见下文"三种运行模式"）。

## 工作方式

```
                      planner（规划）
                     /     |       \
            spec.md /  test-spec.md \ sim-spec.md
                   /       |         \
         builder（编码） ─ ─ ─ simulator（仿真）
                   \       |         /
                    \      v        /
                      tester（测试）      ← 编码、仿真都完成后
                           |
                      scriber（文档）
                           |
                      reviewer（审查）→ PASS / PASS WITH NOTE / STOP
```

1. **规划者**先读懂需求和上传的论文（PDF、Word、tex、图片），写 comprehension.md 自证理解；不懂的符号和假设会提问，最多 3 轮。然后写三份**互相隔离**的规格：spec.md 给编码者，test-spec.md 给测试者，仿真任务另写 sim-spec.md 给仿真者。
2. **编码者**只看 spec.md，实现代码和单元测试；**仿真者**只看 sim-spec.md，把估计量当黑箱写 DGP 和蒙特卡洛主循环；两者写入范围不重叠时可以同时进行。
3. **测试者**只看 test-spec.md，独立设计检查并运行 profile 的验证命令，输出 Per-Test 结果表、修改前后对比表，仿真任务还要跑完整仿真。**容差不可放宽**，失败一律 BLOCK，由组长重派负责的角色修正。
4. **文档者**画架构图（Mermaid）、写过程记录和用户文档。
5. **审查者**读全部产物，核对隔离、规格一致性、收敛、覆盖和每一个容差，给出结论；不通过就 STOP，并指明重派给谁。

三条流水线各自独立得到一致结果，才算可信。这就是 StatsClaw 的"对抗式验证"。

支持的工作流：代码修改、仅文档、仿真 + 代码、仅仿真、仅验证、仅审查，以及小改动的简化流程（需要你确认）。语言 profile 有 R、Python、Stata、Julia、TypeScript、Go、Rust、C、C++，按项目里的标志文件自动识别。

## 三种运行模式

| 模式 | 怎么进入 | 隔离程度 |
|---|---|---|
| 团队模式（推荐） | 新建会话时选 **StatsClaw · 组长** preset | 每个角色是独立的子级，有自己的 preset；派发提示里只出现该角色允许看的规格 |
| 子代理模式 | 普通会话里调用 `statsclaw` skill，会话有通用 `subagent` 工具 | 子级是全新的（看不到对话），先读角色手册再工作；隔离与团队模式基本一致 |
| 串行模式 | 普通会话没有任何委派工具 | 同一个 agent 依次扮演各角色，隔离只能靠纪律，组长会提醒你 |

## 和上游 StatsClaw 的区别

- **不需要 GitHub**：上游把运行记录推到远程 workspace 仓库、用共享 brain 仓库、由 shipper 推送和开 PR。这里全部去掉：运行记录放在项目内的 `.statsclaw/`（自动写进 `.git/info/exclude`，不会被提交），没有 brain/distiller/shipper。提交只在你要求时做；推送和开 PR 只在你明确要求、且本机配置好 git 远程时做。
- **不用 git worktree**：上游让编码、仿真、文档各在一个 worktree 里改。这里改为给每个写入角色划定互不重叠的写入范围；回滚靠开工时记录的基线（git 项目记 commit，非 git 项目把要改的文件复制到运行目录的 `baseline/`）。测试者需要"修改前"的数值时，用 `git archive` 把基线版本解到运行目录里另跑，不动你的工作区。
- **不自动巡检 issue**：没有 issue patrol 和定时循环。要修某个 issue，把内容贴给组长即可。
- **ARCHITECTURE.md** 默认只写在运行目录，你要求时才放到项目根目录。

## 依赖

- DeepSeek Harness ≥ 0.2.1-rc.1。团队模式要用到 DSH 自带的 agent preset、subagent（进程内 spawn）和 persona 插件，桌面版默认都有。
- 目标项目所用语言的运行环境，例如 R（`devtools`、`testthat`）、Python（`pytest`）、Stata、Julia。缺少运行环境时测试者会如实报告，组长会请你安装或提供路径。
- 读 PDF 论文时会用 `pdftotext` 或 Python 的 `pypdf` / `pdfplumber`；读 Word 用 `pandoc` 或 `python-docx`。都没有时规划者会请你提供文字版。

## 安装

**桌面版**：打开「插件 → 添加插件」，填入下面的地址，点击「安装」，再点击「立即启用」。`#` 后面是提交号，下面是目前最新的版本；要装别的版本，换成对应的提交号。

```text
github:wenddymacro/dsh_skills_metrics#bdbc85f0abaef6c4bd9e871c5dec2c9c65c3baf7&path:/statsclaw
```

**命令行**（CLI 管理的 profile）：

```bash
dsh plugin --profile <profile> add "github:wenddymacro/dsh_skills_metrics#bdbc85f0abaef6c4bd9e871c5dec2c9c65c3baf7&path:/statsclaw"
```

从本地 checkout 安装（便于开发）：

```bash
dsh plugin --profile <profile> add "link:/abs/path/to/dsh_skills_metrics/statsclaw"
```

安装或更换版本后需要重启 DeepSeek Harness，并**新建会话**：已有会话会继续用旧的 preset 定义。

## 使用

新建会话，选择 **StatsClaw · 组长**，然后直接说要做什么，例如：

> 当前目录是一个 R 包。按附件论文第 3 节实现双重稳健 DID 估计量，加到 `R/drdid.R`，并写单元测试。

> 对包里现有的 `ife_estimate()` 做蒙特卡洛仿真：N = 100、200、500、1000，正态和 t(3) 误差，看偏误、RMSE 和 95% 置信区间覆盖率。

> `estimate_se()` 在小样本下标准误偏小，修一下，修改前后对比给我看。

> 跑一遍 R CMD check --as-cran，看能不能提交 CRAN。

组长会先说明运行模式，在 `.statsclaw/runs/<request-id>/` 建运行目录，然后自动推进，每一步输出一行进度条。只有角色需要你回答问题时（HOLD）才会停下来问你。

## 结构

```
statsclaw/
├── package.json             # dsh.bundle 声明，不打包任何依赖
├── cordis.patch.yml         # 由 scripts/build-patch.mjs 生成：挂载 skill、组长 preset 和六个角色 preset
├── index.js                 # 用 dsh 自带的 skill-filesystem provider 挂载 skills/
├── scripts/build-patch.mjs  # 从角色手册生成 cordis.patch.yml；--check 检查是否过期
├── locale/{en,zh}.json      # 插件管理器中显示的标题与描述
├── icon.svg
├── LICENSE, NOTICE
├── skills/statsclaw/
│   ├── SKILL.md             # 组长协议：模式判断、开工步骤、工作流、派发模板、关口、信号、收尾
│   ├── references/
│   │   ├── roles/           # 六个角色的工作手册（同时是角色 preset 的人设）
│   │   ├── profiles/        # 九种语言的识别标志、验证命令和编码约定
│   │   ├── artifacts.md     # 运行目录布局和每个产物的必备内容
│   │   └── simulation-study.md
│   ├── templates/           # status.md、log-entry.md、ARCHITECTURE.md
│   └── UPSTREAM-LICENSE.txt
└── test.mjs                 # node --test test.mjs
```

改了 `references/roles/*.md` 之后要重新生成 patch：

```bash
node scripts/build-patch.mjs
```

## 测试

```bash
node --test test.mjs
```

检查 manifest、patch 与生成器输出一致、preset 的 id 和顺序、派发工具只允许派给六个角色、只有组长能派发和提问、审查者不能编辑文件、人设里没有会被 DSH 当作变量解析的 `{{`、角色手册写明了隔离规则、skill 引用的文件都存在，以及 `apply()` 的挂载方式。

这些是离线检查。多角色调度需要在 DSH 桌面版里实际跑一次才能确认。

## 作者、许可与致谢

作者：Wenli Xu。采用 MIT 许可，见 [LICENSE](LICENSE) 和 [NOTICE](NOTICE)。

本插件基于 Tianzhu Qin 和 Yiqing Xu 的 [StatsClaw](https://github.com/statsclaw/statsclaw)（提交 `3de2edf`，MIT 许可）改编和扩展：

- 把 Claude Code 的 agent 定义改写成 DeepSeek Harness 的 agent preset：组长 preset 带专用派发工具，只能派给六个角色 preset；
- 把角色手册和协议译为中文并精简，统一产物格式，保留理解核验、三规格隔离、容差完整性、修改前后对比、仿真验收和审查路由等核心规则；
- 去掉对 GitHub 的依赖（workspace 仓库、brain 共享库、凭证检查、shipper、issue 巡检），运行记录放在项目内的 `.statsclaw/`；
- 用写入范围划分和基线快照代替 git worktree 隔离；
- 新增子代理模式和串行模式，在没有组长 preset 的会话里也能用；
- 新增从角色手册生成 patch 的脚本和测试。

上游许可原文见 `skills/statsclaw/UPSTREAM-LICENSE.txt`。
