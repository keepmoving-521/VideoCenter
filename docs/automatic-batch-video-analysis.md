# A12～A13：下载自动分析与已有视频批量分析

系统将视频技术信息、音轨字幕和视觉资源生成整合为统一的本地资源分析流程。

## 下载完成后自动分析

下载器成功写入文件并登记本地资源时，会自动执行：

- FFprobe 视频、音频和字幕流分析；
- 视频封面生成；
- 三张预览缩略图生成。

分析失败不会把已经成功的下载任务改为失败。对应字段保持为空或标记生成失败，
后续可以通过批量分析接口重新执行。

## 批量分析已有视频

```http
POST /api/v1/local-resources/batch-analyze
Content-Type: application/json

{
  "resource_ids": [1, 2, 3],
  "force": false
}
```

- 单次最多处理 100 个本地资源；
- 重复 ID 自动去重；
- `force=false` 时跳过已经完成分析和视觉资源生成尝试的文件；
- `force=true` 时强制重新执行 FFprobe 和 FFmpeg；
- 文件不存在和数据库记录不存在统一返回在 `missing_resource_ids`；
- 单个文件发生异常时记录到 `failures`，不影响其他文件。

响应区分：

- `analyzed_resource_ids`
- `skipped_resource_ids`
- `missing_resource_ids`
- `failures`

批量分析、目录扫描和下载完成登记共用同一分析服务，因此生成字段和失败降级规则一致。

本次功能复用已有本地资源字段，不需要新增数据库迁移。
