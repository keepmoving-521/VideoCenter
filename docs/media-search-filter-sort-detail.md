# L02-L08：影视搜索、筛选、排序和详情

影视列表接口支持组合搜索、筛选和排序；影视详情接口返回完整关联数据。

## 列表查询

```http
GET /api/v1/media
```

新增参数：

| 参数 | 说明 |
| --- | --- |
| `query` | 模糊匹配标题、排序标题、原始标题和影视别名 |
| `media_type` | 按影片类型筛选 |
| `release_year` | 按上映年份筛选，范围 1888～2100 |
| `status` | 按资源状态筛选 |
| `source_site` | 按来源网站筛选，不区分英文字母大小写 |
| `sort_by` | 排序字段 |
| `sort_order` | `asc` 或 `desc` |

所有条件可以与分页、收藏状态组合使用。

## 支持的排序字段

- `created_at`
- `updated_at`
- `title`
- `release_year`
- `rating`
- `personal_rating`

默认按照 `created_at desc` 排序。同值时使用影视 ID 倒序作为稳定的第二排序条件；空值排在非空值之后。

## 影视详情

```http
GET /api/v1/media/{media_id}
```

详情响应除全部影视字段外，还包含：

- `resources`：本地资源；
- `tags`：影视标签；
- `seasons`：电视剧季；
- `seasons[].episodes`：该季全部分集。

不存在的影视资源继续返回错误代码 `MEDIA_NOT_FOUND`。

本次迭代不修改数据库结构，不需要新增 Alembic 迁移。
