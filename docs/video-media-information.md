# A03～A06：视频媒体信息获取

系统通过 FFprobe 自动读取本地视频的技术信息。

## 获取内容

- `duration_seconds`：视频时长，单位为秒；
- `video_width`：视频宽度，单位为像素；
- `video_height`：视频高度，单位为像素；
- `video_codec`：首个视频流的编码格式，例如 `h264`、`hevc`、`av1`；
- `bitrate`：视频流码率，视频流未提供时使用容器总码率，单位为 bit/s。

## 执行时机

- 扫描发现新文件时自动分析；
- 文件大小或修改时间变化时重新分析；
- 升级前的旧资源在下一次增量扫描时补充信息；
- 下载完成登记本地资源时自动分析。

文件未变化且已经尝试过分析时，增量扫描不会重复调用 FFprobe。

FFprobe 未安装、超时、文件损坏或返回内容无效时，不会导致扫描或下载任务失败。
对应媒体信息保持为空，文件内容变化后系统会再次尝试。

## 查看结果

```http
GET /api/v1/local-resources
```

本地资源响应中会包含上述媒体信息字段。

## 数据库升级

```powershell
uv run alembic upgrade head
```

FFprobe 检测及自定义路径配置参阅
[FFmpeg/FFprobe 检测与路径配置](ffmpeg-detection-configuration.md)。
