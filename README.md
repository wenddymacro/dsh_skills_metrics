# dsh_skills_metrics

为 [DeepSeek Harness](https://github.com/deepseek-ai/deepseek-harness)（`dsh`）开发的计量经济学插件集合。
每类插件放在一个独立文件夹中，各自是一个可单独安装的 dsh 组合包（bundle）。

| 插件 | 作用 |
|---|---|
| [`whichdidshouldiuse/`](whichdidshouldiuse/) | 判断面板数据的 DID 设计类型（CLA、SAD、HAD、SFSD），并推荐估计量；基于 Stata 命令 `whichdidshouldiuse`。[图文使用指南](whichdidshouldiuse/docs/GUIDE.md) |
| [`marcobis/`](marcobis/) | BIS 的 MaRCo@BIS 宏观计量研究助手（中文化）：七阶段人机协同工作流，VAR / BVAR / LP / SVAR 等方法的参考实现和 30 篇经典论文复现；新增国家统计局月度、季度、年度数据的下载与清洗。[图文使用指南](marcobis/docs/GUIDE.md) |
| [`journalfinder/`](journalfinder/) | 根据论文题目、摘要或整篇稿件（PDF / Word），从 5,183 本 JCR SSCI/AHCI 期刊中推荐投稿期刊，标注分区、影响因子、FT50、UTD24、ABS；基于 mskills 的 JournalFinder。[图文使用指南](journalfinder/docs/GUIDE.md) |
| [`sfcmodeler/`](sfcmodeler/) | 搭建、求解和冲击后凯恩斯主义存量流量一致（SFC）模型，逐期核对交易流量矩阵和资产负债表；附 Godley & Lavoie 的 SIM、PC、LP 示例；基于 Python 包 SFCmodeler。[图文使用指南](sfcmodeler/docs/GUIDE.md) |
| [`statadataanalysis/`](statadataanalysis/) | 用 Stata 跑完整实证流程：先读数据给出 Pre-Flight 报告，再写编号 do-file、批处理运行并检查 log，输出可发表的回归表（.tex/.rtf）和图，记录设定台账；改编自 claude-code-my-workflow 的 `/data-analysis`。[图文使用指南](statadataanalysis/docs/GUIDE.md) |
| [`statadiagnose/`](statadiagnose/) | 用"症状 → 复现 → 最小化 → 假设 → 插桩 → 修复"的流程找出 Stata 结果出错、报错或复现不了的根本原因，专查类型、缺失值比较、merge m:m、权重、共线、不收敛等静默错误；改编自 claude-code-my-workflow 的 `/diagnose`。[图文使用指南](statadiagnose/docs/GUIDE.md) |

## 安装某个插件

推荐从 npm 安装（dsh「插件 → 添加插件」填包名，或命令行）：

```bash
dsh plugin --profile <profile> add @dsh-skills-metrics/<插件文件夹>
```

这样装的插件，dsh 的「插件」页能直接检查和更新版本。npm 不通时，可以从 GitHub 的发布标签安装：

```bash
dsh plugin --profile <profile> add "github:wenddymacro/dsh_skills_metrics#<插件文件夹>-v<版本>&path:/<插件文件夹>"
```

例如 `github:wenddymacro/dsh_skills_metrics#marcobis-v0.2.0&path:/marcobis`。
各插件的依赖、用法和当前版本见其文件夹下的 README。

## 更新提醒

从 0.2.0 起，每个插件在 DeepSeek Harness 启动时，会在后台查看本仓库的发布标签，每 12 小时最多查一次，
结果写到 `~/.dsh/cache/dsh-skills-metrics/<插件文件夹>.json`。插件还会读 profile 的 `package.json`，判断自己是从哪里装的。
有新版本时，agent 在用户下次使用该插件时提醒一句：

- 从 npm 装的：请用户在「插件」页点更新（dsh 的 `plugin_manager install_bundle` 不接受已经从 npm 装过的包）。
- 从 GitHub 装的：用户同意后，agent 用 `plugin_manager install_bundle` 安装新标签的地址，dsh 会请用户批准。
- 从本地目录 `link:` 装的：不提醒。

设置 `DSH_SKILLS_METRICS_UPDATE_CHECK=0` 可关闭联网检查。检查代码是各插件文件夹里的 `update-check.js`，
三份内容必须一致（测试会比对）；改动时三份一起改。

## 发布新版本（维护者）

推送标签 `<插件文件夹>-v<version>` 就是发布：GitHub Actions（[`.github/workflows/publish.yml`](.github/workflows/publish.yml)）
会检查标签和 `package.json` 的版本一致、跑测试，然后把这个插件发布到 npm；装了 0.2.0 及以上版本的用户在 12 小时内会看到提醒。
只推送到 `main` 的提交不会发布，也不会触发提醒。

1. 改 `<插件文件夹>/package.json` 的 `version`（例如 `0.2.0` → `0.2.1`），同时改 README 和 `docs/GUIDE.md` 里 GitHub 安装地址中的版本号。
2. 在插件文件夹里运行 `node --test test.mjs`，确认通过。
3. 合并到 `main` 后，在合并后的提交上打标签并推送：

```bash
git fetch origin && git tag marcobis-v0.2.1 origin/main
```

```bash
git push origin marcobis-v0.2.1
```

4. 在仓库的 Actions 页确认「Publish plugin to npm」成功。

### 第一次发布前的一次性设置

1. 在 [npmjs.com](https://www.npmjs.com/) 注册账号，开启两步验证，然后创建名为 `dsh-skills-metrics` 的组织（公开包免费），
   这样才能发布 `@dsh-skills-metrics/...` 这几个包名。
2. 在 npm 账号的 Access Tokens 里生成一个能发布这个组织下包的 token（Granular 或 Automation 类型）。
3. 在 GitHub 仓库的 Settings → Secrets and variables → Actions 里新建 secret，名称 `NPM_TOKEN`，值为上一步的 token。
