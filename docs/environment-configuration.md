# B03：开发、测试、生产环境配置

本文档说明 VideoCenter 的多环境配置结构和使用方法。

## 支持的环境

系统支持三种运行环境：

| 环境 | 配置值 | 用途 |
| --- | --- | --- |
| 开发 | `development` | 本地开发、接口调试 |
| 测试 | `testing` | 自动化测试、集成测试 |
| 生产 | `production` | 正式部署 |

通过 `VIDEOCENTER_ENVIRONMENT` 选择当前环境：

```dotenv
VIDEOCENTER_ENVIRONMENT=development
```

未指定时默认使用 `development`。

## 配置加载顺序

系统按以下顺序加载配置，后面的配置优先级更高：

1. 代码中的默认值；
2. 公共 `.env`；
3. 当前环境文件 `.env.<environment>`；
4. 操作系统环境变量。

例如选择 `testing` 时，会依次读取：

```text
.env
.env.testing
```

因此公共配置可以放在 `.env`，只把数据库地址、日志级别等差异项放入环境文件。

## 配置模板

项目提供以下可提交的模板：

```text
.env.example
.env.development.example
.env.testing.example
.env.production.example
```

实际 `.env` 文件可能包含本机路径、数据库连接或其他敏感配置，不会提交到 Git。

## 开发环境

创建配置：

```powershell
Copy-Item .env.development.example .env.development
$env:VIDEOCENTER_ENVIRONMENT = "development"
```

初始化数据库并启动：

```powershell
uv run alembic upgrade head
uv run uvicorn videocenter.main:app --reload
```

开发模板默认：

- 开启调试模式；
- 开启 API 文档；
- 使用开发 SQLite 数据库；
- 日志级别为 `DEBUG`；
- 允许本地前端开发服务器跨域访问。

## 测试环境

创建配置：

```powershell
Copy-Item .env.testing.example .env.testing
$env:VIDEOCENTER_ENVIRONMENT = "testing"
```

执行迁移和测试：

```powershell
uv run alembic upgrade head
uv run pytest
```

测试模板使用独立数据库和媒体目录，避免测试数据污染开发环境。

自动化测试可以直接设置操作系统环境变量覆盖文件配置。

## 生产环境

创建配置：

```powershell
Copy-Item .env.production.example .env.production
$env:VIDEOCENTER_ENVIRONMENT = "production"
```

根据部署环境修改数据库、媒体目录和允许的跨域来源，然后运行：

```powershell
uv run alembic upgrade head
uv run uvicorn videocenter.main:app --host 0.0.0.0 --port 8000
```

生产环境具有以下安全校验：

- 禁止开启 `DEBUG`；
- 禁止使用通配符 `*` 作为 CORS 来源。

生产模板默认关闭 Swagger、ReDoc 和 OpenAPI 地址。如需开放文档，应在明确的访问控制下设置：

```dotenv
VIDEOCENTER_DOCS_ENABLED=true
```

## 配置项

| 配置项 | 说明 |
| --- | --- |
| `VIDEOCENTER_ENVIRONMENT` | 当前运行环境 |
| `VIDEOCENTER_APP_NAME` | 应用名称 |
| `VIDEOCENTER_DEBUG` | FastAPI 调试模式 |
| `VIDEOCENTER_LOG_LEVEL` | 日志级别 |
| `VIDEOCENTER_LOG_FORMAT` | 文本或 JSON 日志格式 |
| `VIDEOCENTER_LOG_FILE_ENABLED` | 是否输出日志文件 |
| `VIDEOCENTER_LOG_DIR` | 日志文件目录 |
| `VIDEOCENTER_DOCS_ENABLED` | 是否开放 API 文档 |
| `VIDEOCENTER_DATABASE_ECHO` | 是否输出 SQLAlchemy SQL |
| `VIDEOCENTER_DATABASE_URL` | 数据库连接地址 |
| `VIDEOCENTER_MEDIA_ROOT` | 本地媒体根目录 |
| `VIDEOCENTER_FFMPEG_PATH` | FFmpeg 可执行文件路径，留空时从 PATH 检测 |
| `VIDEOCENTER_FFPROBE_PATH` | FFprobe 可执行文件路径，留空时从 PATH 检测 |
| `VIDEOCENTER_API_PREFIX` | API 路径前缀 |
| `VIDEOCENTER_CORS_ORIGINS` | 允许跨域访问的来源列表 |

列表配置使用 JSON 格式：

```dotenv
VIDEOCENTER_CORS_ORIGINS=["https://video.example.com"]
```

## 使用 pip

多环境配置与包管理工具无关。使用 pip 虚拟环境时，命令改为：

```powershell
python -m alembic upgrade head
python -m uvicorn videocenter.main:app
```

## 验证当前环境

应用根接口会返回当前环境和文档地址：

```http
GET /
```

开发环境示例：

```json
{
  "name": "VideoCenter Development",
  "environment": "development",
  "docs": "/docs"
}
```

生产环境关闭文档时，`docs` 返回 `null`。

日志相关配置详见[统一日志配置](logging-configuration.md)。
