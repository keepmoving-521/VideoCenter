# F01：媒体目录配置模型

系统新增持久化媒体目录配置，用于管理媒体根目录下的多个影片存储目录。

## 模型字段

| 字段 | 说明 |
| --- | --- |
| `name` | 目录显示名称，全库唯一 |
| `path` | 规范化绝对路径，全库唯一 |
| `is_default` | 是否为默认媒体目录 |
| `is_enabled` | 是否启用 |
| `auto_scan` | 后续自动扫描任务是否处理该目录 |
| `created_at` | 创建时间 |
| `updated_at` | 更新时间 |

目录路径必须真实存在，并位于 `VIDEOCENTER_MEDIA_ROOT` 内。请求可以传媒体根目录内的
相对路径，也可以传绝对路径；数据库统一保存规范化绝对路径。

## 接口

### 查询目录

```http
GET /api/v1/media-directories
```

默认目录排在最前面。

### 创建目录

```http
POST /api/v1/media-directories
```

```json
{
  "name": "Movies",
  "path": "movies",
  "is_default": true,
  "is_enabled": true,
  "auto_scan": true
}
```

创建第一个目录时，即使没有显式指定 `is_default`，系统也会自动设为默认目录。

### 更新目录

```http
PATCH /api/v1/media-directories/{directory_id}
```

将某个目录设为默认时，原默认目录会自动取消默认状态。当前默认目录不能直接取消默认，
应先把另一个目录设为默认。

## 错误码

- `MEDIA_DIRECTORY_NOT_FOUND`
- `INVALID_MEDIA_DIRECTORY_PATH`
- `MEDIA_DIRECTORY_NAME_EXISTS`
- `MEDIA_DIRECTORY_PATH_EXISTS`
- `MEDIA_DIRECTORY_DEFAULT_REQUIRED`

## 数据迁移

迁移 `79c5840db912` 新增 `media_directories` 表：

```powershell
uv run alembic upgrade head
```

本次只建立配置模型和管理接口，现有下载与扫描仍使用原有路径参数。后续迭代可按媒体
目录 ID 选择下载、扫描和资源归属。
