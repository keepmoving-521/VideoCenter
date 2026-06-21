# P10～P12：音轨、视频清晰度与浏览器格式兼容性

播放器可以在开始播放前查询音轨、清晰度和浏览器直接播放建议。

## 音轨信息

```http
GET /api/v1/stream/{resource_id}/audio-tracks
```

返回完整音轨列表，包括：

- FFprobe 流索引；
- 编码格式；
- 语言和标题；
- 声道数量与布局；
- 默认音轨；
- 默认音轨的流索引。

## 视频清晰度

```http
GET /api/v1/stream/{resource_id}/quality
```

返回：

- 清晰度标签，例如 `720p`、`1080p`、`1440p`、`4K`、`8K`；
- 视频宽度和高度；
- 化简后的宽高比；
- 总像素数；
- 视频码率和编码格式。

## 浏览器格式兼容性

```http
GET /api/v1/stream/{resource_id}/compatibility
User-Agent: ...
```

服务端根据文件容器、视频编码、音频编码和 User-Agent 返回：

- 浏览器类型；
- `supported`、`unsupported` 或 `unknown`；
- 是否建议直接播放；
- 类似 `canPlayType()` 的 `probably`、`maybe` 或空值；
- 判断原因；
- 建议动作：直接播放、客户端探测或转码。

判断采用保守策略：

- MP4/H.264/AAC 视为广泛支持；
- WebM/VP8 或 VP9/Opus 在 Chromium、Edge、Firefox 中视为支持；
- MKV、AVI、TS 等容器视为不适合浏览器直接播放；
- HEVC、AV1 返回 `unknown`，因为实际支持依赖浏览器版本、操作系统和硬件。

该接口是服务端预判，前端仍应使用浏览器 `canPlayType()` 或 MediaCapabilities API
进行最终确认。

播放详情接口会同时返回三个接口的 URL。本次功能不涉及数据库迁移。
