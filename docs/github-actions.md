# B12：GitHub Actions 自动测试

本文档说明 VideoCenter 的 GitHub Actions 持续集成工作流。

## 工作流文件

```text
.github/workflows/ci.yml
```

工作流名称为 `CI`，当前包含一个 `Quality and tests` Job。

## 触发条件

以下情况自动执行：

- 推送到 `main` 分支；
- 创建或更新 Pull Request；
- 在 GitHub Actions 页面手动触发。

```yaml
on:
  push:
    branches:
      - main
  pull_request:
  workflow_dispatch:
```

## 运行环境

CI 使用：

- `ubuntu-latest`
- Python 3.12
- uv 0.11.22
- `uv.lock` 中的精确依赖版本

工作流通过以下命令严格安装：

```bash
uv sync --frozen --extra dev
```

如果 `pyproject.toml` 与 `uv.lock` 不一致，CI 会直接失败，不会临时解析一套新版本。

## Action 版本

当前使用：

```text
actions/checkout@v7
actions/setup-python@v6
astral-sh/setup-uv@v8
```

这些是 B12 实施时官方仓库提供的稳定主版本。uv 本身额外固定为 `0.11.22`。

## CI 环境配置

工作流明确设置：

```text
VIDEOCENTER_ENVIRONMENT=testing
VIDEOCENTER_DATABASE_URL=sqlite:///./data/ci.db
VIDEOCENTER_LOG_FILE_ENABLED=false
VIDEOCENTER_DOCS_ENABLED=false
```

CI 不读取开发或生产数据库，不写入日志文件，也不开放 API 文档。

pytest 仍会根据 B08 创建独立随机测试数据库；`ci.db` 主要用于迁移升级和结构一致性检查。

## 执行步骤

### 1. 检出代码

```yaml
uses: actions/checkout@v7
```

### 2. 安装 Python

```yaml
uses: actions/setup-python@v6
```

Python 版本固定为 3.12。

### 3. 安装 uv

```yaml
uses: astral-sh/setup-uv@v8
```

开启 uv 依赖缓存，并使用 `uv.lock` 作为缓存依赖依据。

### 4. 安装依赖

```bash
uv sync --frozen --extra dev
```

### 5. 运行 pre-commit

```bash
uv run pre-commit run --all-files
```

覆盖文件基础检查、Ruff lint 和 Ruff format。

如果 hook 修改了文件，CI 会失败，开发者需要在本地运行 hooks 并提交修复结果。

### 6. 验证数据库迁移

```bash
uv run alembic upgrade head
uv run alembic check
```

第一条命令验证空数据库可以升级到最新版本；第二条命令验证模型没有遗漏迁移。

### 7. 运行测试和覆盖率

```bash
uv run pytest \
  --cov=videocenter \
  --cov-report=term-missing \
  --cov-report=xml
```

测试结果和缺失覆盖行会显示在 GitHub Actions 日志中，同时生成 `coverage.xml`。

B12 暂不设置最低覆盖率门槛。可以在测试覆盖逐步完善后，再增加 `--cov-fail-under`。

## 权限与并发

工作流只申请：

```yaml
permissions:
  contents: read
```

它不能修改仓库、创建 Release 或推送代码。

同一分支有新提交时，旧的运行会自动取消：

```yaml
concurrency:
  group: ci-${{ github.workflow }}-${{ github.ref }}
  cancel-in-progress: true
```

这样可以减少无意义的重复运行。

单次 Job 超时时间为 15 分钟，避免异常任务长期占用 Runner。

## 本地等价检查

提交前建议执行：

```powershell
uv sync --frozen --extra dev
uv run videocenter-hooks-run
uv run alembic upgrade head
uv run alembic check
uv run pytest --cov=videocenter --cov-report=term-missing
```

日常开发可以使用：

```powershell
uv run videocenter-lint
uv run pytest
```

## 查看结果

推送工作流后，在 GitHub 仓库中打开：

```text
Actions → CI
```

Pull Request 页面也会显示 CI 检查状态。

建议在 GitHub 分支保护规则中将 `Quality and tests` 设为合并前必需检查。

## 常见失败

### Locked dependencies 不一致

执行：

```powershell
uv lock
uv sync --extra dev
```

确认无误后提交 `pyproject.toml` 和 `uv.lock`。

### pre-commit 修改了文件

本地执行：

```powershell
uv run videocenter-hooks-run
git diff
```

检查并提交自动修复结果。

### Alembic check 失败

说明 SQLAlchemy 模型发生变化但没有对应迁移：

```powershell
uv run alembic revision --autogenerate -m "describe change"
uv run alembic upgrade head
uv run alembic check
```

### 测试失败

本地运行失败测试：

```powershell
uv run pytest -q
```

只运行集成测试：

```powershell
uv run pytest -m integration
```

## 当前验证

B12 已在本地执行与 CI 等价的检查：

- 工作流 YAML 结构测试通过；
- Ruff lint 与 format 通过；
- Alembic 空库升级成功；
- Alembic 模型检查通过；
- 55 项测试通过；
- 当前整体代码覆盖率为 77%；
- 开发数据库未参与 CI 测试流程。
