# P16～P18：HLS 转码进度、并发限制与缓存清理

HLS 转码任务支持真实进度更新、固定并发工作队列和安全缓存清理。

## 转码进度

查询任务：

```http
GET /api/v1/stream/hls-tasks/{task_id}
```

系统读取 FFmpeg `-progress` 输出，并根据视频时长计算 `progress`。
转码过程中最高显示为 `99%`，只有播放列表成功生成后才更新为 `100%` 和 `completed`。

任务响应同时返回：

- `cache_available`：播放列表是否仍存在；
- `playlist_url`：仅任务完成且缓存可用时返回。

## 并发限制

通过环境变量配置 HLS 转码工作线程：

```dotenv
VIDEOCENTER_HLS_WORKER_COUNT=1
```

允许范围为 `1～8`，默认只同时执行一个转码任务。超出并发数量的任务保持
`waiting`，由固定工作队列依次处理。

## 缓存保留时间

默认缓存保留 168 小时：

```dotenv
VIDEOCENTER_HLS_CACHE_RETENTION_HOURS=168
```

手动清理接口：

```http
POST /api/v1/stream/hls/cache/cleanup
Content-Type: application/json

{
  "max_age_hours": 24
}
```

省略 `max_age_hours` 时使用环境配置。清理规则：

- 只处理已完成或失败的任务；
- 任务完成时间必须超过保留时间；
- 不清理等待中或运行中的任务；
- 删除播放列表和分片目录；
- 保留任务历史，但清空缓存路径；
- 返回清理任务数、目录数和释放字节数。

缓存被清理后，再次为该资源创建 HLS 时会生成新任务。

本次功能复用已有 HLS 任务表，不需要新增数据库迁移。
