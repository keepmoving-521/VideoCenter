# F04～F06：后台扫描、扫描进度与增量扫描

本地媒体扫描已从同步请求改为持久化后台任务。提交扫描后接口立即返回任务，客户端可
轮询任务详情查看进度。

## 创建扫描任务

```http
POST /api/v1/local-resources/scan
```

```json
{
  "path": "movies",
  "media_id": null,
  "incremental": true
}
```

- `path` 为空时扫描 `VIDEOCENTER_MEDIA_ROOT`。
- 路径必须真实存在并位于媒体根目录内。
- `media_id` 可选，用于将发现的文件关联到指定影视。
- `incremental` 默认值为 `true`。

接口返回 HTTP 202 和状态为 `waiting` 的扫描任务。

## 查询任务

```http
GET /api/v1/local-resources/scan-tasks
GET /api/v1/local-resources/scan-tasks/{task_id}
```

扫描状态：

- `waiting`
- `running`
- `completed`
- `failed`

进度字段：

| 字段 | 说明 |
| --- | --- |
| `progress` | 完成百分比 |
| `total_files` | 扫描开始时发现的媒体文件总数 |
| `processed_files` | 已处理文件数 |
| `discovered_files` | 本次发现文件数 |
| `added_files` | 新增本地资源数 |
| `updated_files` | 更新本地资源数 |
| `skipped_files` | 增量扫描跳过的未变化文件数 |
| `error_message` | 失败原因 |

## 增量扫描

每个本地资源保存文件的纳秒修改时间 `modified_at_ns`。增量扫描同时比较：

- 规范化绝对路径；
- 文件大小；
- 纳秒修改时间；
- 可选的影视关联。

全部相同时直接跳过。文件大小、修改时间或影视关联发生变化时更新原记录。设置
`incremental=false` 时，已有文件也会重新读取并更新元数据。

## 应用重启恢复

应用启动时会把 `waiting` 和意外中断的 `running` 扫描任务重置后重新执行。

## 数据迁移

迁移 `e191f7270b02` 新增：

- `scan_tasks` 表；
- `local_resources.modified_at_ns` 字段。

```powershell
uv run alembic upgrade head
```
