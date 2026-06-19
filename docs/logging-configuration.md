# B04：统一日志配置

本文档说明 VideoCenter 的统一日志配置、输出格式和文件轮转方式。

## 实现目标

日志系统统一管理以下输出：

- VideoCenter 业务模块；
- FastAPI 应用启动和停止；
- Uvicorn 服务日志与访问日志；
- SQLAlchemy 数据库日志；
- Alembic 数据库迁移日志。

项目不再由各模块分别调用 `basicConfig()` 或维护独立日志格式。所有模块通过 Python 标准库获取日志器：

```python
import logging

logger = logging.getLogger(__name__)
logger.info("Media scan started")
```

## 日志初始化

统一入口位于：

```text
src/videocenter/core/logging.py
```

应用导入时根据当前环境配置调用：

```python
configure_logging(settings)
```

Alembic 迁移环境也使用同一个入口，因此迁移和应用拥有一致的级别、格式和文件输出规则。

## 输出位置

日志默认同时输出到：

- 标准输出；
- `data/logs/` 下的轮转日志文件。

测试环境默认只输出到控制台，避免自动化测试产生本地日志文件。

## 文本格式

开发环境默认使用便于阅读的文本格式：

```text
2026-06-19 20:00:00 | INFO | development | request-id | videocenter.main | Application started
```

包含时间、级别、环境、请求 ID、日志器名称和消息。与请求无关的启动、迁移等日志使用 `-` 作为请求 ID。

## JSON 格式

生产环境默认使用单行 JSON，便于日志平台采集：

```json
{
  "timestamp": "2026-06-19T12:00:00+00:00",
  "level": "INFO",
  "logger": "videocenter.main",
  "environment": "production",
  "message": "Application started"
}
```

使用 `extra` 传入的业务字段会自动写入 JSON：

```python
logger.info("Download started", extra={"task_id": 42, "media_id": 10})
```

异常日志会包含格式化后的异常堆栈。

## 文件轮转

项目使用 `RotatingFileHandler` 按文件大小轮转：

- 当前文件达到 `VIDEOCENTER_LOG_MAX_BYTES` 后创建备份；
- 最多保留 `VIDEOCENTER_LOG_BACKUP_COUNT` 个旧文件；
- 超出数量的最旧日志会自动删除；
- 文件统一使用 UTF-8 编码。

例如：

```text
videocenter.log
videocenter.log.1
videocenter.log.2
```

## 配置项

| 配置项 | 默认值 | 说明 |
| --- | --- | --- |
| `VIDEOCENTER_LOG_LEVEL` | `INFO` | 最低日志级别 |
| `VIDEOCENTER_LOG_FORMAT` | `text` | `text` 或 `json` |
| `VIDEOCENTER_LOG_FILE_ENABLED` | `true` | 是否写入文件 |
| `VIDEOCENTER_LOG_DIR` | `./data/logs` | 日志目录 |
| `VIDEOCENTER_LOG_FILE_NAME` | `videocenter.log` | 当前日志文件名 |
| `VIDEOCENTER_LOG_MAX_BYTES` | `10485760` | 单个文件最大字节数 |
| `VIDEOCENTER_LOG_BACKUP_COUNT` | `5` | 轮转备份数量 |
| `VIDEOCENTER_DATABASE_ECHO` | `false` | 是否输出 SQL 语句 |

支持的日志级别：

```text
DEBUG
INFO
WARNING
ERROR
CRITICAL
```

## 环境建议

### 开发环境

```dotenv
VIDEOCENTER_LOG_LEVEL=DEBUG
VIDEOCENTER_LOG_FORMAT=text
VIDEOCENTER_LOG_FILE_ENABLED=true
```

### 测试环境

```dotenv
VIDEOCENTER_LOG_LEVEL=WARNING
VIDEOCENTER_LOG_FORMAT=text
VIDEOCENTER_LOG_FILE_ENABLED=false
```

### 生产环境

```dotenv
VIDEOCENTER_LOG_LEVEL=INFO
VIDEOCENTER_LOG_FORMAT=json
VIDEOCENTER_LOG_FILE_ENABLED=true
VIDEOCENTER_LOG_BACKUP_COUNT=10
```

## 注意事项

- 不要使用 `print()` 输出运行信息；
- 不要在日志中记录密码、令牌或完整 Cookie；
- 文件路径、下载地址等可能包含隐私信息，生产环境应按需脱敏；
- 高频循环中避免逐条记录 `INFO`，进度日志应控制频率；
- 捕获异常时使用 `logger.exception()` 保留堆栈。
