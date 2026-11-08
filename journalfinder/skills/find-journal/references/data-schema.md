# Journal Database Schema

## 数据文件位置

数据库目录由 `--data-dir`、`JOURNAL_FINDER_DATA_DIR`、安装配置或仓库相对路径解析。

- `journals_ssci.json` — canonical 主数据库
- `journals_economics.json` — 经济学兼容子集
- `journals_demography.json` — 人口学兼容子集
- `manual_supplement.json` — 手动维护数据（JCR/中科院分区等）
- `journal_lists/` — AJG2024 / FT50 / UTD24 名单快照（来自 wosaide/wosaide-journal-lists，见 `SOURCE.md`）
- `business_rankings.json` — 由 `scripts/build_business_rankings.py` 生成的 FT50/UTD24/ABS 标注层（ISSN-L 为键），`query_db.py` 加载时附加到每条记录
- `journal_index_meta.json` — FAISS/index-map generation 校验和

## 单条记录 Schema

```json
{
  "issn_l": "string — ISSN-L 主标识",
  "name": "string — 期刊全称",
  "abbreviation": "string|null — 缩写",
  "publisher": "string — 出版商",
  "country_code": "string — 出版国 (ISO 2-letter)",
  "openalex_id": "string — OpenAlex source ID",
  "homepage_url": "string|null — 期刊主页",

  "topics": [
    {
      "name": "string — topic 名称",
      "score": "number — 该 topic 下的文章数",
      "subfield": "string — 所属子领域"
    }
  ],
  "scope_keywords": ["string — 范围关键词（小写）"],

  "jcr_quartile": "string|null — 仅 Q1/Q2/Q3/Q4；N/A 规范为 null",
  "cas_zone": "number|null — 中科院分区 1-4 (手动维护)",
  "impact_factor": "number|null — 最新影响因子 (手动维护)",
  "citedness_2yr": "number — OpenAlex 2年平均被引 (IF近似值)",
  "h_index": "number — H指数",

  "is_oa": "boolean — 是否开放获取",
  "oa_type": "string — subscription/hybrid/gold/diamond",
  "apc_usd": "number|null — 版面费(美元)",
  "apc_waiver": "boolean|null — 是否有减免政策",

  "cn_author_ratio": "number|null — 国人占比(0-1), 近2年中国机构作者文章比例",
  "annual_volume_2024": "number|null — 2024年发文量",
  "annual_volume_2023": "number|null — 2023年发文量",

  "review_median_days": "number|null — 投稿到接收中位数(天)",
  "review_samples": "number — 计算样本量",
  "review_coverage": "number — 有日期数据的文章比例(0-1)",
  "accept_to_online_days": "number|null — 接收到上线中位数(天)",

  "word_limit_min": "number|null — 最低字数",
  "word_limit_max": "number|null — 最高字数",
  "review_type": "string|null — single_blind/double_blind；仅有来源证据时写入",

  "ft50": "boolean — 是否在 FT50 2026 名单（来自 business_rankings.json，查询时附加）",
  "utd24": "boolean — 是否在 UTD24 名单",
  "abs_rating": "string|null — ABS/AJG 2024 评级 4*/4/3/2/1；null = 不在 AJG 中",
  "abs_field": "string|null — AJG 学科代码，如 FINANCE、MKT、GEN MAN",

  "warning_tags": ["string — 避坑标签，如'压稿严重','国人占比高','审稿快'"],
  "notes": "string — 备注",

  "_meta": {
    "last_api_update": "string — 最近API数据更新日期",
    "last_manual_update": "string|null — 最近手动更新日期",
    "has_manual_data": "boolean — 是否有手动补充数据",
    "source_scope": "ssci_ahci|scie_env_health — canonical 收录来源",
    "source_file": "string — 构建该记录的 raw 数据文件"
  }
}
```

## 字段说明

### 关键指标解读

| 字段 | 含义 | 数据来源 | 注意事项 |
|------|------|---------|---------|
| `citedness_2yr` | OpenAlex 计算的2年平均被引次数 | OpenAlex API | 与 JCR IF 略有差异，但趋势一致 |
| `cn_author_ratio` | 近2-3年有中国机构挂靠作者的文章占比 | OpenAlex Works API | 基于机构国家，非作者国籍 |
| `review_median_days` | Crossref 中有 received/accepted 日期的文章的中位审稿天数 | Crossref API | 仅反映最终录用论文的审稿时间，不含拒稿 |
| `review_coverage` | 有完整日期数据的采样文章比例 | Crossref | <0.3 时数据可信度较低 |

### 缺失数据约定

- `null` 表示数据未获取到或不适用
- 不用默认值填充未知审稿形式、分区或费用
- 在推荐表格中显示为 "—"
- `review_coverage < 0.3` 时，`review_median_days` 可信度低，应提醒用户

### 查询结果质量字段

- `quality.status` — `ok` / `limited_matches` / `no_good_match`
- `query.semantic_status` — `enabled` / `fallback` / `disabled_no_query`
- `query.semantic_error` — 语义搜索降级的具体原因；成功时为 `null`
- `_fit_scores.topic_fit` — 通过主题准入门槛后的综合主题分
- `_semantic_score` — SPECTER2 原始余弦分
- `_semantic_fit_score` — 校准后用于融合的语义相关度
- `_core_keyword_score` — 排除地区、方法、样本人群上下文后的核心概念覆盖度
- `query.business_rankings` — `{loaded, ft50_version, utd24_version, abs_version}`
- `query.filters.ft50_only` / `utd24_only` / `min_abs` — FT50 / UTD24 / ABS 硬筛选
- `query.manuscript` — 使用 `--manuscript` 时的解析摘要（标题、文章类型、正文字数、参考文献数、方法、数据、地区、`keyword_source`）
- `query.manuscript_words` — 用于字数检查的正文字数（`--word-count` 优先）
- `_word_limit_check` — `{status: ok|exceeds|limit_unknown|no_manuscript, manuscript_words, word_limit_max}`；`exceeds` 同时产生 `exceeds_word_limit` 风险标签

### parse_manuscript.py 输出

| 字段 | 含义 |
|------|------|
| `title` / `abstract` / `author_keywords` / `jel_codes` | 从正文识别；docx 优先使用 Title / Heading 样式 |
| `section_headings` | 章节标题（编号已去除） |
| `word_count_body` | 正文字数：第一个内容章节到参考文献/附录之前，不含标题块、摘要、关键词；中文按字计 |
| `word_count_total` | 全文字数 |
| `reference_count` / `figure_count` / `table_count` | 参考文献条数、图表编号数 |
| `methods` / `data_sources` / `geography` | 规则识别结果及出现次数（DID、RDD、IV、RCT、合成控制、PSM、面板 FE、SEM、ML、质性等；CFPS、CHARLS、CSMAR、Compustat 等） |
| `article_type` | `empirical` / `theoretical` / `review` / `comment` / `unknown` |
| `suggested_keywords` | 作者关键词优先，不足时用标题/摘要高频短语补充 |
| `warnings` | `title_not_detected` / `abstract_not_detected` / `references_not_detected` |

### FT50 / UTD24 / ABS 对档次分的影响

`_fit_scores.prestige_fit` 原本由 JCR 分区、影响因子、中科院分区加权得到。
期刊若在 FT50/UTD24 或有 ABS 评级，再与名单分（FT50 = UTD24 = 1.0，4* = 1.0，4 = 0.88，3 = 0.68，2 = 0.48，1 = 0.32，取高者）按 75:25 融合；
不在任何名单上的期刊保持原分，不受惩罚（避免非商科期刊被系统性压低）。

### 预留扩展字段（Phase 2）

- `desk_reject_rate` — Desk Reject 率（来自 UGC 数据）
- `rejection_median_days` — 拒稿中位时间
- `user_ratings` — 用户评分
- `similar_journals` — 相似期刊列表
