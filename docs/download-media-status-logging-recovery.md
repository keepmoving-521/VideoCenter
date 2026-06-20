# D20～D22：影片状态、下载日志与重启恢复

## 下载完成后更新影片状态

关联影视的下载任务会驱动影片状态：

- 存在等待、下载中或暂停任务，且尚无本地资源：`downloading`
- 下载成功并登记本地资源：`available`
- 所有活动任务结束且没有本地资源：`pending`

状态计算会检查同一影片的全部下载任务和本地资源。因此某个任务失败或取消时，如果
影片已经存在其他本地资源，不会错误地从 `available` 降级。

## 结构化下载任务日志

下载服务使用 `videocenter.services.downloads` 日志记录器输出结构化事件。

| `download_event` | 说明 |
| --- | --- |
| `queued` | 新任务进入队列 |
| `restored` | 应用启动时恢复任务 |
| `started` | 工作线程开始执行 |
| `progress` | 下载进度跨过新的 10% 区间 |
| `paused` | 用户暂停任务 |
| `resumed` | 用户恢复任务 |
| `cancelled` | 任务被取消 |
| `retry_queued` | 失败任务重新入队 |
| `completed` | 下载、校验和资源登记完成 |
| `failed` | 下载失败 |
| `recovery_completed` | 应用启动恢复流程完成 |

常见上下文字段包括：

- `download_task_id`
- `media_id`
- `status`
- `priority`
- `progress`
- `downloaded_bytes`
- `speed_bytes_per_second`
- `remaining_seconds`
- `duration_ms`
- `error_type`

进度日志按 10% 区间节流，避免每个下载分块都写日志。

## 应用重启恢复

应用启动时：

1. 将数据库中的 `downloading` 重置为 `waiting`。
2. 清空中断任务的进度、速度、剩余时间、目标路径和校验结果。
3. 清理对应的 `.part` 临时文件。
4. 按优先级降序、任务 ID 升序重新入队。
5. 保留用户主动设置的 `paused` 状态，不自动恢复下载。
6. 重新计算关联影片状态。

每个恢复任务会记录 `download_event=restored`，恢复结束记录
`download_event=recovery_completed` 和恢复任务数量。

本次迭代不改变数据库结构，不需要新增 Alembic 迁移。
