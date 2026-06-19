# B10：Ruff 代码检查命令

本文档说明 VideoCenter 的 Ruff 检查入口、检查范围和开发流程。

## 统一命令

项目提供控制台命令：

```powershell
videocenter-lint
```

使用 uv：

```powershell
uv run videocenter-lint
```

使用 pip 虚拟环境：

```powershell
videocenter-lint
```

也可以不依赖控制台脚本，直接通过模块运行：

```powershell
python -m videocenter.quality
```

## 检查内容

统一命令依次执行：

```powershell
python -m ruff check src tests migrations
python -m ruff format --check src tests migrations
```

第一步检查代码问题，第二步确认代码已经按照 Ruff formatter 格式化。

任意一步失败时命令立即返回非零退出码，适合本地开发、Git Hook 和 CI 使用。

## 检查范围

当前检查目录：

```text
src/
tests/
migrations/
```

不检查运行数据、虚拟环境、IDE 设置或生成缓存。

## Ruff 规则

配置位于 `pyproject.toml`：

```toml
[tool.ruff]
line-length = 100
target-version = "py312"

[tool.ruff.lint]
select = ["E", "F", "I", "UP", "B"]
```

当前规则类别：

| 规则 | 说明 |
| --- | --- |
| `E` | pycodestyle 错误 |
| `F` | Pyflakes 未使用导入、未定义名称等 |
| `I` | import 排序 |
| `UP` | Python 语法现代化 |
| `B` | flake8-bugbear 常见缺陷 |

项目目标版本为 Python 3.12。

## FastAPI B008 例外

FastAPI 使用以下依赖注入写法：

```python
db: Session = Depends(get_db)
```

Ruff 的 `B008` 通常禁止在参数默认值中调用函数，但 `Depends()` 是 FastAPI 官方声明式 API。

因此只对路由目录配置例外：

```toml
[tool.ruff.lint.per-file-ignores]
"src/videocenter/api/routes/*.py" = ["B008"]
```

该规则没有在全项目关闭，其他模块中出现参数默认函数调用仍会被检查。

## 自动修复

修复安全的 lint 问题：

```powershell
uv run ruff check --fix src tests migrations
```

格式化代码：

```powershell
uv run ruff format src tests migrations
```

完成后再次执行：

```powershell
uv run videocenter-lint
```

不要不加检查地使用 `--unsafe-fixes`，这类修复可能改变代码行为。

## 开发流程

提交代码前建议执行：

```powershell
uv run videocenter-lint
uv run pytest
```

如果只修改文档，可以不运行 Ruff；修改 Python 代码时必须运行。

## CI 使用

CI 中先严格同步锁文件，再执行检查：

```powershell
uv sync --frozen --extra dev
uv run videocenter-lint
uv run pytest
```

命令返回非零退出码时，CI 应停止后续发布步骤。

## 当前基线

B10 已完成：

- 全部 Python 文件经过 Ruff formatter；
- `ruff check` 无告警；
- `ruff format --check` 无差异；
- 添加跨平台控制台命令；
- 添加命令成功及失败短路测试；
- 数据库模型与 Alembic 迁移保持一致。
