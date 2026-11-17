# 工具

对框架自身文件进行操作的小工具（不是估计代码，估计代码在 [`scripts/lib/`](../lib/)）。

| 工具 | 用途 |
|---|---|
| [`nbs_update.py`](nbs_update.py) | 按 `data/nbs_*/panel.yaml` 下载并清洗国家统计局月度 / 季度 / 年度面板，写出 `dataset.csv` 等文件。见 [`data/nbs_m/UPDATE.md`](../../data/nbs_m/UPDATE.md) |
| [`gmd_tool.py`](gmd_tool.py) | Global Macro Database：查看版本（`versions`）、下载到 `data/gmd/`（`update`）、查变量 / 国家（`vars` / `countries`）、样本覆盖（`coverage`）、切取数据（`extract`）、来源拼接（`raw`）。见 [`data/gmd/UPDATE.md`](../../data/gmd/UPDATE.md) |
| [`nbs_tool.py`](nbs_tool.py) | 国家统计局"国家数据"查询：浏览目录（`browse`）、搜索（`search`）、查看指标键（`indicators`）、取单个序列（`fetch`） |
| [`make_author_dossiers.py`](make_author_dossiers.py) | 把每个模型字典条目渲染成面向作者的档案（我们归于论文的内容及页码、我们复现的、我们改动的、属于我们自己的编辑内容）。站得住的检验标准：一个条目的档案可以原样发给论文原作者时，这个条目就是合格的。见 [`model-dictionary/SKILL.md`](../../skills/model-dictionary/SKILL.md) 中的字段来源一节。 |

`make_author_dossiers.py` 的产出放在同目录的 `outputs/` 子目录（gitignore，可再生），遵循整个框架的
约定。`nbs_update.py` 写入 `data/nbs_*/`，`gmd_tool.py update` 写入 `data/gmd/`。
