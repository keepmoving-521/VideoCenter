# F07～F08：新增与删除视频文件检测

后台扫描现在会比较扫描目录中的实际文件与数据库中的本地资源，检测新增、删除和重新
出现的视频文件。

## 新增文件

扫描发现数据库中不存在的绝对路径时：

- 新建 `LocalResource`；
- 保存文件名、大小、MIME 类型和纳秒修改时间；
- 设置 `is_available=true`；
- 扫描任务的 `added_files` 加一；
- 关联影视状态更新为 `available`。

## 已删除文件

扫描结束后，系统检查数据库中属于本次扫描目录、但本次没有发现的资源：

- 保留本地资源记录及影视关联；
- 设置 `is_available=false`；
- 写入 `missing_at`；
- 扫描任务的 `missing_files` 加一；
- 如果影视没有其他可用资源或活动下载任务，状态更新为 `missing`。

系统不会因为扫描发现文件缺失而直接删除数据库记录，这样观看历史、下载关联和后续
恢复信息不会丢失。

## 文件恢复

缺失文件重新出现在原路径时：

- 更新文件元数据；
- 设置 `is_available=true`；
- 清空 `missing_at`；
- `restored_files` 加一；
- 关联影视恢复为 `available`。

## 扫描范围

删除检测只处理本次请求路径及其子目录中的本地资源。扫描一个子目录不会把其他媒体
目录中的文件误标记为缺失。

## API 字段

本地资源新增：

- `is_available`
- `missing_at`

扫描任务新增：

- `missing_files`
- `restored_files`

## 数据迁移

迁移 `f809bb912daf` 增加资源可用状态和扫描差异计数：

```powershell
uv run alembic upgrade head
```
