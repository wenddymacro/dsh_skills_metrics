# 来源与致谢 / Source & Acknowledgments

## 原始项目

本目录基于开源项目 **Journal Finder** 修改而来，原作者保留其著作权。

| 项目 | 信息 |
|------|------|
| 名称 | Journal Finder — 学术期刊推荐工具 |
| 来源仓库 | <https://github.com/alexishuang1901-hub/journal-finder> |
| 同源仓库 | <https://github.com/yennhi85219-glitch/journal-finder>（上游 README 中的克隆地址，HEAD 与上面的仓库相同） |
| 基于版本 | 提交 `b8fb764bc4b60acb88538e579b165bf4745b3072`（"Add Doubao prompt batch exporter"，2026-07-28） |
| 原作者 | alexis Huang 及 journal-finder contributors |
| 许可证 | MIT License，见 [`LICENSE`](LICENSE)（原文保留，未作改动） |

原项目完成了这个工具的核心工作，包括：
- 当前 JCR SSCI/AHCI 白名单期刊库（5,183 本），数据来自 OpenAlex、Crossref、JCR 和中科院分区
- 关键词与 SPECTER2/FAISS 混合召回
- 多目标偏好排序
- Claude Code 与 Codex 两个版本的 Skill
- 完整的数据管道和测试

在此向原作者表示感谢。

## 本目录的修改

在原项目基础上新增了以下功能，新增代码以 MIT 许可证发布。前两项的逐提交补丁保存在 [`patches/`](patches/)，可以直接向上游提交：

| 补丁 | 内容 |
|------|------|
| `0001-Add-FT50-and-ABS-AJG-journal-annotations.patch` | FT50 / ABS (AJG) 标注、`--ft50-only` / `--min-abs` 筛选、档次分加权、AJG 官方文件导入脚本 |
| `0002-Add-full-manuscript-PDF-Word-parsing-and-word-limit-.patch` | 整篇论文（PDF / Word / TXT）解析、`--manuscript` / `--word-count`、字数限制检查 |

此后又做了两项改动（未生成补丁）：新增 Metrics AI 适配版（`metrics-ai/SKILL.md` 和 `scripts/build_metrics_skill.py`）；改用 wosaide-journal-lists 的名单快照（AJG 2024 全表、FT50 2026、UTD24），替换掉手工录入的种子数据，并新增 `utd24` 字段和 `--utd24-only` 筛选。

新增和修改的文件：
- 新增：`scripts/build_business_rankings.py`、`scripts/build_metrics_skill.py`、`metrics-ai/SKILL.md`、`tests/test_build_metrics_skill.py`、`skill/scripts/parse_manuscript.py`、`data/journal_lists/`（第三方名单快照）、`data/business_rankings.json`、`tests/test_business_rankings.py`、`tests/test_parse_manuscript.py`
- 修改：`skill/scripts/query_db.py`、`skill/SKILL.md`、`codex-skills/find-journal/SKILL.md`、`skill/references/data-schema.md`、`README.md`、`CLAUDE.md`、`requirements.txt`

其余文件与上游 `b8fb764` 保持一致。

## 其他致谢

- **[qwerty239qwe/submission-nav](https://github.com/qwerty239qwe/submission-nav)**：整篇论文解析（PDF/Word → 字数、方法、文章类型）的功能思路受到这个项目启发。该仓库未声明开源许可证，所以**没有复制或改编它的任何代码**，`parse_manuscript.py` 是独立实现的。
- **[wosaide/wosaide-journal-lists](https://github.com/wosaide/wosaide-journal-lists)**：`data/journal_lists/` 中的 AJG2024、FT50、UTD24 三份 CSV 原样取自该仓库的 `LIST/` 目录（提交 `2c7584e`）。感谢维护者整理这些名单。该仓库未声明许可证，来源与官方出处见 [`data/journal_lists/SOURCE.md`](data/journal_lists/SOURCE.md)。
- **Financial Times**：FT50 期刊名单（2026 版）。
- **UT Dallas Naveen Jindal School of Management**：UTD24 期刊名单。
- **Chartered Association of Business Schools**：《Academic Journal Guide 2024》(AJG)，官方页面 <https://charteredabs.org/academic-journal-guide/>。
- **数据来源**（沿用原项目）：[OpenAlex](https://openalex.org/)、[Crossref](https://www.crossref.org/)、Clarivate JCR、中国科学院文献情报中心期刊分区表、SPECTER2 (Allen Institute for AI)。
