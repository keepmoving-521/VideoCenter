# D05～D07：实时下载进度、速度与剩余时间

下载任务现在会持久化字节级进度。客户端可以轮询现有接口获取实时数据：

```http
GET /api/v1/downloads/{task_id}
```

也可以通过任务列表查看全部任务：

```http
GET /api/v1/downloads
```

## 响应字段

| 字段 | 单位 | 说明 |
| --- | --- | --- |
| `progress` | 百分比 | 下载百分比，范围 `0～100` |
| `downloaded_bytes` | 字节 | 当前已写入临时文件的大小 |
| `total_bytes` | 字节 | 服务端提供的文件总大小，未知时为 `null` |
| `speed_bytes_per_second` | 字节/秒 | 从任务开始到当前的平均实时速度 |
| `remaining_seconds` | 秒 | 根据剩余字节和当前速度估算，未知时为 `null` |

响应示例：

```json
{
  "status": "downloading",
  "progress": 42.5,
  "downloaded_bytes": 44564480,
  "total_bytes": 104857600,
  "speed_bytes_per_second": 5242880.0,
  "remaining_seconds": 11.5
}
```

## 计算规则

- 下载器每写入一个分块便发送一次进度回调。
- 百分比为 `downloaded_bytes / total_bytes * 100`。
- 速度为任务开始后的累计平均速度。
- 剩余时间为 `(total_bytes - downloaded_bytes) / speed_bytes_per_second`。
- 百分比、速度和剩余时间保留两位小数。
- 如果服务器没有返回 `Content-Length`，系统仍提供已下载字节数和速度，但总大小、
  百分比及剩余时间无法估算。
- 任务完成后，进度为 `100`，剩余时间为 `0`。

前端通常可以每秒轮询一次；不建议按下载器内部每个分块的频率请求 API。

## 数据迁移

迁移 `b81d5ca75147` 新增进度指标字段和数据范围约束：

```powershell
uv run alembic upgrade head
```
