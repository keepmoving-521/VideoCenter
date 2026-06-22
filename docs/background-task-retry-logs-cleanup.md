# Q10～Q12：统一任务重试、日志与历史清理

统一任务中心支持失败任务重试、结构化日志查询和过期历史清理。

## 失败任务重试

```http
POST /api/v1/tasks/{task_id}/retry
```

仅 `failed` 状态可以重试，并调用真实业务执行器：

- 下载任务重置原下载任务并重新进入下载队列；
- 扫描任务重置进度后重新启动扫描线程；
- HLS 任务重置进度后重新进入转码队列；
- 媒体分析创建新的业务任务和统一任务，通过 `parent_task_id` 指向原任务。

下载、扫描和 HLS 的统一任务会增加 `attempt`。分析重试返回新统一任务，其 `attempt` 为
父任务次数加一。

资源解析任务目前依赖请求期间的解析器运行上下文，尚不支持安全重试，返回
`BACKGROUND_TASK_RETRY_NOT_SUPPORTED`。

## 任务日志

```http
GET /api/v1/tasks/{task_id}/logs?page=1&page_size=100
```

可使用 `event` 参数筛选事件。日志包含：

- 事件名称和说明；
- 事件发生时的任务状态与进度；
- 结构化详情；
- 创建时间。

系统记录任务接入、启动、状态变化、进度、完成、失败、取消和重试事件。一次最多查询
500 条。

## 历史任务清理

```http
POST /api/v1/tasks/cleanup
Content-Type: application/json

{
  "max_age_days": 30
}
```

只删除完成时间早于截止日期且状态为 `completed`、`failed` 或 `cancelled` 的统一任务，
并同步删除任务日志。等待、运行和暂停任务不会被清理。

清理操作不会删除业务任务明细、影视条目、下载文件或媒体缓存。

## 数据库迁移

迁移 `a8c31f72d590` 新增 `background_task_logs`：

```powershell
uv run alembic upgrade head
```
