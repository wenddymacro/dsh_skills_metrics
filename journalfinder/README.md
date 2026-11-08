# journalfinder · DSH 插件

把 mskills 仓库里的 **JournalFinder**（投稿期刊推荐工具）做成 [DeepSeek Harness](https://github.com/deepseek-ai/deepseek-harness) 插件。
安装后，每个会话的 skill 目录里会多出 `find-journal`：当你问"这篇论文该投哪些期刊"时，agent 会在本机用 Python 查询插件自带的期刊库，
给出 5–8 本候选期刊，并标注 JCR 分区、中科院分区、影响因子、FT50、UTD24、ABS（AJG 2024）星级、OA/APC、国人占比、年发文量和审稿周期。

它只做**投稿候选推荐**，不预测录用，也不改稿。

## 功能

- 输入可以是题目、摘要、关键词，也可以是整篇稿件（PDF / Word / TXT）：自动提取标题、摘要、关键词、JEL、正文字数、研究方法、数据来源、文章类型，并检查期刊字数限制
- 期刊库：5,183 本 JCR SSCI/AHCI 期刊（4,802 本 SSCI/AHCI + 381 本环境健康交叉期刊）
- 主题贴合度先过门槛，再按偏好排序：主题贴合 / 求档次 / 求快 / 预算有限 / 国人友好 / 容量稳
- 商科名单筛选：只看 FT50、只看 UTD24、ABS 3 星以上等
- 完全离线，不需要网络

## 依赖

- DeepSeek Harness ≥ 0.2.1-rc.1
- 本机 Python 3.10 及以上版本（`python3`；Windows 上为 `python`）。只用标准库
- 解析 PDF 稿件时需要 `pypdf`：`python3 -m pip install pypdf`。`.docx` / `.txt` 不需要额外依赖

## 安装

**桌面版**：打开「插件 → 添加插件」，填入下面的地址，点击「安装」，再点击「立即启用」。`<commit>` 换成要安装的提交号。
具体操作与 [whichdidshouldiuse 的图文指南](../whichdidshouldiuse/docs/GUIDE.md) 相同，只是地址末尾的路径换成 `/journalfinder`。

```text
github:wenddymacro/dsh_skills_metrics#<commit>&path:/journalfinder
```

**命令行**（CLI 管理的 profile）：

```bash
dsh plugin --profile <profile> add "github:wenddymacro/dsh_skills_metrics#<commit>&path:/journalfinder"
```

从本地 checkout 安装（便于开发）：

```bash
dsh plugin --profile <profile> add "link:/abs/path/to/dsh_skills_metrics/journalfinder"
```

如果把已安装的插件换成另一个来源或版本，需要重启 DeepSeek Harness，新代码才会生效。

## 使用

直接用自然语言提问即可，例如：

> 我的论文研究最低工资对青年就业的影响，用了 DID，数据来自中国。帮我推荐投稿期刊，求档次，只要 Q1–Q2。

> /Users/me/papers/draft.pdf 这篇稿子投哪里合适？只看 ABS 3 星以上。

也可以输入 `/find-journal` 显式调用这个 skill。没有说明偏好时，agent 会先问一次你更看重哪些方面。

## 与 mskills 版本的差别

- **只有关键词召回。** 不附带 SPECTER2/FAISS 语义索引（模型约 440 MB，构建依赖 `sentence-transformers` 和 `faiss`），
  所以报告里会注明"本次为关键词匹配"。跨学科论文多给几个领域关键词效果更好。
- 只附带运行时需要的 `query_db.py`、`parse_manuscript.py`、`runtime_paths.py` 和两份数据文件
  （`journals_ssci.json`、`business_rankings.json`）。数据管道、抓取脚本和旧版 economics/demography 库不在插件里。
- 脚本通过自身位置找到 `data/`，不需要安装配置文件；仍可用 `JOURNAL_FINDER_DATA_DIR` 或 `--data-dir` 指向别的数据目录。
- 偏好在对话里问一次，不依赖 Claude Code 的 AskUserQuestion 卡片。

## 结构

```
journalfinder/
├── package.json            # dsh.bundle 声明，不打包任何依赖
├── cordis.patch.yml        # 挂载本包的插件
├── index.js                # 用 dsh 自带的 skill-filesystem provider 挂载 skills/
├── locale/{en,zh}.json     # 插件管理器中显示的标题与描述
├── icon.svg
├── skills/find-journal/
│   ├── SKILL.md            # agent 的工作流程、参数速查与报告格式
│   ├── scripts/            # query_db.py、parse_manuscript.py、runtime_paths.py
│   ├── data/               # journals_ssci.json（期刊库）、business_rankings.json（FT50/UTD24/ABS）
│   └── references/         # 数据 schema、致谢、许可证、名单来源
└── test.mjs                # node --test test.mjs
```

## 测试

```bash
node --test test.mjs
```

单元测试检查 manifest、patch、locale、SKILL frontmatter 和 `apply()` 的挂载方式；本机有 Python 3.10+ 时，
集成测试会从任意工作目录运行关键词查询、UTD24 筛选和稿件解析，确认脚本能找到插件自带的数据。

## 许可与致谢

插件代码采用 MIT 许可。`skills/find-journal/scripts/` 与 `data/` 来自
[wenddymacro/mskills](https://github.com/wenddymacro/mskills) 的 JournalFinder（分支 `claude/blissful-maxwell-2a79mr`，提交 `776f262`），
它 fork 自 [alexishuang1901-hub/journal-finder](https://github.com/alexishuang1901-hub/journal-finder)（MIT，版权归 journal-finder contributors），
感谢原作者。FT50 / UTD24 / AJG 2024 名单快照取自 [wosaide/wosaide-journal-lists](https://github.com/wosaide/wosaide-journal-lists)。
完整来源见 [`skills/find-journal/references/ACKNOWLEDGMENTS.md`](skills/find-journal/references/ACKNOWLEDGMENTS.md)
和 [`journal-lists-SOURCE.md`](skills/find-journal/references/journal-lists-SOURCE.md)。
