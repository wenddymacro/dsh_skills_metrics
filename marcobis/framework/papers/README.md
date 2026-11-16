# papers/：原文 PDF 的本地暂存区

这个目录存放用于起草和核验模型字典条目的原始论文 PDF（模式 B 暂存和条目核验）。**PDF 不随框架分发。**
已发表的论文通常受版权保护，所以 `.gitignore` 排除了 `papers/**/*.pdf`，每个用户自己暂存副本。

每个字典条目（`skills/model-dictionary/entries/*.yaml`）的 `verified.pdf_location` 字段记录了核验时
所对照的本地文件名。要对照原文重新核验一个条目，获取这篇论文（出版社、工作论文系列或你所在的图书馆），
按那个文件名保存到这里。

**命名约定。**每个条目的 PDF 以其字典条目 id 命名，所以 `verified.pdf_location` 是
`papers/<id>.pdf`（例如 `kilian_2009_oil_svar.pdf`、`uhlig_2005_sign_restrictions.pdf`）。少数条目
还列出了辅助 PDF。本身不是字典条目的辅助论文，用描述性的 `author_year_topic.pdf` 命名（例如
`blanchard_perotti_2002_fiscal_svar.pdf`、`lewis_2021_hetid_robust_inference.pdf`、
`mertens_ravn_2019_reply.pdf`）。

公共领域的论文可以随你自己的副本保存（如果使用版本管理，用 `git add -f`）。
