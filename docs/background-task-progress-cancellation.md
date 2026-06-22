# Q08～Q09：统一任务进度查询与取消

系统提供统一后台任务列表、详情和取消接口。客户端不再需要分别查询下载、扫描、分析和
转码接口，即可展示跨业务任务中心。

## 任务列表

```http
GET /api/v1/tasks?page=1&page_size=50
```

支持筛选：

- `task_type`：`resource_parse`、`download`、`media_scan`、`media_analysis`、
  `hls_transcode` 或 `generic`；
- `status`：`waiting`、`running`、`paused`、`completed`、`failed` 或
  `cancelled`。

响应包含标准分页信息和完整统一任务数据。

## 任务详情与进度

```http
GET /api/v1/tasks/{task_id}
```

响应包含：

- 状态、百分比进度；
- 已处理数量和总数量；
- 当前尝试次数和最大次数；
- 是否允许取消或暂停；
- 任务参数、执行结果和错误；
- 创建、开始、完成及心跳时间。

## 取消任务

```http
POST /api/v1/tasks/{task_id}/cancel
```

取消接口会分发到真实业务执行器。目前视频下载已支持可靠取消，会同时停止下载队列并更新
下载业务状态和统一任务状态。重复取消已取消任务是幂等操作。

资源解析、本地扫描、媒体分析和 HLS 转码目前尚未实现安全中断，因此统一任务会标记
`cancellable = false`，取消请求返回 `BACKGROUND_TASK_NOT_CANCELLABLE`。系统不会只修改
数据库状态而让实际后台任务继续运行。

## 数据库

本次迭代没有修改数据库结构，不需要新增 Alembic 迁移。
