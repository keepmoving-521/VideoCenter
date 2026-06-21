# D23：yt-dlp 下载器

系统现在支持通过 yt-dlp 下载视频网站页面、HLS/DASH 流媒体及其他 yt-dlp 支持的
资源。

## 依赖安装

yt-dlp 已加入项目运行依赖。更新代码后执行：

```powershell
uv sync --extra dev
```

使用 pip 时：

```powershell
python -m pip install -r requirements-dev.txt
```

下载分离的视频和音频流并进行合并时，还需要系统安装 FFmpeg，并确保 `ffmpeg`
命令位于 `PATH`。

## 创建任务

`POST /api/v1/downloads` 新增可选字段 `downloader`：

```json
{
  "source_url": "https://example.com/watch/123",
  "downloader": "yt-dlp"
}
```

允许值：

| 值 | 说明 |
| --- | --- |
| `auto` | 自动选择，默认值 |
| `http-direct` | 强制使用 HTTP 直链下载器 |
| `yt-dlp` | 强制使用 yt-dlp |

自动选择规则：

- URL 以常见音视频扩展名结尾时使用 `http-direct`。
- 普通网页、HLS 清单等其他地址使用 `yt-dlp`。

实际选中的实现保存到任务的 `downloader_name` 字段，应用重启或失败重试后仍使用
同一个下载器。旧任务的 `auto` 会在首次执行时重新选择并保存。

## 实现行为

- 使用 yt-dlp 官方 Python API，不解析命令行输出。
- 使用 `progress_hooks` 接入现有实时进度、速度和剩余时间。
- 默认只下载单个视频，不展开播放列表。
- 默认格式为 `bestvideo*+bestaudio/best`。
- 支持暂停、恢复、取消和任务队列。
- 下载完成后计算 SHA-256，并执行可选的预期摘要校验。
- 成功后继续使用现有本地资源登记和影片状态更新流程。
- 失败或取消时清理 yt-dlp 的 `.part`、`.ytdl` 临时文件。

## 数据迁移

迁移 `a02de5d1fc76` 新增 `downloader_name`：

```powershell
uv run alembic upgrade head
```
