# B02：创建当前数据库初始迁移

本文档记录 VideoCenter 首个数据库迁移版本的结构、验证结果和使用方式。

## 迁移版本

```text
Revision ID: 81fd73d3a90a
Parent: base
文件: migrations/versions/81fd73d3a90a_initial_schema.py
```

该版本是项目迁移历史的起点，负责创建当前全部业务表。

## 创建的表

### media

保存影视条目的基础信息，包括：

- 标题和原标题；
- 电影、电视剧等媒体类型；
- 简介、上映年份；
- 海报地址和来源页面地址；
- 创建和更新时间。

索引：

- `ix_media_title`
- `ix_media_media_type`

### local_resources

保存已登记的本地视频文件，包括文件路径、名称、大小、类型和时长。

约束和索引：

- `file_path` 唯一约束；
- `media_id` 外键；
- 删除影视条目时将 `media_id` 设置为空；
- `ix_local_resources_media_id` 索引。

### download_tasks

保存下载任务的来源、目标文件、状态、进度和错误信息。

约束和索引：

- `media_id` 外键；
- `ix_download_tasks_media_id` 索引；
- `ix_download_tasks_status` 索引。

### watch_history

保存每个影视条目的播放位置和最近观看时间。

约束和索引：

- `media_id` 外键；
- `resource_id` 外键；
- 每个影视条目只保留一条观看进度；
- `ix_watch_history_media_id` 索引；
- `ix_watch_history_watched_at` 索引。

Alembic 还会创建 `alembic_version` 表，用于记录数据库当前迁移版本。

## 新环境初始化

安装依赖并配置 `.env` 后，必须先升级数据库：

```powershell
# uv
uv run alembic upgrade head

# pip 虚拟环境
python -m alembic upgrade head
```

然后再启动服务：

```powershell
uv run uvicorn videocenter.main:app --reload
```

应用启动时不再自动调用 SQLAlchemy 的 `create_all()`。这样可以保证所有数据库结构变化都有明确的迁移记录。

## 已有数据库接入

如果数据库中的业务表由旧版 `create_all()` 创建，但尚无 `alembic_version` 表，不应直接执行初始迁移，否则会出现“表已存在”错误。

正确流程：

1. 停止应用；
2. 备份数据库；
3. 确认现有结构与当前模型一致；
4. 标记为当前最新版本；
5. 检查是否还有未生成的结构变化。

```powershell
Copy-Item .\data\videocenter.db .\data\videocenter.backup.db
uv run alembic stamp head
uv run alembic check
uv run alembic current
```

`stamp` 只写入版本标记，不会创建、删除或修改业务表。仅当现有数据库结构确实与初始迁移一致时才能使用。

本次迭代已先在数据库副本上执行 `stamp head` 和 `alembic check`，确认无结构差异后，才为当前本地数据库写入版本标记。

## 回退

初始迁移可以回退到空结构：

```powershell
uv run alembic downgrade base
```

该操作会删除四张业务表及其数据，只能用于空测试数据库或明确允许清空的环境。生产数据库禁止直接执行。

## 验证结果

本次迁移已完成以下验证：

- 在空 SQLite 数据库执行 `upgrade head` 成功；
- 四张业务表、版本表、索引和约束均成功创建；
- `alembic check` 未发现模型差异；
- 执行 `downgrade base` 成功；
- 降级后重新执行 `upgrade head` 成功；
- 已有数据库副本执行 `stamp head` 后结构检查通过；
- 当前本地数据库已接入版本 `81fd73d3a90a`。

## 后续模型变更

从该版本开始，每次修改数据库模型都需要创建新的迁移：

```powershell
uv run alembic revision --autogenerate -m "描述数据库变更"
uv run alembic upgrade head
uv run alembic check
```

模型修改和对应迁移文件应在同一次代码提交中完成。
