# P03～P05：视频缓存、文件丢失检测与播放详情

本次迭代完善在线播放资源的缓存协商、失效检测和播放器初始化信息。

## 视频缓存响应头

GET 和 HEAD 视频响应包含：

```http
Cache-Control: private, max-age=3600, no-transform
ETag: "..."
Last-Modified: ...
```

- `private`：私人媒体不允许共享缓存；
- `max-age=3600`：客户端可以缓存一小时；
- `no-transform`：中间代理不得擅自转码或修改视频。

支持条件请求：

```http
If-None-Match: "..."
If-Modified-Since: ...
```

文件未变化时返回 `304 Not Modified`，不返回视频正文。Range 请求仍优先返回实际的
`206 Partial Content`，避免播放器分段请求被错误转换为 304。

## 播放时文件丢失检测

GET、HEAD 或播放详情访问时都会检查磁盘文件：

- 文件不存在时将本地资源标记为不可用；
- 写入资源缺失时间；
- 重新计算所属影视条目状态；
- 实际播放请求返回 `VIDEO_FILE_MISSING`。

## 播放资源详情

```http
GET /api/v1/stream/{resource_id}/details
```

返回内容包括：

- 完整本地资源技术信息；
- 当前是否可播放以及文件是否存在；
- GET 播放地址和 HEAD 地址；
- 封面与预览缩略图 API 地址；
- 是否支持 Range；
- 当前缓存策略。

详情接口不暴露磁盘绝对路径。文件已丢失时仍返回资源记录，但 `playable` 和
`file_exists` 均为 `false`，便于前端展示失效状态。

本次功能不涉及数据库迁移。
