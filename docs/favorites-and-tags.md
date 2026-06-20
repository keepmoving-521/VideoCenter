# L12-L13：收藏与标签管理

## 收藏和取消收藏

收藏影视：

```http
PUT /api/v1/media/{media_id}/favorite
```

取消收藏：

```http
DELETE /api/v1/media/{media_id}/favorite
```

响应：

```json
{
  "media_id": 1,
  "is_favorite": true
}
```

两个接口都是幂等的，重复收藏或重复取消不会报错。收藏列表仍可使用：

```http
GET /api/v1/media?is_favorite=true
```

## 标签管理

| 功能 | 接口 |
| --- | --- |
| 标签列表 | `GET /api/v1/tags` |
| 创建标签 | `POST /api/v1/tags` |
| 标签详情及关联数量 | `GET /api/v1/tags/{tag_id}` |
| 重命名标签 | `PATCH /api/v1/tags/{tag_id}` |
| 删除标签 | `DELETE /api/v1/tags/{tag_id}` |
| 替换影视全部标签 | `PUT /api/v1/media/{media_id}/tags` |
| 给影视增加一个标签 | `POST /api/v1/media/{media_id}/tags/{tag_id}` |
| 从影视移除一个标签 | `DELETE /api/v1/media/{media_id}/tags/{tag_id}` |

标签名称按大小写无关方式保持唯一。重复名称返回错误代码 `TAG_ALREADY_EXISTS`。

给影视增加已有标签、从影视移除不存在的关联均按幂等操作处理。删除标签会清理它与所有影视的关联，但不会删除影视资源。

本次迭代不修改数据库结构，不需要新增 Alembic 迁移。
