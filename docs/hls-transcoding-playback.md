# P13～P15：HLS 转码任务、播放列表与分片

系统可以将浏览器不适合直接播放的本地视频后台转码为 HLS VOD。

## 创建 HLS 转码任务

```http
POST /api/v1/stream/{resource_id}/hls
```

接口返回 `202 Accepted`。任务状态包括：

- `waiting`
- `running`
- `completed`
- `failed`

同一资源已有等待、运行或有效完成任务时会直接复用，避免重复转码。

查询任务：

```http
GET /api/v1/stream/hls-tasks/{task_id}
```

任务完成后响应包含 `playlist_url`。

实时进度、并发限制和缓存清理详见
[HLS 转码进度、并发限制与缓存清理](hls-progress-concurrency-cache.md)。

## 转码格式

- 视频：H.264；
- 音频：AAC 128 kbps；
- 分片长度：约 6 秒；
- 播放列表类型：VOD；
- 分片容器：MPEG-TS。

转码文件存放在：

```text
data/media/.videocenter-cache/hls/
```

媒体扫描不会收录缓存目录。

## HLS 播放列表

```http
GET /api/v1/stream/hls/{task_id}/index.m3u8
```

播放列表只有任务完成后可访问，MIME 类型为
`application/vnd.apple.mpegurl`。

## HLS 分片

```http
GET /api/v1/stream/hls/{task_id}/segments/{segment_name}
```

只允许访问对应任务缓存目录内的 `.ts` 分片，禁止目录穿越。

## 重启恢复

应用启动时会恢复等待中或运行中的 HLS 任务。重新执行时会清理该任务对应的旧输出目录，
避免新旧分片混合。

## 数据库升级

```powershell
uv run alembic upgrade head
```
