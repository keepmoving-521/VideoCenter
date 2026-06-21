# H01：保存视频播放进度

播放器可按本地视频资源保存当前播放位置。系统会自动找到资源关联的影视条目，并为每个
影视条目维护一条最新观看记录。

## 接口

```http
PUT /api/v1/stream/{resource_id}/progress
Content-Type: application/json

{
  "position_seconds": 356.5,
  "duration_seconds": 5400
}
```

- `position_seconds`：必填，当前播放位置，单位为秒。
- `duration_seconds`：可选，播放器获取到的视频总时长。未提供时优先使用本地资源经
  FFprobe 分析得到的时长。
- 同一影视条目重复上报时更新原记录，不会生成多条重复历史。
- 播放位置不能大于已知总时长。

成功响应包含观看记录编号、影视条目编号、本地资源编号、播放位置、总时长和最后观看时间。
播放详情 `GET /api/v1/stream/{resource_id}/details` 同时返回 `progress_url`，前端无需自行
拼接上报地址。

## 错误处理

- 本地资源不存在：`LOCAL_RESOURCE_NOT_FOUND`。
- 本地资源尚未关联影视条目：`RESOURCE_NOT_ASSOCIATED`。
- 播放位置超过资源总时长：`PLAYBACK_POSITION_EXCEEDS_DURATION`。
- 请求中同时提供播放位置和总时长且位置超出总时长：统一参数校验错误。

## 数据库

本次迭代复用现有 `watch_history` 表，没有修改数据库结构，不需要新增 Alembic 迁移。
