# H08～H09：最近观看分集与下一集推荐

系统可以记录电视剧最近观看到的分集，并根据季号、集号自动推荐目录中的下一集。

## 记录最近观看分集

保存播放进度时可显式提供分集编号：

```http
PUT /api/v1/stream/{resource_id}/progress
Content-Type: application/json

{
  "episode_id": 35,
  "position_seconds": 120,
  "duration_seconds": 2700
}
```

如果未提供 `episode_id`，系统会尝试使用本地资源识别出的
`parsed_season_number` 和 `parsed_episode_number` 自动匹配分集。分集必须属于资源关联的
同一影视条目。

查询最近观看分集：

```http
GET /api/v1/history/{media_id}/recent-episode
```

响应包含季号、集号、标题、播放进度、最近资源和播放地址。

## 推荐下一集

```http
GET /api/v1/history/{media_id}/next-episode
```

推荐规则：

- 优先选择当前季中集号更大的第一集；
- 当前季结束后，选择后续季中最早的一集；
- 只根据已建立的季和分集目录推荐，不凭空推测缺失集数；
- 如果找到匹配季号和集号的可用本地资源，同时返回 `resource_id`、`stream_url` 和
  `playable = true`；
- 目录中存在下一集但本地尚无资源时仍返回分集资料，并设置 `playable = false`。

没有最近观看分集时返回 `RECENT_EPISODE_NOT_FOUND`，已经观看到目录最后一集时返回
`NEXT_EPISODE_NOT_FOUND`。

## 数据库迁移

迁移 `341af49d67c8` 为 `watch_history` 增加可空的 `episode_id` 外键。升级数据库：

```powershell
uv run alembic upgrade head
```
