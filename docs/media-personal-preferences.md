# M14-M15：收藏状态、个人评分和备注

本次迭代为私人影视库增加个人偏好数据，并与影片自身的公共元数据分开保存。

## 字段

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `is_favorite` | 布尔值 | 是否收藏，默认 `false` |
| `personal_rating` | 浮点数或空值 | 个人评分，范围为 0～10 |
| `personal_notes` | 文本或空值 | 个人备注，最长 10000 字 |

原有 `rating` 表示影片来源站点或公共评分，`personal_rating` 只表示当前用户的个人评分。

个人备注会自动去除首尾空白；提交纯空白字符串会保存为空值。个人评分和备注均可通过提交 `null` 清空。

## API 用法

创建或更新影片时可直接提交：

```json
{
  "is_favorite": true,
  "personal_rating": 9.5,
  "personal_notes": "周末适合重温"
}
```

只查询收藏影片：

```http
GET /api/v1/media?is_favorite=true
```

取消收藏并清空个人信息：

```json
{
  "is_favorite": false,
  "personal_rating": null,
  "personal_notes": null
}
```

数据库升级使用：

```powershell
uv run alembic upgrade head
```

对应迁移版本为 `2e9d613cec84`，上一版本为 `3e5fa1d03c30`。
