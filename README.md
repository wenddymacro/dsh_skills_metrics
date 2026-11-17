# dsh_skills_metrics

为 [DeepSeek Harness](https://github.com/deepseek-ai/deepseek-harness)（`dsh`）开发的计量经济学插件集合。
每类插件放在一个独立文件夹中，各自是一个可单独安装的 dsh 组合包（bundle）。

| 插件 | 作用 |
|---|---|
| [`whichdidshouldiuse/`](whichdidshouldiuse/) | 判断面板数据的 DID 设计类型（CLA、SAD、HAD、SFSD），并推荐估计量；基于 Stata 命令 `whichdidshouldiuse`。[图文使用指南](whichdidshouldiuse/docs/GUIDE.md) |
| [`marcobis/`](marcobis/) | BIS 的 MaRCo@BIS 宏观计量研究助手（中文化）：七阶段人机协同工作流，VAR / BVAR / LP / SVAR 等方法的参考实现和 30 篇经典论文复现；新增国家统计局月度、季度、年度数据的下载与清洗。[图文使用指南](marcobis/docs/GUIDE.md) |
| [`journalfinder/`](journalfinder/) | 根据论文题目、摘要或整篇稿件（PDF / Word），从 5,183 本 JCR SSCI/AHCI 期刊中推荐投稿期刊，标注分区、影响因子、FT50、UTD24、ABS；基于 mskills 的 JournalFinder。[图文使用指南](journalfinder/docs/GUIDE.md) |

## 安装某个插件

```bash
dsh plugin --profile <profile> add "github:wenddymacro/dsh_skills_metrics#<插件文件夹>-v<版本>&path:/<插件文件夹>"
```

例如 `github:wenddymacro/dsh_skills_metrics#marcobis-v0.2.0&path:/marcobis`。桌面版在「插件 → 添加插件」里填同一个地址。
各插件的依赖、用法和当前版本见其文件夹下的 README。

## 更新提醒

从 0.2.0 起，每个插件在 DeepSeek Harness 启动时，会在后台查看本仓库的发布标签，每 12 小时最多查一次，
结果写到 `~/.dsh/cache/dsh-skills-metrics/<插件文件夹>.json`。有新版本时，agent 在用户下次使用该插件时提醒一句，
用户同意后再通过 dsh 的 `plugin_manager` 工具安装新版本。dsh 会请用户批准这次安装，所以不会在用户不知情时更新。
设置 `DSH_SKILLS_METRICS_UPDATE_CHECK=0` 可关闭联网检查。

检查代码是各插件文件夹里的 `update-check.js`，三份内容必须一致（测试会比对）；改动时三份一起改。

## 发布新版本（维护者）

用户只会被提醒**打了标签**的版本；只推送到 `main` 的提交不会触发提醒。发布插件 `<插件文件夹>` 的新版本：

1. 改 `<插件文件夹>/package.json` 的 `version`（例如 `0.2.0` → `0.2.1`），同时改 README 和 `docs/GUIDE.md` 里安装地址中的版本号。
2. 在插件文件夹里运行 `node --test test.mjs`，确认通过。
3. 合并到 `main` 后，在合并后的提交上打标签并推送，标签名必须是 `<插件文件夹>-v<version>`，和 `package.json` 一致：

```bash
git tag marcobis-v0.2.1 origin/main
```

```bash
git push origin marcobis-v0.2.1
```

标签推送后，已安装 0.2.0 及以上版本的用户在 12 小时内会看到提醒。
