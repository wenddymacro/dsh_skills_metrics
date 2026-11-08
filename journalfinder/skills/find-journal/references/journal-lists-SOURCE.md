# 期刊名单快照来源 / Source of journal-list snapshots

本目录的三个 CSV 原样复制自 **[wosaide/wosaide-journal-lists](https://github.com/wosaide/wosaide-journal-lists)** 的 `LIST/` 目录，内容未作修改。

- 复制时的上游提交：`2c7584eda5ee7e4524f9221bfee91c5eb268e587`（2026-11-07）
- 复制日期：2026-11-08
- 上游仓库未声明开源许可证。名单本身由各发布机构维护，以下是各名单的官方来源（摘自上游 `LIST/README.md`）：

| 文件 | 名单 | 官方来源 |
|------|------|----------|
| `AJG2024.csv` | Academic Journal Guide 2024，Chartered Association of Business Schools。列：Print ISSN, E-ISSN, Field, Journal Title, Publisher, AJG 2024 | <https://charteredabs.org/academic-journal-guide/academic-journal-guide-2024>；方法说明：<https://assets.charteredabs.org/ajg-2024-methodology.pdf> |
| `FT50.csv` | Financial Times 商学院研究排名期刊名单（FT50 2026，生效日期 2026-04-29） | <https://www.ft.com/content/db863a0a-6524-45f9-bc52-fee997634bdc> |
| `UTD24.csv` | UT Dallas Top 100 Business School Research Rankings 使用的 24 本期刊 | <https://jindal.utdallas.edu/the-utd-top-100-business-school-research-rankings/> |

## 更新

出了新版名单后，用上游的新快照或官方文件替换对应的 CSV，然后重新生成标注层：

```bash
python scripts/build_business_rankings.py
```

各名单的权利归其发布机构所有。AJG 的使用请遵守 Chartered ABS 的条款；如需公开再分发，请先确认是否符合其许可要求。
