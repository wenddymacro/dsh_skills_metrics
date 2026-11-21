# statsclaw-stata · DSH 插件

[StatsClaw](https://github.com/statsclaw/statsclaw) 多角色团队的 **Stata 专用版**，做成 [DeepSeek Harness](https://github.com/deepseek-ai/deepseek-harness) 插件。适合"把这篇论文的估计量写成 Stata 命令"、"修这个 ado 的标准误"、"给命令加 `vce(cluster)` 选项"、"对这个命令做蒙特卡洛仿真"、"写 sthlp 帮助文件"、"检查能不能 `net install` / 提交 SSC"这类任务。

它和同仓库的通用版 [`statsclaw/`](../statsclaw/) 用同一套机制（组长 preset + 六个角色 preset + 规格隔离），但所有角色手册、验证方法和检查清单都按 Stata 写深了。两个插件的 preset 和工具名不冲突，可以同时安装。

## 安装后多出什么

- **StatsClaw Stata · 组长** preset：新建会话时选它。组长只规划、派发、核对、汇报，有专用派发工具 `statsclaw_stata_dispatch`，只能派给下面六个角色。
- **六个角色 preset**：`statsclaw-stata-planner`、`-builder`、`-tester`、`-simulator`、`-scriber`、`-reviewer`，由组长派发，一般不要直接选。
- **`statsclaw-stata` skill**：组长协议。在普通会话里输入 `/statsclaw-stata` 也能用（子代理模式或串行模式，见通用版 README）。

## 各角色在 Stata 里做什么

| 角色 | 只看 | 做什么 |
|---|---|---|
| 规划 | 需求、论文 | 读懂方法（PDF / Word / tex），写 comprehension.md；spec.md 写完整的 `syntax` 行、选项缩写和默认值、eclass/rclass、**全部 e()/r() 返回值**、每种非法输入的错误码；test-spec.md 写成可执行的断言（`mreldif`、`rcof`、`datasignature`），每个场景指定**基准命令**，并从静默错误清单里挑出相关场景 |
| 编码 | spec.md | 按约定写 ado / Mata：`*!` 版本行、`version`、`marksample`、`tempvar`、`sortpreserve`、`ereturn post ... esample()`、标准错误码、`cholsolve` 不显式求逆、`seed()` 选项不写死种子；写自己的认证脚本并冒烟运行 |
| 测试 | test-spec.md | `adopath ++` 指向项目并 `which` 核对版本；跑 `stata_pkg_check.py`；写自己的 `cscript` 认证脚本，对照 `regress`、`xtreg`、`ivregress`、`reghdfe`、`margins` 或论文数值；跑项目已有的认证脚本做回归；用 `git archive` 取出修改前版本做前后对比；在临时 PLUS 目录里 `net install` 检查打包。**容差不可放宽** |
| 仿真 | sim-spec.md | 用 `simulate` 或 `postfile` 写 DGP 和主循环，失败重复计入失败率，`rngstream` 分块并行；冒烟运行并估计完整耗时 |
| 文档 | 全部 | 按 SMCL 骨架写 `.sthlp`（Syntax 与 `syntax` 行一致、Stored results 与实际返回值一一对应、例子实际跑过、能 `translate`）；同步 sthlp 版本注释和 pkg 的 `Distribution-Date`；架构图和过程记录 |
| 审查 | 全部 | 通用版的全部核对，加上 Stata 代码约定、27 条静默错误、版本同步、打包检查 |

工作流：代码修改、仅文档、仿真 + 代码、仅仿真、仅验证、仅审查、简化（需确认），以及 **发布检查**（静态检查 + 临时目录 `net install` + 帮助文件转换 → 审查）。复现项目（只有 do-file）也支持，验证以 `master.do` 跑通、关键数值与基准一致、同种子可复现为准。

## 附带的工具和资料

```
skills/statsclaw-stata/
├── SKILL.md                         # 组长协议
├── references/
│   ├── roles/                       # 六个角色手册（同时是角色 preset 的人设）
│   ├── stata/conventions.md         # ado / Mata 编码约定：程序骨架、返回值、错误码、数值、随机数、依赖
│   ├── stata/testing.md             # run_stata.sh、认证脚本写法、基准命令对照表、前后对比、包装检查
│   ├── stata/helpfile-and-packaging.md  # SMCL 帮助文件、.pkg / stata.toc、发布清单
│   ├── stata/pitfalls.md            # 27 条 Stata 静默错误：缺失值、精度、排序、宏、注释吞代码、权重、共线、旧版 ado……
│   ├── simulation-study.md          # 仿真设计 + simulate / postfile 写法 + 指标计算
│   └── artifacts.md
├── scripts/
│   ├── run_stata.sh                 # 找到本机 Stata，批处理运行 do-file，报告 r(###) 和静默错误警告
│   └── stata_pkg_check.py           # 命令包静态检查（只用 Python 标准库）
└── templates/                       # cert_template.do、helpfile.sthlp、package.pkg、status.md、log-entry.md、ARCHITECTURE.md
```

`stata_pkg_check.py` 检查的内容：

- **ERROR**：ado 里没有与文件同名的 program；注释里有不闭合的 `/*`（会悄悄吞掉后面的代码）；公开命令没有帮助文件；`.pkg` 第一行不是 `v 3`，或列出的文件不存在；`stata.toc` 指向不存在的 pkg。
- **WARN**：缺 `*!` 版本行；主程序缺 `version`；eclass 命令没有设置 `e(cmd)`；ado 里写死了 `set seed`；用了 `merge m:m`；文件没列进 pkg；sthlp 和 ado 的版本号不一致。

```bash
python3 skills/statsclaw-stata/scripts/stata_pkg_check.py [--json] <项目目录>
```

## 依赖

- DeepSeek Harness ≥ 0.2.1-rc.1（团队模式要用 DSH 自带的 agent preset、subagent 和 persona 插件，桌面版默认都有）
- 本机 Stata 16 及以上版本：会自动查找；找不到时设置 `STATA_BIN`，例如 `/Applications/StataNow/StataMP.app/Contents/MacOS/stata-mp`
- Python 3（运行 `stata_pkg_check.py`，只用标准库；没有时测试者按同样的清单人工检查）
- 作为基准的第三方命令（如 `reghdfe`、`ivreg2`）缺失时，团队会告诉你，**不会自动 `ssc install`**

## 安装

**桌面版**：打开「插件 → 添加插件」，填入下面的地址，点击「安装」，再点击「立即启用」。`#` 后面是提交号，下面是目前最新的版本；要装别的版本，换成对应的提交号。

```text
github:wenddymacro/dsh_skills_metrics#<commit>&path:/statsclaw-stata
```

**命令行**（CLI 管理的 profile）：

```bash
dsh plugin --profile <profile> add "github:wenddymacro/dsh_skills_metrics#<commit>&path:/statsclaw-stata"
```

从本地 checkout 安装（便于开发）：

```bash
dsh plugin --profile <profile> add "link:/abs/path/to/dsh_skills_metrics/statsclaw-stata"
```

安装或更换版本后需要重启 DeepSeek Harness，并**新建会话**。

## 使用

新建会话，选择 **StatsClaw Stata · 组长**，直接说要做什么，例如：

> 当前目录是一个 Stata 包。按附件论文第 2 节实现 `drdid` 命令（双重稳健 DID），支持 `vce(cluster)` 和 pweight，返回 e(b)、e(V)、e(N)，写帮助文件。

> `myreg` 在有缺失值时 e(N) 不对，修一下，修改前后对比给我看。

> 对 `myreg` 做蒙特卡洛：N = 100、500、1000，正态和 t(3) 误差，各 2000 次，看偏误、RMSE 和 95% 覆盖率。

> 检查这个包能不能 net install、帮助文件有没有问题，准备提交 SSC。

组长会先检查本机 Stata，判断是命令包还是复现项目，在 `.statsclaw/runs/<request-id>/` 建运行目录，然后自动推进，每步输出一行进度条；只有角色需要你回答问题时才停下来问你。

## 开发

改了 `skills/statsclaw-stata/references/roles/*.md` 之后重新生成 patch：

```bash
node scripts/build-patch.mjs          # 生成 cordis.patch.yml
node scripts/build-patch.mjs --check  # 检查是否过期
node --test test.mjs
```

测试检查 manifest、patch 与生成器一致、preset 和派发工具的约束、人设里没有 `{{`、角色手册写明隔离规则、Stata 参考文件齐全、与通用版 preset 不冲突，以及 `stata_pkg_check.py` 在干净包、问题包、模板上的结果和 `run_stata.sh` 的参数校验；本机有 Stata 时还会用认证脚本模板实际跑一次。多角色调度需要在 DSH 桌面版里实际跑一次才能确认。

## 作者、许可与致谢

作者：Wenli Xu。采用 MIT 许可，见 [LICENSE](LICENSE) 和 [NOTICE](NOTICE)。

本插件基于 Tianzhu Qin 和 Yiqing Xu 的 [StatsClaw](https://github.com/statsclaw/statsclaw)（提交 `3de2edf`，MIT 许可）改编和扩展。在同仓库通用版 `statsclaw` 的改动（DSH preset 化、中文化、去掉 GitHub 依赖、用写入范围和基线快照代替 worktree、子代理和串行模式）之外：

- 把六个角色手册按 Stata 命令包开发重写：接口规格写到 `syntax` 行、返回值和错误码，验证用认证脚本对照基准命令，文档按 SMCL 骨架；
- 新增 Stata 编码约定、验证方法、帮助文件与打包、27 条静默错误清单四份参考资料，以及 Stata 版仿真写法；
- 新增 `stata_pkg_check.py` 静态检查、认证脚本 / 帮助文件 / pkg 模板、发布检查工作流；
- 复用本仓库 `statadataanalysis` 插件的 `run_stata.sh`；静默错误清单部分整理自本仓库的 `statadiagnose` 插件。

上游许可原文见 `skills/statsclaw-stata/UPSTREAM-LICENSE.txt`。
