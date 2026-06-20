# D08～D11：下载任务暂停、恢复、取消与重试

## 接口

```http
POST /api/v1/downloads/{task_id}/pause
POST /api/v1/downloads/{task_id}/resume
POST /api/v1/downloads/{task_id}/cancel
POST /api/v1/downloads/{task_id}/retry
```

所有接口返回更新后的下载任务。

## 状态流转

| 操作 | 允许的来源状态 | 目标状态 |
| --- | --- | --- |
| 暂停 | `waiting`、`downloading` | `paused` |
| 恢复 | `paused` | `waiting` 或 `downloading` |
| 取消 | `waiting`、`downloading`、`paused` | `cancelled` |
| 重试 | `failed` | `waiting` |

重复取消已经是 `cancelled` 的任务会直接返回当前任务。其他不合法状态转换返回
HTTP 409，并使用以下错误码：

- `DOWNLOAD_NOT_PAUSABLE`
- `DOWNLOAD_NOT_RESUMABLE`
- `DOWNLOAD_NOT_CANCELLABLE`
- `DOWNLOAD_NOT_RETRYABLE`

## 暂停行为

运行中的 HTTP 下载采用协作式暂停：

- 工作线程保持运行，但阻塞在下一次分块读取之前。
- 当前 `.part` 临时文件和已建立的 HTTP 响应保持不变。
- 恢复后继续读取后续分块。
- 暂停期间速度和剩余时间设置为 `null`，已下载字节和百分比保持不变。

如果应用在暂停期间重启，任务仍保持 `paused`。之后调用恢复接口会重新进入队列，
并从头开始下载；跨进程断点续传不属于本次迭代范围。

## 重试行为

失败任务重试时会清空：

- 下载百分比和字节进度；
- 文件总大小、速度和剩余时间；
- 错误信息和目标文件路径。

任务随后重新进入等待队列。

## 数据迁移

迁移 `cf6e704f63c2` 为下载状态枚举增加 `PAUSED`：

```powershell
uv run alembic upgrade head
```
