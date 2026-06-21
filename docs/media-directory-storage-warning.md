# F19～F20：磁盘空间统计与媒体目录容量预警

本次迭代为每个媒体目录增加磁盘容量统计和独立预警阈值。

## 容量配置

创建或更新媒体目录时可以设置：

```json
{
  "capacity_warning_enabled": true,
  "capacity_warning_threshold_percent": 90
}
```

- `capacity_warning_enabled`：是否启用容量预警，默认启用。
- `capacity_warning_threshold_percent`：磁盘使用率阈值，范围为 `1～100`，默认 `90`。

预警依据媒体目录所在磁盘卷的实际使用率判断。达到或超过阈值时，
统计结果中的 `warning_triggered` 为 `true`。

## 查询单个目录容量

```http
GET /api/v1/media-directories/{directory_id}/storage
```

返回内容包括：

- 磁盘总容量、已用容量和可用容量；
- 磁盘使用率；
- 系统在该目录下登记的可用文件数量与文件体积；
- 预警开关、阈值和当前预警状态。

## 查询全部目录容量

```http
GET /api/v1/media-directories/storage
```

结果顺序与媒体目录列表一致，默认目录排在最前面。

多个媒体目录位于同一个磁盘卷时，它们的磁盘总量、已用量和可用量相同，
但系统登记的文件数量、文件体积和预警阈值可以不同。

本次迭代只提供预警状态，不会自动暂停或拒绝下载任务。

## 数据库升级

```powershell
uv run alembic upgrade head
```

迁移会为已有目录启用预警，并将默认阈值设置为 `90%`。
