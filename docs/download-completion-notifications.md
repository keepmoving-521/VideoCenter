# D28：下载完成通知

下载任务成功完成、文件校验通过并登记本地资源后，系统会自动生成一条持久化站内
通知。用户离线或应用重启不会丢失通知。

## 通知接口

### 查询通知

```http
GET /api/v1/notifications?unread_only=false&limit=50
```

- `unread_only`：只返回未读通知。
- `limit`：返回数量，范围 `1～200`。
- 通知按照创建时间倒序排列。

### 查询未读数量

```http
GET /api/v1/notifications/unread-count
```

### 标记单条已读

```http
POST /api/v1/notifications/{notification_id}/read
```

该操作是幂等的，重复调用不会改变原来的已读时间。

### 全部标记已读

```http
POST /api/v1/notifications/read-all
```

响应中的 `updated_count` 表示本次更新的通知数量。

## 通知内容

下载完成通知包含：

- `notification_type=download_completed`
- 下载任务 ID
- 关联影视 ID
- 标题和消息
- 创建时间
- 已读时间

有关联影视时，消息使用影视标题；否则使用下载目标文件名。

每个下载任务最多生成一条通知。数据库唯一约束和业务层检查会共同防止重复完成回调
产生重复通知。

## 数据迁移

迁移 `ec06ac928b64` 新增 `notifications` 表：

```powershell
uv run alembic upgrade head
```
