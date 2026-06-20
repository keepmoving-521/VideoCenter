# D03～D04：下载任务队列与状态

## 下载任务队列

下载任务不再为每个任务单独创建线程。系统使用固定数量的后台工作线程，从先进先出
队列中依次取出任务执行。

工作线程数量通过环境变量配置：

```env
VIDEOCENTER_DOWNLOAD_WORKER_COUNT=1
```

允许范围为 `1～16`，默认值为 `1`。单工作线程会按入队顺序依次下载，增加数量后可
并行处理多个任务。

同一任务 ID 不会重复进入队列。等待中的任务可以取消；它到达队首后会被跳过，不会
开始网络请求。

## 下载状态

| API 值 | 数据库值 | 说明 |
| --- | --- | --- |
| `waiting` | `WAITING` | 已创建并进入队列，等待工作线程 |
| `downloading` | `DOWNLOADING` | 工作线程正在下载 |
| `completed` | `COMPLETED` | 下载和本地资源登记完成 |
| `failed` | `FAILED` | 下载失败，错误信息写入 `error_message` |
| `cancelled` | `CANCELLED` | 等待中或下载中的任务已取消 |

新任务默认状态为 `waiting`。工作线程取出任务后切换为 `downloading`，成功后设置
`progress=100` 并切换为 `completed`。

## 应用重启恢复

应用启动时会恢复未完成任务：

- 数据库中的 `DOWNLOADING` 会重置为 `WAITING`，进度重置为 `0`。
- 所有 `WAITING` 任务按照任务 ID 依次重新入队。

这样进程意外终止后，未完成任务不会永久卡在下载中状态。

## 数据迁移

迁移 `6f17a72c8e41` 会转换旧状态：

- `PENDING` → `WAITING`
- `RUNNING` → `DOWNLOADING`

执行：

```powershell
uv run alembic upgrade head
```
