# D02：HTTP 直链下载器重构

D02 将原来写在下载任务线程中的 HTTP 文件传输逻辑拆分为独立的
`HttpDirectDownloader`，并接入 D01 定义的统一下载器接口。

## 职责划分

`HttpDirectDownloader` 负责：

- 发起 HTTP/HTTPS 请求。
- 传递自定义请求头和超时配置。
- 分块写入 `.part` 临时文件。
- 报告开始、下载中和收尾阶段的进度。
- 响应协作式取消。
- 下载完成后原子移动为目标文件。
- 返回文件路径、大小和 MIME 类型。
- 失败或取消时清理临时文件。

下载任务服务负责：

- 管理后台线程。
- 更新 `DownloadTask` 状态和百分比。
- 管理任务取消令牌。
- 下载完成后创建 `LocalResource` 记录。
- 将下载器异常记录到任务中。

## 当前行为

现有 `POST /api/v1/downloads`、下载详情和取消接口保持不变。任务执行时默认使用
`HttpDirectDownloader`，并设置 `User-Agent: VideoCenter/0.1`。

当前任务保持原有覆盖目标文件的行为。直接单独调用下载器时，`overwrite` 默认为
`false`，避免无意覆盖已有文件。

本次迭代不修改数据库结构，不需要新增 Alembic 迁移。
