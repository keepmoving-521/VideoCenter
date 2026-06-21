# D24～D27：清晰度、格式、字幕与封面

yt-dlp 下载任务现在支持选择视频清晰度和容器格式，并可同步下载字幕与封面。

## 请求参数

```json
{
  "source_url": "https://example.com/watch/123",
  "video_quality": "1080p",
  "video_format": "mkv",
  "download_subtitles": true,
  "subtitle_languages": ["zh-CN", "en"],
  "download_thumbnail": true
}
```

### 清晰度

`video_quality` 支持：

- `best`
- `2160p`
- `1440p`
- `1080p`
- `720p`
- `480p`
- `360p`

该值表示高度上限。例如 `1080p` 会优先选择不超过 1080 高度的最佳视频和音频。

### 视频格式

`video_format` 支持：

- `best`
- `mp4`
- `mkv`
- `webm`

系统优先选择目标容器已有的媒体流；无法直接匹配时，会退回最佳媒体流并让 yt-dlp
通过 FFmpeg 合并到目标容器。

### 字幕

- `download_subtitles=true` 下载可用的人工字幕。
- `subtitle_languages` 指定语言代码，例如 `zh-CN`、`en`。
- 语言列表为空时请求全部可用人工字幕。
- 只要提供了语言列表，系统会自动启用字幕下载。
- 字幕作为视频同目录下的旁车文件保存，不嵌入视频。

### 封面

`download_thumbnail=true` 会下载站点提供的封面，并作为视频同目录下的旁车图片保存。

## 下载器选择

在 `downloader=auto` 模式下，只要指定了清晰度、格式、字幕或封面选项，即使源地址
看起来是普通直链，也会自动使用 yt-dlp。

HTTP 直链下载器不会转码，也不会提取字幕或封面。

## FFmpeg

选择特定容器或下载分离的视频/音频流时通常需要 FFmpeg。请确保 `ffmpeg` 命令位于
系统 `PATH`。

## 数据迁移

迁移 `df3d06a94df5` 新增媒体选择字段：

```powershell
uv run alembic upgrade head
```
