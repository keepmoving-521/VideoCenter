# Alembic 数据库迁移

本文档记录 VideoCenter 在 `B01` 迭代中引入 Alembic 数据库迁移的设计、配置与使用方式。

## 目标

随着影视资源、下载任务、观看历史等数据模型持续扩展，不能再依赖删除数据库后重新建表。Alembic 用于：

- 记录每次数据库结构变化；
- 将已有数据库安全升级到新版本；
- 必要时回退数据库结构；
- 根据 SQLAlchemy 模型生成迁移草稿；
- 保证开发、测试和生产环境使用一致的数据库结构。

## 当前实现

项目已完成以下基础设施：

- 在运行依赖中加入 `alembic>=1.14,<2.0`；
- 创建根目录配置文件 `alembic.ini`；
- 创建迁移目录 `migrations/`；
- 在 `migrations/env.py` 中加载全部 SQLAlchemy 模型；
- 将 `Base.metadata` 配置为自动生成迁移的数据源；
- 从项目设置中读取数据库连接地址；
- 开启字段类型差异检测；
- 为 SQLite 开启批量迁移模式。

初始数据库版本已在 `B02` 迭代中创建，详见
[初始数据库迁移](initial-database-migration.md)。

## 目录说明

```text
alembic.ini
migrations/
├── env.py
├── README
├── script.py.mako
└── versions/
```

- `alembic.ini`：Alembic 主配置和日志配置。
- `migrations/env.py`：连接项目配置、数据库和模型元数据。
- `migrations/script.py.mako`：新迁移文件的生成模板。
- `migrations/versions/`：保存实际的迁移版本文件。

## 数据库连接配置

迁移命令与应用使用相同的配置系统。数据库地址来自环境变量：

```dotenv
VIDEOCENTER_DATABASE_URL=sqlite:///./data/videocenter.db
```

如果 `.env` 中未配置该变量，则使用项目默认值：

```text
sqlite:///./data/videocenter.db
```

执行迁移命令前，应确认当前目录和 `.env` 指向了正确的数据库，尤其不要误将开发迁移执行到生产数据库。

## 常用命令

下面同时给出 uv 和 pip 虚拟环境的用法。

### 查看当前数据库版本

```powershell
# uv
uv run alembic current

# pip 虚拟环境
python -m alembic current
```

### 查看迁移历史

```powershell
uv run alembic history --verbose
```

### 查看最新迁移版本

```powershell
uv run alembic heads
```

### 根据模型变化生成迁移草稿

```powershell
uv run alembic revision --autogenerate -m "add media tags"
```

`--autogenerate` 只负责比较模型和数据库结构。生成后必须人工检查迁移文件，特别关注：

- 字段重命名是否被误判为“删除旧字段并新增字段”；
- 删除表或字段是否会造成数据丢失；
- 新增非空字段是否需要默认值或数据回填；
- SQLite 批量迁移是否保留索引、约束和外键。

### 升级到最新版本

```powershell
# uv
uv run alembic upgrade head

# pip 虚拟环境
python -m alembic upgrade head
```

### 升级到指定版本

```powershell
uv run alembic upgrade <revision>
```

### 回退一个版本

```powershell
uv run alembic downgrade -1
```

### 回退到指定版本

```powershell
uv run alembic downgrade <revision>
```

生产环境执行回退前必须先备份数据库，并确认迁移文件的 `downgrade()` 不会破坏业务数据。

### 生成离线 SQL

```powershell
uv run alembic upgrade head --sql
```

该命令只输出 SQL，不直接修改数据库，适合迁移审查。

## 模型变更工作流

每次修改 `src/videocenter/models/` 下的数据模型后，建议按以下流程操作：

1. 修改 SQLAlchemy 模型。
2. 执行 `revision --autogenerate` 生成迁移草稿。
3. 人工检查并完善 `upgrade()` 和 `downgrade()`。
4. 在测试数据库执行 `upgrade head`。
5. 运行项目测试。
6. 如有必要，执行一次降级和重新升级测试。
7. 将模型代码与对应迁移文件放在同一个提交中。

示例：

```powershell
uv run alembic revision --autogenerate -m "add media rating"
uv run alembic upgrade head
uv run pytest
```

## 新增模型时的注意事项

Alembic 只能识别已经加载到 `Base.metadata` 的模型。新增模型模块后，需要确保它被
`videocenter.models` 导入，并且 `migrations/env.py` 加载模型包。

当前迁移环境加载以下模型：

- `Media`
- `LocalResource`
- `DownloadTask`
- `WatchHistory`

如果新模型没有出现在自动生成结果中，应先检查模型导入关系，而不是手写一份缺少元数据依据的迁移。

## SQLite 注意事项

VideoCenter 当前默认使用 SQLite。SQLite 对部分 `ALTER TABLE` 操作支持有限，因此迁移环境启用了 Alembic 的批量模式。

复杂结构修改可能采用以下过程：

1. 创建临时表；
2. 复制旧表数据；
3. 删除旧表；
4. 将临时表重命名。

因此在执行删除字段、修改约束等迁移前，应先备份数据库文件：

```powershell
Copy-Item .\data\videocenter.db .\data\videocenter.backup.db
```

## 提交规范

数据库模型发生变化时，应同时提交：

- 修改后的模型文件；
- `migrations/versions/` 下的新迁移文件；
- 必要的测试；
- 涉及行为变化时的专题文档。

不要提交以下内容：

- 本地 `data/videocenter.db`；
- 临时数据库备份；
- 迁移执行产生的本地缓存。

## 当前状态

- 已创建初始迁移版本 `81fd73d3a90a`；
- 应用启动时不再调用 `create_all()`；
- 新环境必须先执行 `alembic upgrade head`；
- 已有数据库可在结构核验后使用 `alembic stamp head` 接入版本管理。
