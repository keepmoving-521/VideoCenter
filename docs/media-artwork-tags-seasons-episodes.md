# M09-M12：海报、标签、电视剧季与分集

本次迭代补齐影视目录的展示素材和电视剧层级结构。

## 数据模型

- `media.poster_url`：影视海报地址，沿用已有字段。
- `media.background_url`：详情页背景图地址。
- `tags`：可复用的影视标签；标签名称按大小写无关方式保持唯一。
- `media_tags`：影视与标签的多对多关联表。
- `seasons`：电视剧季；同一影视条目内季号唯一，`0` 可表示特别篇。
- `episodes`：电视剧分集；同一季内集号唯一，集号从 `1` 开始。

删除影视条目时，其季和分集会随之删除；删除季时，其分集也会删除。

## API

| 功能 | 接口 |
| --- | --- |
| 查询、创建标签 | `GET/POST /api/v1/tags` |
| 删除标签 | `DELETE /api/v1/tags/{tag_id}` |
| 替换影视标签 | `PUT /api/v1/media/{media_id}/tags` |
| 查询、创建季 | `GET/POST /api/v1/media/{media_id}/seasons` |
| 更新、删除季 | `PATCH/DELETE /api/v1/seasons/{season_id}` |
| 查询、创建分集 | `GET/POST /api/v1/seasons/{season_id}/episodes` |
| 更新、删除分集 | `PATCH/DELETE /api/v1/episodes/{episode_id}` |

只有 `media_type=series` 的影视条目允许创建季。影视详情和列表响应会返回 `tags`，海报与背景图分别通过 `poster_url` 和 `background_url` 返回。

## 数据库升级

```powershell
# uv
uv run alembic upgrade head

# pip 虚拟环境
python -m alembic upgrade head
```

对应迁移版本为 `3e5fa1d03c30`，上一版本为 `8bcdd86d27ba`。
