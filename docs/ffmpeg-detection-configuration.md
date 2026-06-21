# A01～A02：FFmpeg/FFprobe 检测与路径配置

系统可以检测 FFmpeg 和 FFprobe 是否可用，并返回实际可执行文件路径与版本。

## 自动检测

未配置路径时，系统会从操作系统的 `PATH` 中分别查找：

```text
ffmpeg
ffprobe
```

检测时只执行 `-version`，默认最长等待 5 秒。

## 手动配置路径

在 `.env` 或对应环境配置文件中设置：

```dotenv
VIDEOCENTER_FFMPEG_PATH=C:\ffmpeg\bin\ffmpeg.exe
VIDEOCENTER_FFPROBE_PATH=C:\ffmpeg\bin\ffprobe.exe
```

Linux 示例：

```dotenv
VIDEOCENTER_FFMPEG_PATH=/usr/local/bin/ffmpeg
VIDEOCENTER_FFPROBE_PATH=/usr/local/bin/ffprobe
```

配置路径优先于系统 `PATH`。路径不存在或程序无法运行时，应用仍然可以启动，
检测接口会返回具体错误。

修改配置后需要重新启动服务。

## 检测接口

```http
GET /api/v1/system/media-tools
```

顶层 `available` 仅在 FFmpeg 和 FFprobe 都可用时为 `true`。每个工具分别返回：

- `available`：是否可用；
- `configured_path`：用户配置的路径；
- `executable_path`：最终检测到的实际路径；
- `version`：版本号；
- `error`：不可用原因。

本次功能不涉及数据库结构，因此不需要执行数据库迁移。
