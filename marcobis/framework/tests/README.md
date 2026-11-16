# 测试

`scripts/lib/` 的自洽性和跨软件包验证。测试对照的是理论和独立的软件包，而不是早先的输出（见下面
"为什么旧输出绝不是标准答案"）。

## 验证原则

1. **理论自洽**：由数学推出的性质：
   - `h=0` 时的 Cholesky 脉冲响应精确等于 `np.linalg.cholesky(Sigma_u)`
   - 控制变量相同时，`h=0` 的 LP 等于 OLS 的冲击系数
   - LP-IV 的第一阶段与单独的 OLS 回归一致
   - `h=0` 时，政策变量对自身冲击的 LP-IV 等于 1
   - `lambda_1 -> 无穷` 时，BVAR 后验均值 -> OLS 估计
   - `lambda_1 -> 0` 时，BVAR 系数收缩到 `rw_deltas`
2. **跨软件包验证**：`statsmodels.tsa.api.VAR` 是独立维护的：
   - `fit_var` 的系数与 `statsmodels` 一致到 1e-10
   - AIC、BIC 与 `statsmodels` 一致到浮点精度
   - `cholesky_irf` 的点估计与 `statsmodels.results.irf().orth_irfs` 一致
3. **基于性质的检查**：无论输入是什么，输出都满足的不变量：
   - 置信区间有序：`lower_90 ≤ lower_68 ≤ median ≤ upper_68 ≤ upper_90`
   - 符号约束脉冲响应在每个受约束期限上都满足自己的约束
   - 参数抽样以点估计为中心

## 运行

```bash
# pytest 是开发依赖，不在 requirements.txt 里：
python -m pip install pytest

# 快速测试集（约 2–3 分钟）。缺少数据 CSV 时，依赖 FRED 数据的测试会干净地跳过。
python -m pytest tests/ -q

# 包括较慢的端到端复现冒烟测试（约 20 分钟）以及国家统计局联网测试：
python -m pytest tests/ -q --runslow

# 只运行文档 / 设定漂移检查：
python -m pytest tests/test_doc_consistency.py -q

# 只运行国家统计局数据层的测试（离线；联网部分加 --runslow）：
python -m pytest tests/test_nbs.py -q
```

## 测试了什么

1,000 多个测试，每个 lib 模块一个测试模块，加上下面这些横向的层（以及差分测试、教科书基准和高阶矩
测试集）：

| 层 | 文件 | 固定了什么 |
|---|---|---|
| 逐模块单元测试 | `test_var.py`、`test_bvar.py`、`test_identification.py`、`test_lp.py`、`test_filters.py`、`test_tvp.py`……（每个 lib 模块一个） | API 约定、理论性质、极限行为 |
| 约定契约 | `test_conventions.py` | `CONVENTIONS.md` 中的数学约定（期限下标、归一化、ddof、先验校准），以闭式断言表达 |
| 数据生成过程还原契约 | 在相关模块的测试中 | 在已知数据生成过程上还原参数（只测形状和有限性，发现不了方向、符号或校准错误） |
| 覆盖率研究 | `test_coverage.py`（慢） | 推断机制的蒙特卡洛区间覆盖率 |
| 文档 / 设定漂移检查 | `test_doc_consistency.py` | YAML 可解析性、索引与条目同步、过时的计数、失效链接、悬空的 lib 引用 |
| 端到端冒烟测试 | `test_replications_smoke.py`（`--runslow`） | 完整运行复现，对照其 `paper_targets.yaml`；运行完成但有论文目标不通过时，测试失败（数值回归防护） |
| 国家统计局数据层 | `test_nbs.py` | 客户端（时间代码、分段拼接、指标匹配、遇到防火墙验证页立即停止）、`nbs` fetcher 的 cache-on-fetch、`lib.preprocess.china` 清洗函数、自带面板定义的有效性；联网测试需 `--runslow` |

## 为什么旧输出绝不是标准答案

单元测试和契约测试对照的是理论（闭式解、已知数据生成过程、已发表的数字），而不是之前某个实现的输出。
原因在方法论上：两个实现共享同一个 bug 时，对照旧实现的回归测试会错误地确认新实现。所以这些契约都表述
为正确的数学必须满足的性质，并在测试的 docstring 中写明来源（论文公式、CONVENTIONS.md 条目或解析
极限）。

例外是明确的回归检查：复现冒烟测试（对某些复现，目标是作者自己同一复现的结果，每个
`paper_targets.yaml` 都会说明），以及少数固定某个复现主要数字的端到端测试。它们能发现与之前某次运行
的偏离，但发现不了那次运行本身就有的错误。

## 添加新测试

添加新的库模块时，优先（按顺序）：
1. 按构造必须成立的理论性质
2. 适用时，与 `statsmodels` / `scipy` / `numpy` 比较
3. 极限行为检查（例如某个超参数趋于退化值时，输出应趋于已知的闭式解）

避免：
- "与 `legacy_script.py` 的输出一致"：那是回归测试，不是正确性测试
- "与论文 X 的表 1 一致"：有用但脆弱（论文的数据可能无法由修订后的 FRED 数据重现）
