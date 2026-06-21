# H10～H12：删除观看历史

系统支持删除单个、批量和全部观看历史。删除观看历史只影响播放位置、观看完成状态和最近
观看分集，不会删除影视条目、本地视频、季或分集目录。

## 删除单条历史

```http
DELETE /api/v1/history/{media_id}
```

成功返回 `204 No Content`。指定影片没有观看记录时返回
`404 WATCH_HISTORY_NOT_FOUND`。

## 批量删除

```http
POST /api/v1/history/batch-delete
Content-Type: application/json

{
  "media_ids": [12, 18, 25]
}
```

一次最多提交 100 个影片编号，重复编号会自动去重。响应示例：

```json
{
  "deleted_count": 2,
  "deleted_media_ids": [12, 18],
  "missing_media_ids": [25]
}
```

## 清空全部历史

```http
DELETE /api/v1/history/clear
```

响应包含实际删除数量：

```json
{
  "deleted_count": 36
}
```

清空接口是幂等的，没有观看历史时返回 `deleted_count: 0`。

## 数据库

本次迭代没有修改数据库结构，不需要新增 Alembic 迁移。
