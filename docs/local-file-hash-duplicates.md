# F14～F15：文件哈希与重复文件检测

本次迭代使用 SHA-256 为本地视频生成内容指纹，并根据相同指纹识别重复文件。

## 哈希计算

- 新增或内容发生变化的扫描文件会分块计算 SHA-256。
- 增量扫描遇到未变化且已有哈希的文件时不会重复计算。
- 升级前的资源会在下一次扫描时补充哈希。
- 下载器已经计算过的 SHA-256 会在下载登记时直接复用。

哈希保存在 `local_resources.checksum_sha256` 字段。

## 查询重复文件

```http
GET /api/v1/local-resources/duplicates
```

响应包含：

- `group_count`：重复组数量。
- `duplicate_file_count`：重复组内的文件总数。
- `reclaimable_bytes`：每组保留一个文件后理论可释放的空间。
- `groups`：按 SHA-256 分组的本地资源。

仅当前可用且已经计算哈希的资源参与检测。接口只检测和报告重复文件，不会自动删除。

## 数据库升级

```powershell
uv run alembic upgrade head
```
