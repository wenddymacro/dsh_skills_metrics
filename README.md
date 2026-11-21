# dsh_skills_metrics

为 [DeepSeek Harness](https://github.com/deepseek-ai/deepseek-harness)（`dsh`）开发的计量经济学插件集合。
每类插件放在一个独立文件夹中，各自是一个可单独安装的 dsh 组合包（bundle）。

作者：Wenli Xu。各插件基于上游开源项目改进和扩展，上游来源、许可和具体改动见各插件 README 的「作者、许可与致谢」。

| 插件 | 作用 |
|---|---|
| [`whichdidshouldiuse/`](whichdidshouldiuse/) | 判断面板数据的 DID 设计类型（CLA、SAD、HAD、SFSD），并推荐估计量；基于 Stata 命令 `whichdidshouldiuse`。[图文使用指南](whichdidshouldiuse/docs/GUIDE.md) |
| [`marcobis/`](marcobis/) | BIS 的 MaRCo@BIS 宏观计量研究助手（中文化）：七阶段人机协同工作流，VAR / BVAR / LP / SVAR 等方法的参考实现和 30 篇经典论文复现；新增国家统计局月度、季度、年度数据的下载与清洗。[图文使用指南](marcobis/docs/GUIDE.md) |
| [`journalfinder/`](journalfinder/) | 根据论文题目、摘要或整篇稿件（PDF / Word），从 5,183 本 JCR SSCI/AHCI 期刊中推荐投稿期刊，标注分区、影响因子、FT50、UTD24、ABS；基于 mskills 的 JournalFinder。[图文使用指南](journalfinder/docs/GUIDE.md) |
| [`sfcmodeler/`](sfcmodeler/) | 搭建、求解和冲击后凯恩斯主义存量流量一致（SFC）模型，逐期核对交易流量矩阵和资产负债表；附 Godley & Lavoie 的 SIM、PC、LP 示例；基于 Python 包 SFCmodeler。[图文使用指南](sfcmodeler/docs/GUIDE.md) |
| [`statadataanalysis/`](statadataanalysis/) | 用 Stata 跑完整实证流程：先读数据给出 Pre-Flight 报告，再写编号 do-file、批处理运行并检查 log，输出可发表的回归表（.tex/.rtf）和图，记录设定台账；改编自 claude-code-my-workflow 的 `/data-analysis`。[图文使用指南](statadataanalysis/docs/GUIDE.md) |
| [`statadiagnose/`](statadiagnose/) | 用"症状 → 复现 → 最小化 → 假设 → 插桩 → 修复"的流程找出 Stata 结果出错、报错或复现不了的根本原因，专查类型、缺失值比较、merge m:m、权重、共线、不收敛等静默错误；改编自 claude-code-my-workflow 的 `/diagnose`。[图文使用指南](statadiagnose/docs/GUIDE.md) |
| [`statsclaw/`](statsclaw/) | 统计软件包开发团队：组长 preset 调度规划、编码、测试、仿真、文档、审查六个角色 preset，spec.md / test-spec.md / sim-spec.md 互相隔离，代码、测试和蒙特卡洛仿真独立验证后由审查者给出能否交付的结论；支持 R、Python、Stata、Julia 等，不需要 GitHub；基于 StatsClaw。 |
| [`statsclaw-stata/`](statsclaw-stata/) | StatsClaw 的 Stata 专用版：同样的组长 + 六角色团队，手册按 Stata 命令包开发写深——规格写到 `syntax` 行、e()/r() 返回值和错误码，测试用 `cscript` 认证脚本对照 regress、ivregress、reghdfe 等基准命令，附 27 条静默错误清单、`stata_pkg_check.py` 打包检查和 sthlp / pkg 模板；可与通用版同时安装。 |

## 安装某个插件

```bash
dsh plugin --profile <profile> add "git+https://github.com/wenddymacro/dsh_skills_metrics.git#<commit>&path:/<插件文件夹>"
```

`<commit>` 换成要安装的提交号，目前最新的是 `bdbc85f0abaef6c4bd9e871c5dec2c9c65c3baf7`。各插件的依赖与用法见其文件夹下的 README。
