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

支持的工作流：代码修改、仅文档、仿真 + 代码、仅仿真、仅验证、仅审查、小改动的简化流程（需要你确认），以及发布检查（SSC / PyPI / CRAN 发布前的打包核对）。

## 语言包与维护者规范

角色手册是通用的，语言相关的内容放在 `skills/statsclaw/references/profiles/` 的**语言包**里，按项目里的标志文件自动选择：

| 语言包 | 形式 | 内容 |
|---|---|---|
| **Stata** `profiles/stata/` | 目录 | 编码约定（ado / Mata 骨架、eclass/rclass、错误码、数值、随机数）、验证方法（`cscript` 认证脚本、对照 `regress` / `ivregress` / `reghdfe` 等基准命令、`git archive` 取旧版做前后对比、临时目录 `net install`）、SMCL 帮助文件与 `.pkg` / `stata.toc` 打包、27 条静默错误清单、仿真写法（`simulate` / `postfile`）、`run_stata.sh`、`stata_pkg_check.py`、认证脚本 / sthlp / pkg 模板，以及**每个角色的 Stata 须知** |
| **Python** `profiles/python/` | 目录 | 上游的 Python profile，加开工检查（环境工具识别）、写入范围建议、仿真注意事项和发布检查（build、twine check、临时环境安装） |
| R、Julia、TypeScript、Go、Rust、C、C++ | 单个文件 | 上游 StatsClaw 的 profile（R 有完整的 CRAN 提交清单） |

**维护者规范**是你自己的习惯，优先级高于语言包：

| 文件 | 写什么 |
|---|---|
| `profiles/maintainer.md` | 跨语言：作者与许可、版本号规则、提交习惯、默认容差、文档语言、发布流程 |
| `profiles/stata/maintainer.md` | 你维护的 Stata 命令：目录布局、文件头和版本格式、编码和返回值习惯、认证脚本写法、帮助文件习惯、发布流程、踩过的坑 |
| `profiles/python/maintainer.md` | 你维护的 Python 包：布局与工具链、版本来源、API 风格、数值断言默认容差、基准包、文档和发布流程 |

三个文件目前是带提纲的空模板，第一行有 `statsclaw:maintainer-template 未填写` 标记，角色会跳过它们；填写后删掉这一行即生效。

规定冲突时的优先级（高 → 低）：项目的 `.statsclaw/context.md` > 该语言的 `maintainer.md` > 跨语言的 `maintainer.md` > 语言包其余文件 > 角色手册的通用做法。**规格隔离和容差完整性两条规则不受任何规范覆盖。**

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
- 目标项目所用语言的运行环境，例如 Stata 16+（自动查找，找不到时设置 `STATA_BIN`）、Python（`pytest` 等）、R（`devtools`、`testthat`）。缺少运行环境时测试者会如实报告，组长会请你安装或提供路径。
- Stata 包的静态检查 `stata_pkg_check.py` 需要 Python 3（只用标准库）。
- 缺少第三方包（SSC、CRAN、PyPI）时，团队会告诉你缺什么，**不会自动安装**。
- 读 PDF 论文时会用 `pdftotext` 或 Python 的 `pypdf` / `pdfplumber`；读 Word 用 `pandoc` 或 `python-docx`。都没有时规划者会请你提供文字版。

## 安装

**桌面版**：打开「插件 → 添加插件」，填入下面的地址，点击「安装」，再点击「立即启用」。`#` 后面是提交号，下面是目前最新的版本；要装别的版本，换成对应的提交号。

```text
github:wenddymacro/dsh_skills_metrics#d1cf3a3b235e3112375182fb08a73c7a43b5700a&path:/statsclaw
```

**命令行**（CLI 管理的 profile）：

```bash
dsh plugin --profile <profile> add "github:wenddymacro/dsh_skills_metrics#d1cf3a3b235e3112375182fb08a73c7a43b5700a&path:/statsclaw"
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
│   │   ├── profiles/
│   │   │   ├── maintainer.md        # 跨语言维护者规范（模板）
│   │   │   ├── stata/               # Stata 语言包：profile.md、maintainer.md、四份参考、simulation.md、
│   │   │   │                        #   run_stata.sh、stata_pkg_check.py、templates/
│   │   │   ├── python/              # Python 语言包：profile.md、maintainer.md
│   │   │   └── r-package.md …       # 其余语言的单文件 profile
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

检查 manifest、patch 与生成器输出一致、preset 的 id 和顺序、派发工具只允许派给六个角色、只有组长能派发和提问、审查者不能编辑文件、人设里没有会被 DSH 当作变量解析的 `{{`、角色手册写明了隔离规则和语言包优先级、语言包的文件齐全、维护者模板带未填写标记、skill 引用的文件都存在、`apply()` 的挂载方式，以及 `stata_pkg_check.py` 在干净包、问题包和模板上的结果和 `run_stata.sh` 的参数校验；本机有 Stata 时还会用认证脚本模板实际跑一次。

这些是离线检查。多角色调度需要在 DSH 桌面版里实际跑一次才能确认。

## 作者、许可与致谢

作者：Wenli Xu。采用 MIT 许可，见 [LICENSE](LICENSE) 和 [NOTICE](NOTICE)。

本插件基于 Tianzhu Qin 和 Yiqing Xu 的 [StatsClaw](https://github.com/statsclaw/statsclaw)（提交 `3de2edf`，MIT 许可）改编和扩展：

- 把 Claude Code 的 agent 定义改写成 DeepSeek Harness 的 agent preset：组长 preset 带专用派发工具，只能派给六个角色 preset；
- 把角色手册和协议译为中文并精简，统一产物格式，保留理解核验、三规格隔离、容差完整性、修改前后对比、仿真验收和审查路由等核心规则；
- 去掉对 GitHub 的依赖（workspace 仓库、brain 共享库、凭证检查、shipper、issue 巡检），运行记录放在项目内的 `.statsclaw/`；
- 用写入范围划分和基线快照代替 git worktree 隔离；
- 新增子代理模式和串行模式，在没有组长 preset 的会话里也能用；
- 把语言 profile 改成可插拔的语言包，新增完整的 Stata 语言包（编码约定、认证脚本验证、帮助文件与打包、静默错误清单、仿真写法、`stata_pkg_check.py` 和模板）和 Python 语言包的开工与发布检查；
- 新增维护者规范层（跨语言、Stata、Python），优先级高于语言包，但不能覆盖隔离和容差规则；
- 新增发布检查工作流；`run_stata.sh` 复用本仓库 `statadataanalysis` 插件，静默错误清单部分整理自本仓库 `statadiagnose` 插件；
- 新增从角色手册生成 patch 的脚本和测试。

上游许可原文见 `skills/statsclaw/UPSTREAM-LICENSE.txt`。
