---
name: find-journal
description: >-
  Recommend journals to submit a research paper to, from its title, abstract, keywords or a
  full manuscript (PDF / Word / TXT), by querying a bundled local database of 5,183 JCR
  SSCI/AHCI journals (plus environmental-health crossover journals). Reports JCR and CAS
  quartiles, impact factor, FT50, UTD24, ABS (AJG 2024) rating, OA/APC, share of Chinese
  authors, annual volume and review time, ranks by topic fit, prestige, speed, budget or
  CN-friendliness, and checks word limits. Use when the user asks where to submit a paper,
  for journal recommendations, "find a journal", "帮我找期刊", "期刊推荐", "投稿建议",
  "投哪个期刊", FT50 / UTD24 / ABS 3 星以上 journals, in economics, management, sociology,
  political science, psychology, education, law, communication, geography, demography or
  other social sciences and humanities.
---

# Journal Finder — 投稿期刊推荐

This skill answers one question: **which journals fit this paper?** Candidates come from the
local database bundled with this skill; nothing is fetched from the network.

The output is a ranked shortlist, not an acceptance prediction. **Topic fit is a hard gate**:
a fast, prestigious or cheap journal is not recommended when the topic does not fit.

Everything lives in this skill's resource directory (the base directory reported with this skill;
written `<skill-dir>` below):

| Path | Content |
|---|---|
| `scripts/query_db.py` | Recall, filter and rank journals; prints JSON |
| `scripts/parse_manuscript.py` | Extract title, abstract, keywords, word count, methods, article type from a PDF / Word / TXT manuscript; prints JSON |
| `scripts/runtime_paths.py` | Locates `data/` (used by both scripts) |
| `data/journals_ssci.json` | Canonical database: 4,802 SSCI/AHCI + 381 environmental-health crossover journals |
| `data/business_rankings.json` | FT50 2026, UTD24 and AJG 2024 annotations keyed by ISSN-L |
| `references/data-schema.md` | Full field schema |
| `references/ACKNOWLEDGMENTS.md`, `LICENSE.txt`, `journal-lists-SOURCE.md` | Provenance and licences |

Requirements: Python 3.10+ (`python3`; on Windows `python`). Only the standard library is needed,
except for PDF manuscripts, which need `pypdf` (`python3 -m pip install pypdf`). If the import fails,
tell the user that command, or ask for a `.docx` or the pasted title and abstract instead.

## Boundaries

- **Recommend only; do not rewrite.** Do not edit the user's title or abstract here.
- **Never guess missing data.** Missing quartile, APC, review time or word limit is shown as `—`
  and described as missing.
- **SSCI/AHCI coverage only.** Pure natural science, clinical medicine, environmental engineering,
  chemistry or ecology are not in the database. Say so and ask for the closest social-science,
  humanities or environmental-health angle.
- **Keyword recall only.** The plugin does not ship the SPECTER2/FAISS semantic index (the model
  is ~440 MB), so `query.semantic_search = false` and `query.semantic_status = "fallback"` are
  expected; ignore the "Run build_embeddings.py" hint in `semantic_error`. For cross-disciplinary
  papers pass scope keywords from each field, and state in the report that this run used keyword
  matching only.

## Workflow

### 1. Get the paper

- **Manuscript file** (`.pdf`, `.docx`, `.txt`, `.md`): parse it first, with an absolute path.

  ```sh
  python3 <skill-dir>/scripts/parse_manuscript.py "/abs/path/paper.pdf"
  ```

  It returns `title`, `abstract`, `author_keywords`, `jel_codes`, `section_headings`,
  `word_count_body` (main text without title block, abstract, references, appendices),
  `reference_count`, `figure_count`, `table_count`, detected `methods` / `data_sources` /
  `geography`, `article_type` (`empirical` / `theoretical` / `review` / `comment` / `unknown`),
  `suggested_keywords` and `warnings`.
  - Use `title` + `abstract` + `author_keywords` as the paper description, and refine
    `suggested_keywords` into 3–6 **journal-scope concepts**. Methods, data and geography are
    context, not scope.
  - Before the table, briefly echo what was detected (title, body word count, methods, data,
    article type) so the user can correct misreads.
  - If it returns `error` (scanned PDF without a text layer, legacy `.doc`) or `warnings` contains
    `title_not_detected` / `abstract_not_detected`, ask the user to paste the title and abstract.
- **Title / abstract / description**: extract 3–6 scope keywords yourself. Do not let a country,
  sample population or method replace the core field and problem keywords.
- **Nothing usable**: ask for at least a paragraph describing the paper before going on.

### 2. Ask for preferences once

Skip this when the user already stated priorities. Otherwise ask one question (offer choices if your
interface supports a picker):

> 你更看重哪些方面？可多选：主题贴合、求档次、求快、预算有限、国人友好、容量稳；也可以说"均衡推荐"。
> 有没有硬性要求，比如只要 FT50 / UTD24、ABS 3 星以上、APC 上限、只要 OA、只要 Q1–Q2？

Map choices to flags: 主题贴合→`fit`, 求档次→`prestige`, 求快→`speed`, 预算有限→`budget`,
国人友好→`cn`, 容量稳→`volume`, passed as `--priorities a,b`. With a single dominant goal also set
the matching `--sort`; with several use `--sort balanced`. If the user asks for separate rankings
("求档次和求快各一份"), run one query per goal.

### 3. Query

```sh
python3 <skill-dir>/scripts/query_db.py --keywords "minimum wage,youth employment,labor market" --top 15 [flags]
```

- With a manuscript, add `--manuscript "/abs/path/paper.pdf"` so word limits are checked; without
  `--keywords` it uses the manuscript's `suggested_keywords`, and a `review` article automatically
  enables `--include-review-only`.
- Keep `--top` at 15 or below; 15 results are about 31,000 characters of JSON.

| User says | Flags |
|---|---|
| 主题贴合优先 / balanced | `--sort balanced --priorities fit` |
| 求档次 | `--sort prestige --priorities prestige` |
| 求快 | `--sort speed --priorities speed` (only journals with review data: add `--require-review-data`) |
| 档次 + 速度兼顾 | `--sort balanced --priorities prestige,speed` |
| 预算有限 / APC ≤ N USD | `--priorities budget --max-apc N` |
| 国人友好 | `--sort cn_friendly --priorities cn` |
| 容量稳 | `--priorities volume` |
| 只要 FT50 | `--ft50-only` |
| 只要 UTD24 | `--utd24-only` |
| ABS 3 星以上 / ABS 4* | `--min-abs 3` / `--min-abs 4*` |
| 只要 Q1–Q2 | `--min-quartile Q2` |
| 只要 OA | `--oa-only` |
| 审稿不超过 N 天 | `--max-review-days N` |
| 稿件是综述 | `--include-review-only` |
| 正文字数为 N | `--word-count N` |

FT50 / UTD24 / ABS filters are hard filters: use them only when the user asks. Otherwise the lists
only add to the prestige score. A few listed journals (*Production and Operations Management*,
*INFORMS Journal on Computing*) are not in the database and cannot be recommended.

### 4. Check the result before concluding

- `quality.status` of `limited_matches` or `no_good_match`: **never pad the table with unrelated
  journals.** Suggest relaxing filters or revising keywords, and rerun.
- `_review_confidence` of `limited` / `very_limited` / `missing`: review time is a weak signal;
  mention the small sample.
- `_word_limit_check.status`: `exceeds` means the manuscript is over the journal's limit (also the
  `exceeds_word_limit` risk flag); `limit_unknown` is the common case, so tell the user to confirm on
  the journal site rather than implying it fits.
- `abs_rating = null` means the journal is not in AJG 2024, not that it is low-tier.

Per-result fields: `name`, `abbreviation`, `publisher`, `jcr_quartile`, `cas_zone`, `impact_factor`,
`is_oa`, `oa_type`, `apc_usd`, `cn_author_ratio`, `annual_volume_2024`, `review_median_days`,
`ft50`, `utd24`, `abs_rating`, `abs_field`, plus `_final_score`, `_fit_scores` (topic / prestige /
speed / cost / cn / volume / data), `_recommendation_notes`, `_risk_flags`, `_review_confidence`,
`_review_evidence`, `_word_limit_check`. Query-level: `query.semantic_status`,
`query.business_rankings` (list versions), `query.manuscript`, `quality.status`. Full schema:
`references/data-schema.md`.

### 5. Report

Pick 5–8 journals: 1–2 reach, 3–4 solid fits, 1–2 safer options.

```
## 稿件识别（仅在有稿件文件时）
标题：…；正文约 <n> 词；方法：…；数据：…；文章类型：…

## 推荐期刊
（本次为关键词匹配，未使用语义检索）

| 期刊名称 | JCR分区 | 中科院分区 | 影响因子 | FT50 | UTD24 | ABS | OA/APC | 国人占比 | 年发文量 | 审稿周期(天) | 避坑提示 |
|----------|---------|-----------|---------|------|-------|-----|--------|---------|---------|-------------|---------|
| Journal Name (Abbr) | Q1 | 1区 | 9.8 | ✓ | — | 4* | 订阅制 | 8% | 65 | 120 | — |

## 前三本分析
每本：为什么贴合；风险（审稿慢、字数超限、主题偏差等）；冲刺 / 稳妥 / 保底定位。
```

- Missing values are always `—`. FT50 / UTD24 columns show `✓` or `—`; the ABS column shows the
  rating. When none of the recommended journals is on any list (common outside business,
  economics and management), drop those three columns.
- Answer in the user's language; the table may keep Chinese headers.

## Source

Adapted from [alexishuang1901-hub/journal-finder](https://github.com/alexishuang1901-hub/journal-finder)
(MIT) via the mskills JournalFinder fork; list snapshots from
[wosaide/wosaide-journal-lists](https://github.com/wosaide/wosaide-journal-lists). See
`references/ACKNOWLEDGMENTS.md`.
