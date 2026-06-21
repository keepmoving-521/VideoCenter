# H05～H07：观看完成状态与手动标记

系统会持久化影片是否看完，并支持用户手动修正观看状态。

## 自动判断看完

播放器保存进度时，如果播放位置达到总时长的 `95%`，系统自动设置：

- `is_completed = true`；
- `completed_at` 为首次判断完成的时间。

选择 95% 是为了避免片尾字幕未完整播放导致影片一直停留在继续观看列表。影片一旦标记
完成，之后重新播放并保存较小位置不会自动取消完成状态。

观看记录和观看列表响应均增加：

- `is_completed`：是否看完；
- `completed_at`：首次完成时间。

继续观看列表现在直接排除 `is_completed = true` 的记录。

## 手动标记已看完

```http
PUT /api/v1/history/{media_id}/completed
```

系统优先使用观看记录或本地资源中的视频时长，将播放位置移动到结尾；没有视频时长时也会
强制标记完成。影片尚无观看记录时会自动创建记录。

## 手动标记未观看

```http
PUT /api/v1/history/{media_id}/unwatched
```

该操作删除影片的观看记录，使影片退出继续观看和最近观看列表。接口是幂等的：影片存在时，
即使没有观看记录也返回 `204 No Content`。

## 数据库迁移

本次新增迁移 `62c84ba172e1`，为 `watch_history` 增加：

- `is_completed`；
- `completed_at`。

升级时会将已有且播放进度达到 95% 的记录回填为已完成。

```powershell
uv run alembic upgrade head
```
