# statadiagnose · DSH 插件

把一个 Stata 结果诊断的 skill 做成 [DeepSeek Harness](https://github.com/deepseek-ai/deepseek-harness) 插件。安装后，每个会话的 skill 目录里会多出
`stata-diagnose`：当你说"回归结果不对"、"这个数怎么变了"、"do-file 报错"、"复现不出来"、"昨天还能跑"时，agent 会按"定义症状 → 复现 → 最小化 → 列假设 → 插桩定位 → 修复"的流程找出根本原因，而不是乱试乱改。

纪律只有两条：**复现之前不改代码；说清原因之前不修。**

- **Step 0 / Phase 0**：先复述代码本来该做什么，钉住期望值（及其依据和容差）与实际值，等你确认
- **Phase 1–2**：固定 `version`、种子、`sortseed`，记录环境和 ado 版本，稳定复现后剪出最小可复现例子（MWE）
- **Phase 3**：先列出全部候选原因再排序，重点是 Stata 不报错、只悄悄算错的情形——字符串 / 数值类型与 `float` 精度、缺失值 `.` 是正无穷、`merge m:m` 与重复键、聚类和权重类型、共线被 omitted、singleton、不收敛、坏控制、排序依赖、ado 与 Stata 版本差异
- **Phase 4**：用 `count`、`isid`、`tab _merge`、`ereturn list` 等插桩二分定位到具体一行
- **Phase 5**：在根源处做最小修复，重跑 MWE 和完整 do-file 核对，并加一条防护断言（如 `merge 1:1 ..., assert(match)`）

诊断报告写到 `quality_reports/diagnoses/YYYY-MM-DD_<slug>.md`。说"只诊断不改"或带上 `--no-fix` 时，只点名原因、写报告，不改任何源文件。

**图文使用指南：[docs/GUIDE.md](docs/GUIDE.md)**（从安装到读懂结果，附 DeepSeek Harness 桌面版实测截图）

![根本原因](docs/images/06-ask-cause.jpg)

## 依赖

- DeepSeek Harness ≥ 0.2.1-rc.1
- 本机 Stata 16 及以上版本（会自动查找；找不到时设置 `STATA_BIN`，例如
  `/Applications/StataNow/StataMP.app/Contents/MacOS/stata-mp`）

## 安装

**桌面版**：打开「插件 → 添加插件」，填入下面的地址，点击「安装」，再点击「立即启用」。`#` 后面是提交号，下面是目前最新的版本；要装别的版本，换成对应的提交号。

```text
github:wenddymacro/dsh_skills_metrics#fea1e496d187b5dc34d9e4b41789f0616ee583fa&path:/statadiagnose
```

**命令行**（CLI 管理的 profile）：

```bash
dsh plugin --profile <profile> add "github:wenddymacro/dsh_skills_metrics#fea1e496d187b5dc34d9e4b41789f0616ee583fa&path:/statadiagnose"
```

从本地 checkout 安装（便于开发）：

```bash
dsh plugin --profile <profile> add "link:/abs/path/to/dsh_skills_metrics/statadiagnose"
```

如果把已安装的插件换成另一个来源或版本，需要重启 DeepSeek Harness，新代码才会生效。

## 使用

直接用自然语言提问即可，例如：

> analysis_divorce/02_twfe.do 换了新版 controls.dta 之后，udl 的系数从 0.123 变成了 0.087，设定没动，帮我查原因。

> 这个 do-file 跑到第 40 行报 r(459)，帮我 debug，只诊断不改。

也可以输入 `/stata-diagnose` 显式调用这个 skill。从头做一个分析时，配合同仓库的 [`statadataanalysis`](../statadataanalysis/) 插件。

## 结构

```
statadiagnose/
├── package.json            # dsh.bundle 声明，不打包任何依赖
├── cordis.patch.yml        # 挂载本包的插件
├── index.js                # 用 dsh 自带的 skill-filesystem provider 挂载 skills/
├── locale/{en,zh}.json     # 插件管理器中显示的标题与描述
├── icon.svg
├── LICENSE, NOTICE
├── skills/stata-diagnose/
│   ├── SKILL.md            # agent 的工作流程
│   ├── scripts/run_stata.sh  # 找到本机 Stata，批处理运行 do-file，报告错误码、警告和 log 末尾
│   └── UPSTREAM-LICENSE.txt  # 上游 MIT 许可原文
└── test.mjs                # node --test test.mjs
```

`run_stata.sh` 的用法：

```bash
bash skills/stata-diagnose/scripts/run_stata.sh [--tail N] path/to/file.do [ARG ...]
```

在当前目录（项目根目录）以批处理模式运行，批处理 log `<file>.log` 放在 do-file 旁边，打印 log 路径、第一个 `r(###)` 错误码及其前文、
共线 / singleton / 不收敛 / 奇异方差矩阵 / 完全预测等警告，以及 log 末尾 N 行（默认 40）。有错误时退出码为 1。
`--which-stata` 显示将使用的 Stata，`--version` 显示 Stata 版本。

## 测试

```bash
node --test test.mjs
```

单元测试检查 manifest、patch、locale、SKILL frontmatter、`apply()` 的挂载方式和 `run_stata.sh` 的参数校验；本机有 Stata 时，
集成测试会检查运行成功、报错定位（`r(111)`）、共线警告和版本查询。

## 作者、许可与致谢

作者：Wenli Xu。采用 MIT 许可，见 [LICENSE](LICENSE) 和 [NOTICE](NOTICE)。

本插件基于上游 Pedro H. C. Sant'Anna 的 [claude-code-my-workflow](https://github.com/pedrohcgs/claude-code-my-workflow)
中的 `/diagnose`（提交 `fe70774`，MIT 许可）改进和扩展：

- 把排查流程改写为针对 Stata 的版本：列出 Stata 不报错、只悄悄算错的常见原因，配上插桩命令和一行防护断言；
- 做成 DeepSeek Harness 的 skill，去掉本机硬编码路径；
- 新增 `run_stata.sh`：自动查找本机 Stata，以 batch 模式运行 do-file，报告第一个错误码和共线、singleton、不收敛等警告，批处理 log 放在 do-file 旁边；
- 根据实测补充注意事项（如注释里的 `/*` 会悄悄吞掉后面的代码）；
- 新增测试和中文图文使用指南。

上游许可原文见 `skills/stata-diagnose/UPSTREAM-LICENSE.txt`。
