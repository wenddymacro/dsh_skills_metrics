# dsh_skills_metrics

为 [DeepSeek Harness](https://github.com/deepseek-ai/deepseek-harness)（`dsh`）开发的计量经济学插件集合。
每类插件放在一个独立文件夹中，各自是一个可单独安装的 dsh 组合包（bundle）。

| 插件 | 作用 |
|---|---|
| [`whichdidshouldiuse/`](whichdidshouldiuse/) | 判断面板数据的 DID 设计类型（CLA、SAD、HAD、SFSD），并推荐估计量；基于 Stata 命令 `whichdidshouldiuse`。[图文使用指南](whichdidshouldiuse/docs/GUIDE.md) |
| [`journalfinder/`](journalfinder/) | 根据论文题目、摘要或整篇稿件（PDF / Word），从 5,183 本 JCR SSCI/AHCI 期刊中推荐投稿期刊，标注分区、影响因子、FT50、UTD24、ABS；基于 mskills 的 JournalFinder。[图文使用指南](journalfinder/docs/GUIDE.md) |

## 安装某个插件

```bash
dsh plugin --profile <profile> add "git+https://github.com/wenddymacro/dsh_skills_metrics.git#<commit>&path:/<插件文件夹>"
```

各插件的依赖与用法见其文件夹下的 README。
