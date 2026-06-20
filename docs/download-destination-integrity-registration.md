# D16～D19：目标目录、完整性校验、临时文件清理与资源登记

## 目标目录选择

创建下载任务时可以传入 `target_directory`：

```json
{
  "source_url": "https://example.com/movie.mp4",
  "target_directory": "movies/action"
}
```

相对路径以 `VIDEOCENTER_MEDIA_ROOT` 为根目录。也允许传入媒体根目录内部的绝对路径。
解析后的路径必须位于媒体根目录内，`../` 等越界路径会被拒绝。

数据库保存的是相对于媒体根目录的标准 `/` 分隔路径，根目录本身保存为空字符串。

## 文件完整性检查

系统执行两层检查：

1. HTTP 响应存在 `Content-Length` 时，实际下载字节数必须完全一致。
2. 请求提供 `expected_sha256` 时，下载内容的 SHA-256 必须一致。

```json
{
  "source_url": "https://example.com/movie.mp4",
  "expected_sha256": "64位十六进制摘要"
}
```

下载器始终计算 SHA-256。成功后实际摘要写入 `checksum_sha256`；预期摘要保存于
`expected_sha256`。

## 失败临时文件清理

下载数据先写入同目录下的 `文件名.part`。以下情况都会删除临时文件：

- 网络或文件写入错误；
- 响应长度不一致；
- SHA-256 校验失败；
- 下载取消；
- 任务层捕获到其他失败。

只有完整性检查通过后，临时文件才会移动为最终文件。

## 自动登记本地资源

下载完成后系统自动按最终绝对路径登记 `LocalResource`，包含：

- 关联影视 ID；
- 文件名和绝对路径；
- 文件大小；
- MIME 类型。

登记操作是幂等的：相同路径已经存在记录时更新原记录，不重复插入。

## 数据迁移

迁移 `8651d026e704` 新增：

- `target_directory`
- `expected_sha256`
- `checksum_sha256`

执行：

```powershell
uv run alembic upgrade head
```
