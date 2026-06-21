# A14～A15：分析任务进度与失败重试

批量视频分析使用后台任务执行。创建任务后接口立即返回任务信息，客户端可以持续查询进度。

## 创建分析任务

```http
POST /api/v1/local-resources/batch-analyze
Content-Type: application/json

{
  "resource_ids": [1, 2, 3],
  "force": false
}
```

响应状态码为 `202`，初始状态为 `waiting`。

## 查询任务

```http
GET /api/v1/local-resources/analysis-tasks
GET /api/v1/local-resources/analysis-tasks/{task_id}
```

任务返回：

- `status`：`waiting`、`running`、`completed` 或 `failed`；
- `progress`：百分比进度；
- `total_resources` 和 `processed_resources`；
- 已分析、已跳过和文件缺失的资源 ID；
- 单个资源的失败原因；
- 开始时间和完成时间。

单个资源分析失败不会中止整批任务。所有资源处理结束后任务状态仍为 `completed`，
失败项保存在 `failures` 中。

## 重试失败资源

```http
POST /api/v1/local-resources/analysis-tasks/{task_id}/retry
```

重试会创建一个新的后台任务：

- 只包含原任务的失败资源；
- 自动启用强制重新分析；
- 通过 `retry_of_task_id` 关联原任务；
- 不修改原任务的历史执行结果。

工作线程发生系统级异常时，任务状态为 `failed`，重试任务还会包含原任务中尚未处理的资源。
没有失败项或未处理资源时返回 `ANALYSIS_TASK_NOT_RETRYABLE`。

## 重启恢复

应用启动时会恢复 `waiting` 和 `running` 状态的分析任务，并从头重新执行。
分析写入具有幂等性，已经生成的哈希和视觉资源缓存可以复用。

## 数据库升级

```powershell
uv run alembic upgrade head
```
