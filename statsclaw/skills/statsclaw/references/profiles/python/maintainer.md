<!-- statsclaw:maintainer-template 未填写：填写后删除这一行，各角色才会采用本文件 -->
# 维护者规范：Python

这里写**你自己维护 Python 包的规范**。与本目录 `profile.md` 冲突时，以本文件为准（但不能覆盖规格隔离和容差完整性）。跨语言的规定写在上一级的 `maintainer.md`。

## 1. 我维护的包

| 包 | 仓库 / 路径 | 发布渠道 | 支持的 Python 版本 | 备注 |
|---|---|---|---|---|
|  |  |  |  |  |

## 2. 项目布局与工具

- 布局（`src/` 还是平铺）：
- 环境与依赖管理（uv / poetry / pip / conda）：
- 构建后端（hatchling / setuptools / flit / poetry-core）：
- lint / 格式化 / 类型检查（ruff、black、mypy、pyright）及配置：

## 3. 版本与元数据

- 版本号来源（写死 / `__version__` / setuptools-scm）：
- 何时升级：

## 4. 编码习惯

- API 风格（函数式 / 类 / 仿 statsmodels 的 fit-result 结构）：
- 输入类型（numpy、pandas、polars；是否接受公式）：
- 返回对象和 `summary()` 的习惯：
- 异常类型和报错措辞：
- docstring 风格（NumPy / Google）：
- 依赖哪些包、是否允许新增依赖：

## 5. 测试习惯

- 测试框架和目录：
- 数值断言写法（`numpy.testing.assert_allclose` 的 rtol / atol 默认值）：
- 必须对照的基准（statsmodels、linearmodels、R 包、Stata 结果、论文）：
- 回归测试的数据集：

## 6. 文档习惯

- 文档工具（Sphinx / MkDocs / 只有 README）：
- 示例的形式（notebook / 脚本 / docstring 例子）：

## 7. 发布流程

- 发布到哪（PyPI、conda-forge、GitHub）：
- 发布前后要做的事：

## 8. 踩过的坑

-
