# P06～P09：字幕列表、外挂字幕访问与 WebVTT 转换

播放器可以查询视频的内嵌字幕与同目录外挂字幕，并以浏览器支持的 WebVTT 格式读取外挂字幕。

## 字幕列表

```http
GET /api/v1/stream/{resource_id}/subtitles
```

响应同时包含：

- `embedded`：FFprobe 检测到的视频容器内字幕；
- `external`：与视频同目录、文件名匹配的外挂字幕。

外挂字幕文件名需要与视频主文件名一致或以其开头，例如：

```text
movie.mp4
movie.srt
movie.zh-CN.srt
movie.en.vtt
```

支持发现 `.vtt`、`.srt`、`.ass` 和 `.ssa`。

## 外挂字幕访问

字幕列表中的外挂字幕包含受控的 `access_url`：

```http
GET /api/v1/stream/{resource_id}/subtitles/{subtitle_id}?format=webvtt
```

字幕 ID 不能用于读取其他目录或不属于该视频的文件。

获取原始文件：

```http
GET /api/v1/stream/{resource_id}/subtitles/{subtitle_id}?format=original
```

## WebVTT 转换

- `.vtt` 直接返回；
- `.srt` 由系统转换时间轴并添加 `WEBVTT` 文件头；
- `.ass` 和 `.ssa` 使用 FFmpeg 转换；
- 转换结果缓存在 `.videocenter-cache/subtitles/`；
- 原字幕修改后会自动重新转换。

转换失败返回 `SUBTITLE_CONVERSION_FAILED`，不会影响视频播放。

内嵌字幕当前仅提供轨道信息，不提供独立访问 URL；后续可以增加从容器提取字幕的任务。

本次功能不涉及数据库迁移。
