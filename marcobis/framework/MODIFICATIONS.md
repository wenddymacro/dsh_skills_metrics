# 对上游 MaRCo@BIS 的修改说明

本目录来自 MaRCo@BIS 开源仓库（Copyright © 2026 Bank for International Settlements，
Apache License 2.0，见 [`LICENSE`](LICENSE) 和 [`NOTICE`](NOTICE)），上游版本：

- 仓库：https://github.com/wenddymacro/marco-BIS
- 提交：`8a51b9a4ff8953b0c7deb73de15883734c5bddfd`（2026-11-12）

按 Apache License 2.0 第 4(b) 条，这里列出修改过的文件。这些修改由 Wenli Xu 做出，
是对上游的改进和扩展。BIS 的名称和标志未经 BIS 书面许可不得使用（见 NOTICE）。

## 新增文件

| 文件 | 内容 |
|---|---|
| `scripts/lib/data/nbs_client.py` | 国家统计局"国家数据"平台客户端：目录树、指标、取数、分段表拼接 |
| `scripts/lib/data/fetchers/nbs.py` | `lib.fetch_data(api="nbs", ...)` fetcher |
| `scripts/lib/preprocess/china.py` | 中国官方数据清洗：累计值转当期值、1–2 月合并处理、定基指数链接、比例衔接 |
| `scripts/tools/nbs_update.py` | 下载并清洗国家统计局月度 / 季度 / 年度面板 |
| `scripts/tools/nbs_tool.py` | 国家统计局目录浏览、搜索、指标查询、单序列取数 |
| `data/nbs_m/`、`data/nbs_q/`、`data/nbs_a/` | 面板定义 `panel.yaml`（月度约 35、季度 13、年度 39 个序列，另有派生序列）和说明 `UPDATE.md` |
| `tests/test_nbs.py` | 上述模块的测试（联网测试需 `--runslow`） |
| `scripts/lib/data/gmd_client.py` | Global Macro Database 客户端：版本、变量表、下载缓存、按国家 / 变量 / 年份切取；`lib.load_gmd` |
| `scripts/lib/data/fetchers/gmd.py` | `lib.fetch_data(api="gmd", ...)` fetcher |
| `scripts/tools/gmd_tool.py` | GMD 版本、下载、变量 / 国家查询、覆盖、切取、来源拼接 |
| `data/gmd/UPDATE.md` | GMD 说明（数据由 `gmd_tool.py update` 下载，学术许可，不分发） |
| `tests/test_gmd.py` | GMD 模块的测试（联网测试需 `--runslow`） |
| `MODIFICATIONS.md` | 本文件 |

## 修改的文件

| 文件 | 修改 |
|---|---|
| `scripts/lib/data/fetchers/__init__.py` | 登记 `nbs`、`gmd` fetcher |
| `scripts/lib/preprocess/__init__.py` | 导出 `china` 子模块 |
| `data/registry.yaml` | 登记 `nbs_m`、`nbs_q`、`nbs_a` 三个数据集和 `gmd`（国家面板，`loader: load_gmd`） |
| `.gitignore` | 忽略国家统计局面板的生成文件和目录缓存，以及 GMD 下载的文件 |
| `scripts/lib/data/loader.py` | 注册表条目带 `loader` 时（如 `gmd`），`load_dataset` 提示改用对应的读取函数 |
| `scripts/lib/__init__.py`、`scripts/lib/data/__init__.py` | 导出 `load_gmd` |
| `CLAUDE.md`、`README.md`、`CONVENTIONS.md`、`DEVELOPMENT.md`、`TEST_SUITE.md`（另加 T4.6、T6.5 两个中国数据行为测试），以及 `skills/` 下全部 Markdown（12 个 `SKILL.md` 和 `orchestrator/modes.md`） | 翻译成简体中文；在适当位置补充国家统计局数据的说明；把"Claude Code"相关表述改为适用于任意 agent 环境 |
| `scripts/lib/README.md`、`scripts/lib/preprocess/README.md`、`scripts/applications/README.md`、`scripts/replications/README.md`、`tests/README.md`、`scripts/tools/README.md`、`papers/README.md`、`data/fred_md/UPDATE.md`、`data/fred_qd/UPDATE.md` | 翻译成简体中文（lib / preprocess / tools 的 README 补充了新增模块） |
| `scripts/lib/data/nbs_client.py` 等新增文件的 docstring | 中文撰写 |

尚未翻译、保持英文原文的部分：

- `SECURITY.md`、`CITATION.cff`；
- 各复现目录 `scripts/replications/<id>/` 下的 README、配置和脚本；
- 结构化数据和代码：模型字典条目（`skills/model-dictionary/entries/*.yaml`、`index.yaml`，测试依赖其字段
  和受控词表）、上游 Python 代码及其 docstring、`tests/` 下的上游测试。

上游的文档一致性测试（`tests/test_doc_consistency.py`）中检查"模块数 / 条目数"的正则表达式只匹配
英文表述。翻译后的中文文档不再受这两项检查约束，修改文档中的数字时请人工核对。
