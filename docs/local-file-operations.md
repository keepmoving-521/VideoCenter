# F16～F18：文件重命名、安全删除与失效资源清理

本次迭代增加受媒体根目录保护的本地文件操作。

## 文件重命名

```http
PUT /api/v1/local-resources/{resource_id}/rename
Content-Type: application/json

{
  "file_name": "新的影片名称.2024.mp4"
}
```

- 只允许修改文件名，不能传入目录路径。
- 目标文件必须仍在原目录和媒体根目录内。
- 不覆盖已经存在的文件。
- 仅允许系统支持的视频扩展名。
- 重命名后重新解析标题、年份、影片类型和季集编号，文件哈希保持不变。

## 本地文件安全删除

```http
DELETE /api/v1/local-resources/{resource_id}/file
```

文件不会永久删除，而是移动到：

```text
data/media/.videocenter-trash/YYYYMMDD/
```

资源记录会标记为不可用，并同步更新影视条目状态。媒体扫描会忽略回收站目录，
避免被删除的文件重新登记。

## 清理失效资源

```http
POST /api/v1/local-resources/cleanup-invalid
```

该操作只清理同时满足以下条件的数据库记录：

- 已标记为不可用；
- 原始文件路径在磁盘上确实不存在。

关联的播放历史会保留，但其中的本地资源引用会被解除。磁盘上仍存在的文件不会被清理。
回收站中的实体文件也不会被此接口永久删除。
