# Q14：WebSocket 推送任务状态

统一任务中心支持通过 WebSocket 实时推送任务创建、状态、进度、完成、失败、取消、重试和
恢复事件。前端无需频繁轮询任务详情接口。

## 建立连接

```text
ws://localhost:8000/api/v1/tasks/ws
```

连接建立后首先收到：

```json
{
  "type": "connected",
  "task_type": null,
  "status": null
}
```

## 事件格式

```json
{
  "type": "task_event",
  "event": "progress",
  "message": "任务进度更新为 50.00%",
  "details": {
    "processed_items": 5,
    "total_items": 10
  },
  "occurred_at": "2026-06-22T23:30:00",
  "task": {
    "id": 42,
    "task_type": "media_scan",
    "status": "running",
    "progress": 50,
    "processed_items": 5,
    "total_items": 10
  }
}
```

任务对象还包含优先级、重试次数、取消和暂停能力、执行结果、错误、开始时间、完成时间及
心跳时间。

## 订阅筛选

可按任务类型和状态筛选：

```text
ws://localhost:8000/api/v1/tasks/ws?task_type=download&status=running
```

筛选值与统一任务列表接口一致。非法值返回 `INVALID_TASK_EVENT_FILTER`，连接以
WebSocket 关闭码 `1008` 结束。

## 心跳

- 客户端发送文本 `ping`，服务端返回 `pong`；
- 连接空闲 25 秒时，服务端发送 `heartbeat`；
- 心跳消息包含服务器发送时间。

## 可靠性边界

事件总线运行在当前应用进程内，每个连接使用最多 100 条的有界队列。客户端消费过慢时会
丢弃最旧事件并保留较新状态，避免阻塞下载或转码线程。

WebSocket 用于实时界面更新，不替代数据库事实来源。客户端断线重连后应通过
`GET /api/v1/tasks` 或 `GET /api/v1/tasks/{task_id}` 获取最新完整状态。

多进程或多实例部署时，后续可将进程内事件总线替换为 Redis Pub/Sub 等跨进程消息系统。

## 数据库

本次迭代复用统一任务日志事件，不修改数据库结构，不需要新增 Alembic 迁移。
