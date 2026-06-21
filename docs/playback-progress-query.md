# H02：查询单个影片播放进度

系统支持按影视条目查询其最新播放进度，播放器可在打开影片时恢复到上次观看位置。

## 接口

```http
GET /api/v1/history/{media_id}
```

成功响应示例：

```json
{
  "id": 12,
  "media_id": 8,
  "resource_id": 21,
  "position_seconds": 356.5,
  "duration_seconds": 5400,
  "watched_at": "2026-06-21T20:30:00"
}
```

- `position_seconds`：上次保存的播放位置，单位为秒。
- `duration_seconds`：保存进度时已知的视频总时长。
- `resource_id`：上次播放的本地资源，可用于恢复到同一个视频文件。
- `watched_at`：最近一次保存进度的时间。

## 错误处理

- 影视条目不存在：返回 `404 MEDIA_NOT_FOUND`。
- 影视条目存在但没有播放记录：返回 `404 WATCH_HISTORY_NOT_FOUND`。客户端可以将后一种
  情况视为从头播放。
- 非正整数影片编号：返回统一参数校验错误。

## 数据库

本次迭代复用现有 `watch_history` 表，没有修改数据库结构，不需要新增 Alembic 迁移。
