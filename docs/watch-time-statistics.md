# H13～H14：累计观看时长与每日统计

系统会记录播放器实际观看时长，并提供累计概览和每日趋势数据。

## 上报实际观看时长

播放进度接口增加可选字段 `watched_seconds`：

```http
PUT /api/v1/stream/{resource_id}/progress
Content-Type: application/json

{
  "position_seconds": 620,
  "duration_seconds": 5400,
  "watched_seconds": 20
}
```

`watched_seconds` 表示自上次上报后实际播放的秒数，建议播放器每 15～30 秒上报一次。该值
不会因快进或拖动进度条而虚增。未提供时，系统使用本次位置减去上次位置的正向差值兼容旧
客户端；倒退播放位置不会产生负数统计。

单次上报最多记录 86400 秒。

## 累计观看统计

```http
GET /api/v1/history/stats/summary
```

返回累计秒数、分钟、小时、观看影片数、活跃天数、日均观看秒数和看完次数。

## 每日观看统计

```http
GET /api/v1/history/stats/daily?start_date=2026-06-01&end_date=2026-06-22
```

- 未提供日期时默认返回截至今天的最近 30 天；
- 最大查询跨度为 366 天；
- 返回连续日期，没有观看活动的日期自动补零；
- 每日数据包含观看秒数、分钟、观看影片数和看完次数。

## 删除语义

单条删除、批量删除、标记未观看和清空观看历史时，会同步删除相应观看统计。

## 数据库迁移

迁移 `9d4c7a21b6e0` 新增 `watch_daily_stats` 表，按日期和影片保存聚合数据：

```powershell
uv run alembic upgrade head
```
