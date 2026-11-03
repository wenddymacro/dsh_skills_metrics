# whichdidshouldiuse · DSH 插件

把 [whichDIDshouldIuse](https://github.com/Credible-Answers/whichDIDshouldIuse)（Trelles、de Chaisemartin、Quispe 的 Stata 命令）做成
[DeepSeek Harness](https://github.com/deepseek-ai/deepseek-harness) 插件。安装后，每个会话的 skill 目录里会多出
`which-did-should-i-use`：当你问"我的面板该用哪种 DID / 哪个估计量"时，agent 会在本机用 Stata 运行 `whichdidshouldiuse`，
报告设计类型（CLA、SAD、HAD、SFSD 或 OTHER）、推荐估计量、对应的教科书章节，以及所有可能影响结论的样本调整。

它只**分类**，不**估计**。

## 依赖

- DeepSeek Harness ≥ 0.2.1-rc.1
- 本机 Stata 16 及以上版本（会自动查找；找不到时设置 `STATA_BIN`，例如
  `/Applications/StataNow/StataMP.app/Contents/MacOS/stata-mp`）
- 首次运行时，命令会从 SSC 安装 `distinct`；没有 stayers 的 HAD 面板还会用到 `did_had`、`nprobust`、`gtools`。
  如果本机的 `did_had` 太旧（不支持 `_no_updates`），HAD 的子情形会报告为 `undetermined`，在 Stata 里运行
  `ssc install did_had, replace` 升级即可。

## 安装

从本仓库安装（子目录安装，`<commit>` 换成要安装的提交）：

```bash
dsh plugin --profile <profile> add "git+https://github.com/wenddymacro/dsh_skills_metrics.git#<commit>&path:/whichdidshouldiuse"
```

从本地 checkout 安装（便于开发）：

```bash
dsh plugin --profile <profile> add "link:/abs/path/to/dsh_skills_metrics/whichdidshouldiuse"
```

Desktop app 的 profile 由 app 自己管理，请在 app 的**插件**页面里，从本地目录或 Git 地址安装。

## 使用

直接用自然语言提问即可，例如：

> 当前目录下的 panel.dta 里，y 是结果变量，id 是个体，year 是年份，d 是处理变量。这是哪种 DID 设计？该用什么估计量？

也可以输入 `/which-did-should-i-use` 显式调用这个 skill。skill 自带 4 个教科书示例面板（`skills/which-did-should-i-use/data/`），
可以用来演示或检查环境是否就绪。

## 结构

```
whichdidshouldiuse/
├── package.json            # dsh.bundle 声明，不打包任何依赖
├── cordis.patch.yml        # 挂载本包的插件
├── index.js                # 用 dsh 自带的 skill-filesystem provider 挂载 skills/
├── locale/{en,zh}.json     # 插件管理器中显示的标题与描述
├── icon.svg
├── skills/which-did-should-i-use/
│   ├── SKILL.md            # agent 的工作流程与结果解读
│   ├── scripts/run_whichdid.sh   # 以 batch 模式运行 Stata，只输出报告和 return list
│   ├── stata/              # 上游 .ado / .sthlp / LICENSE（MIT）
│   └── data/               # 4 个教科书示例面板
└── test.mjs                # node --test test.mjs
```

## 测试

```bash
node --test test.mjs
```

单元测试检查 manifest、patch、locale、SKILL frontmatter 和 `apply()` 的挂载方式；本机有 Stata 时，集成测试会用 4 个示例面板
复现上游 README 中的分类结果（CLA、SAD、SFSD、HAD）。

## 许可与致谢

插件代码采用 MIT 许可。`skills/which-did-should-i-use/stata/` 与 `data/` 来自上游
[Credible-Answers/whichDIDshouldIuse](https://github.com/Credible-Answers/whichDIDshouldIuse)（提交 `d032764`，MIT 许可，版权归原作者所有）。
设计定义与估计量建议来自 de Chaisemartin & D'Haultfœuille (2026), *Causal Inference with Differences-in-Differences:
Credible Answers to Hard Questions*, Princeton University Press。
