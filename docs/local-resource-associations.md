# F12～F13：本地文件手动与批量关联

本次迭代支持将扫描或下载登记的本地文件关联到影视条目，也支持批量处理多个文件。
关联发生变化后，系统会同步更新新旧影视条目的资源状态。

## 单个文件关联

```http
PUT /api/v1/local-resources/{resource_id}/association
Content-Type: application/json

{
  "media_id": 12
}
```

接口返回更新后的本地资源。重新提交其他 `media_id` 可以改绑到其他影视条目。

解除关联时传入：

```json
{
  "media_id": null
}
```

## 批量关联

```http
POST /api/v1/local-resources/batch-associate
Content-Type: application/json

{
  "resource_ids": [1, 2, 3],
  "media_id": 12
}
```

- 单次最多处理 100 个本地资源。
- 重复 ID 会自动去重，并保持首次出现顺序。
- 不存在的本地资源通过 `missing_resource_ids` 返回，不影响其他有效资源。
- 目标影视条目不存在时不会修改任何关联。
- 批量解除关联同样将 `media_id` 设置为 `null`。

本次功能复用现有 `local_resources.media_id` 字段，不需要新增数据库迁移。
