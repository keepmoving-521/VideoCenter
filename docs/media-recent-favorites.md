# L17～L18：最近添加与收藏影视列表

## 最近添加列表

```http
GET /api/v1/media/recent?page=1&page_size=50
```

列表按照 `created_at` 创建时间倒序排列；创建时间相同时按照影视 ID 倒序排列。

## 收藏影视列表

```http
GET /api/v1/media/favorites?page=1&page_size=50
```

接口只返回 `is_favorite=true` 的影视条目，并按照创建时间倒序排列。
收藏和取消收藏仍使用：

```http
PUT /api/v1/media/{media_id}/favorite
DELETE /api/v1/media/{media_id}/favorite
```

## 分页规则

两个接口统一返回 `MediaPage` 分页结构：

- `page` 默认值为 `1`，必须大于等于 `1`。
- `page_size` 默认值为 `50`，允许范围为 `1～200`。
- 响应包含 `items`、`total`、`total_pages`、`has_next` 和
  `has_previous`。

本次迭代没有修改数据库结构，不需要新增 Alembic 迁移。
