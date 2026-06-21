# A10～A11：视频封面与预览缩略图生成

系统使用 FFmpeg 为本地视频自动生成一张封面和三张预览缩略图。

## 生成规则

- 封面取视频约 `10%` 的时间点，宽度为 1280 像素；
- 预览图分别取约 `25%`、`50%`、`75%` 的时间点，宽度为 480 像素；
- 保持原始宽高比，输出 JPEG；
- 时长未知时使用 1 秒、5 秒和 10 秒等安全默认时间点；
- 文件以 SHA-256 命名，相同内容可以复用已经生成的图片。

生成文件保存在：

```text
data/media/.videocenter-cache/artwork/
```

媒体扫描会忽略 `.videocenter-cache`。图片先写入临时文件，成功后再原子替换正式文件。

## 执行时机

- 扫描新增或变化的视频文件时；
- 下载完成并登记本地资源时；
- 升级前的资源在下一次增量扫描时。

FFmpeg 不可用、超时或视频无法解码时，不会导致扫描或下载失败。
`visual_assets_generated` 会返回 `false`，图片路径保持为空。

## 本地资源字段

- `cover_image_path`
- `preview_thumbnail_paths`
- `visual_assets_generated`

## 图片读取接口

```http
GET /api/v1/local-resources/{resource_id}/cover
GET /api/v1/local-resources/{resource_id}/previews/{preview_index}
```

`preview_index` 从 `0` 开始。接口只允许读取系统媒体缓存目录内的图片。

## 数据库升级

```powershell
uv run alembic upgrade head
```
