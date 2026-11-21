# 语言包：Python

本目录（`<SKILL>/references/profiles/python/`）是 Python 的语言包。组长派发时把本文件路径交给每个角色；每个角色读本文件，再读 `maintainer.md`（填写后优先级高于本文件）。

| 文件 | 内容 |
|---|---|
| `profile.md` | 本文件：识别、开工检查、验证命令、编码与测试约定、发布检查 |
| `maintainer.md` | **维护者的 Python 规范**（填写后优先级高于本文件） |

> 本语言包目前是上游 StatsClaw 的 profile 加开工检查和发布检查，还没有 Stata 语言包那样的认证写法、基准对照表和静默错误清单；这些等维护者提供自己的包后再补。

## 开工检查（组长做）

1. 记下 `python --version`，以及项目用的环境工具：`uv.lock` → uv，`poetry.lock` → poetry，`environment.yml` → conda，否则 venv / pip。验证命令一律在该环境里运行（如 `uv run pytest`）。
2. 记下 `pyproject.toml` 里的 `requires-python`、测试框架、lint / 类型检查工具，写进 `.statsclaw/context.md`。
3. 缺依赖时**任何角色都不自动 `pip install` / `uv add`**：记录缺哪个、为什么需要，交给组长问用户。

## 写入范围建议

| 角色 | 典型写入范围 |
|---|---|
| builder | `src/<pkg>/` 或 `<pkg>/` 下的源码、`tests/` 下对应的单元测试、`pyproject.toml` 的依赖段（需记入 mailbox） |
| simulator | 仿真目录（如 `simulations/`、`benchmarks/`） |
| scriber | docstring 以外的文档：`docs/`、README、CHANGELOG、示例 notebook / 脚本 |

docstring 跟着代码走，由 builder 写；scriber 负责它们和文档站点的一致性。


## Repo Markers（识别）

Detect this profile when the target repository contains:

- `pyproject.toml` or `setup.py` or `setup.cfg` (at least one required)
- `src/` directory or a top-level package directory with `__init__.py`
- `tests/` directory

## Validation Commands

| Stage | Command | Notes |
| --- | --- | --- |
| Unit tests | `pytest` | Core test suite |
| Tests + coverage | `pytest --cov` | With coverage reporting |
| Type check | `mypy .` or `mypy src/` | Static type analysis |
| Lint | `ruff check .` | Fast linting |
| Format check | `ruff format --check .` | Formatting verification |
| Build | `python -m build` | Produces sdist and wheel |

## Documentation

- **API docs**: Docstrings in source files (NumPy or Google style)
- **Type annotations**: Inline type hints on all public functions and methods
- **Docs site**: Sphinx (`docs/`) or MkDocs (`mkdocs.yml`) when present
- **README**: `README.md` or `README.rst` at the repo root
- **CHANGELOG**: `CHANGELOG.md` or `CHANGES.rst` for user-visible changelog

## Common Tooling

- `pytest` — test framework
- `mypy` — static type checker
- `ruff` — linter and formatter
- `uv` or `pip` — dependency management
- `sphinx` or `mkdocs` — documentation site generation
- `coverage` / `pytest-cov` — test coverage reporting

## Build Exclusions

StatsClaw keeps every run artifact under `.statsclaw/` in the project root and lists it in `.git/info/exclude`, so nothing is committed by accident. If the package build would still pick it up (for example `R CMD build`, `MANIFEST.in`, `.npmignore`), add `.statsclaw/` to the build ignore file only when the user agrees.

## Builder Notes

- Follow PEP 8 style conventions; prefer `ruff` auto-formatting when the project uses it.
- Use type hints on all public function signatures; prefer `from __future__ import annotations` for modern annotation syntax.
- Place tests in `tests/` mirroring the source layout (e.g., `tests/test_module.py` for `src/package/module.py`).
- Do not add new dependencies to `pyproject.toml` without noting it in the mailbox for leader review.
- Use `__all__` in `__init__.py` to control the public API when the package follows that convention.
- Prefer raising specific exception types over bare `Exception`.
- Use `pathlib.Path` over `os.path` for filesystem operations unless the project has an established convention.

## Tester Notes

- Run `pytest` with coverage (`--cov`) and report the coverage percentage for changed modules.
- `mypy` must pass with zero errors on the changed files at minimum; prefer whole-project type check.
- `ruff check` must pass with zero errors; treat all lint violations as blockers.
- If the project uses `ruff format`, verify formatting compliance.
- If Sphinx or MkDocs docs exist, confirm they build without warnings.
- Check that all new public functions have docstrings.

## Simulation Notes

- Use `numpy.random.default_rng(seed)`; derive per-scenario generators with `numpy.random.SeedSequence(master).spawn(k)`.
- Parallelize with `joblib` or `concurrent.futures` and pass each worker its own spawned generator.
- Store per-replication results in a `pandas.DataFrame` (or parquet / csv on disk for large R); plots with `matplotlib`.

## 发布检查（工作流 8）

组长写的 test-spec.md 至少包含：

1. `python -m build` 生成 sdist 和 wheel 成功；`python -m twine check dist/*` 通过。
2. 在**临时虚拟环境**里 `pip install dist/<wheel>` 后能 `import` 并跑一个最小例子（不装进用户的环境）。
3. 版本号在 `pyproject.toml`（或动态版本来源）、`__version__`、CHANGELOG 三处一致。
4. 测试、lint、类型检查全部通过；文档站点能构建。

上传 PyPI 需要用户自己的凭证，插件只准备文件、核对清单，不代为上传。
