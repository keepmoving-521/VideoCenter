# B08：测试专用数据库

本文档说明 VideoCenter 自动化测试使用的独立数据库、生命周期和安全机制。

## 目标

执行测试时不得连接或修改开发、生产数据库。测试数据库应满足：

- 在导入应用和数据库模块前完成配置；
- 每次测试运行使用独立数据库文件；
- 使用真实 Alembic 迁移创建结构；
- 不依赖开发数据库已有的表或数据；
- 测试之间自动清理业务数据；
- 测试结束后自动删除数据库文件；
- 配置异常时拒绝继续执行。

## 数据库文件

pytest 启动时生成随机 SQLite 数据库：

```text
data/pytest-<uuid>.db
```

例如：

```text
data/pytest-e280997fd87f4ce6af65cbb27ed9feae.db
```

随机文件名使并行或连续测试不会复用旧数据。`data/` 已被 Git 忽略，因此测试数据库不会提交到仓库。

## 配置时机

测试配置位于：

```text
tests/conftest.py
```

pytest 会在收集测试模块前加载该文件。此时强制设置：

```text
VIDEOCENTER_ENVIRONMENT=testing
VIDEOCENTER_DATABASE_URL=sqlite:///.../data/pytest-<uuid>.db
VIDEOCENTER_LOG_FILE_ENABLED=false
VIDEOCENTER_DOCS_ENABLED=true
```

这样测试模块随后导入 `videocenter.main` 或 `videocenter.core.database` 时，数据库引擎已经绑定到测试库，不可能先连接开发库。

## 安全检查

创建数据库前会验证：

- 当前环境必须为 `testing`；
- 数据库文件名必须以 `pytest-` 开头；
- 数据库必须位于项目的 `data/` 目录。

任意条件不满足时测试直接失败，不会执行数据库迁移或清理操作。

## 数据库创建

测试会话开始时执行：

```python
command.upgrade(alembic_config, "head")
```

即使用与正式环境相同的 Alembic 迁移建表，而不是调用 SQLAlchemy `create_all()`。

这可以同时验证：

- 迁移文件能够创建完整数据库；
- 测试结构与生产结构一致；
- 新增模型时是否遗漏迁移。

## 测试隔离

### db_session fixture

数据库测试可以直接声明：

```python
def test_create_media(db_session):
    ...
```

`db_session` 使用项目的测试数据库会话工厂，并在测试结束时执行回滚和关闭。

### 自动清理

每个测试结束后，fixture 会按照外键依赖的逆序清空全部业务表。

`alembic_version` 不属于 SQLAlchemy 业务模型元数据，因此不会被清理，测试期间数据库始终保持在最新迁移版本。

即使测试主动调用 `commit()`，提交的数据也会在该测试结束后删除，不会影响下一项测试。

## 生命周期

完整流程如下：

```text
pytest 启动
  → 设置 testing 环境和随机数据库地址
  → 导入应用与数据库模块
  → Alembic upgrade head
  → 执行测试
  → 每项测试后清空业务表
  → 释放数据库连接池
  → 删除 pytest-*.db
```

测试中断后如果异常遗留了 `pytest-*.db`，可以安全删除以 `pytest-` 开头的测试文件。不要使用模糊规则删除其他数据库。

## 运行方式

使用 uv：

```powershell
uv run pytest
```

使用 pip 虚拟环境：

```powershell
python -m pytest
```

无需提前创建 `.env.testing`，测试 fixture 会覆盖关键隔离配置。

`.env.testing` 仍可用于手动启动测试环境服务，但 pytest 不依赖固定的 `videocenter-testing.db`。

## 新增数据库测试

推荐使用 `db_session`：

```python
from sqlalchemy import select

from videocenter.models.media import Media


def test_media_is_saved(db_session):
    db_session.add(Media(title="Test movie"))
    db_session.commit()

    media = db_session.scalar(select(Media))
    assert media.title == "Test movie"
```

不要在测试中：

- 硬编码 `data/videocenter.db`；
- 自行连接开发数据库；
- 删除整个 `data/` 目录；
- 依赖其他测试创建的数据；
- 跳过 Alembic 后直接手工建表。

## 当前验证

B08 已验证：

- pytest 使用随机测试数据库；
- 测试环境标识为 `testing`；
- 数据库结构由 Alembic 创建；
- 会话 fixture 指向测试数据库；
- 测试结束后不残留 `pytest-*.db`；
- 完整测试运行前后开发数据库内容哈希保持不变。
