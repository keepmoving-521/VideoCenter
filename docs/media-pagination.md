# L01：影视资源分页查询

影视资源列表接口现在返回分页结构，避免资源数量增长后一次加载全部数据。

## 接口

```http
GET /api/v1/media?page=1&page_size=50
```

查询参数：

| 参数 | 默认值 | 限制 | 说明 |
| --- | --- | --- | --- |
| `page` | `1` | 大于等于 1 | 页码 |
| `page_size` | `50` | 1～200 | 每页数量 |
| `query` | 空 | 1～100 字符 | 标题搜索 |
| `is_favorite` | 空 | 布尔值 | 收藏状态筛选 |

更多标题搜索、类型、年份、状态、来源筛选和排序参数参见
[L02-L08 影视搜索筛选排序与详情](media-search-filter-sort-detail.md)。

## 响应结构

```json
{
  "items": [],
  "total": 125,
  "page": 2,
  "page_size": 50,
  "total_pages": 3,
  "has_next": true,
  "has_previous": true
}
```

- `items`：当前页影视资源；
- `total`：应用全部筛选条件后的总数；
- `total_pages`：总页数；无数据时为 0；
- `has_next`：是否存在下一页；
- `has_previous`：是否存在上一页。

列表按照影视 ID 倒序排列，最新创建的资源优先。请求超过最后一页时返回空 `items`，同时保留真实的总数和总页数。

本次迭代修改了列表 API 响应格式，但没有修改数据库结构，不需要新增 Alembic 迁移。
