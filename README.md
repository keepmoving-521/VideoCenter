# VideoCenter

[![CI](https://github.com/keepmoving-521/VideoCenter/actions/workflows/ci.yml/badge.svg)](https://github.com/keepmoving-521/VideoCenter/actions/workflows/ci.yml)

VideoCenter 是一个面向个人使用的轻量级影视库后端，用于统一管理影视条目、下载任务、本地视频、在线播放进度和观看历史。

## 当前能力

- 影视条目增删改查与搜索
- HTTP/HTTPS 直链后台下载、进度查询和任务取消
- 扫描本地媒体目录并登记视频文件
- 支持 HTTP Range 的视频流播放
- 保存播放进度和观看历史
- SQLite 本地数据库与自动生成的 OpenAPI 文档

> 请只下载和管理你有权使用的内容。当前下载器仅处理直接媒体文件链接，后续可以通过 `DownloadProvider` 接口接入 yt-dlp、Aria2 等实现。

## 快速开始

要求 Python 3.12+。项目同时支持 `uv` 和传统 `pip`，任选一种方式即可。

### 使用 uv（推荐）

首次安装 `uv`：

```powershell
python -m pip install uv
```

创建虚拟环境并严格按照锁文件安装开发依赖：

```powershell
uv sync --extra dev --frozen
Copy-Item .env.example .env
uv run alembic upgrade head
uv run uvicorn videocenter.main:app --reload
```

### 使用 pip

创建并激活虚拟环境：

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
```

开发环境安装（包含测试、覆盖率和代码检查工具）：

```powershell
python -m pip install -r requirements-dev.txt
Copy-Item .env.example .env
python -m alembic upgrade head
python -m uvicorn videocenter.main:app --reload
```

生产环境只安装运行依赖：

```powershell
python -m pip install -r requirements.txt
Copy-Item .env.example .env
python -m alembic upgrade head
python -m uvicorn videocenter.main:app --host 0.0.0.0 --port 8000
```

打开：

- API 文档：http://127.0.0.1:8000/docs
- 健康检查：http://127.0.0.1:8000/api/v1/health

运行测试（根据安装方式选择）：

```powershell
# uv
uv run pytest

# pip 虚拟环境
python -m pytest
```

## 依赖与锁文件

依赖文件的职责如下：

- `pyproject.toml`：项目元数据和允许使用的依赖版本范围。
- `uv.lock`：uv 使用的完整锁文件。
- `requirements.txt`：pip 生产环境的固定依赖版本。
- `requirements-dev.txt`：pip 开发环境的固定依赖版本。

`requirements*.txt` 从 `uv.lock` 导出，不应单独手动修改。更新依赖时先更新锁文件，再重新导出 pip 文件。

添加运行依赖：

```powershell
uv add 包名
```

添加开发依赖：

```powershell
uv add --optional dev 包名
```

修改 `pyproject.toml` 后更新锁文件和本地环境：

```powershell
uv lock
uv sync --extra dev
```

同步生成 pip 依赖文件：

```powershell
uv export --frozen --no-dev --no-editable --no-annotate --no-header --no-hashes --output-file requirements.txt
uv export --frozen --extra dev --no-annotate --no-header --no-hashes --output-file requirements-dev.txt
```

升级全部允许升级的依赖：

```powershell
uv lock --upgrade
uv sync --extra dev
```

只升级一个依赖：

```powershell
uv lock --upgrade-package fastapi
uv sync --extra dev
```

CI 或生产部署应使用 `--frozen`，确保配置和锁文件不一致时直接失败：

```powershell
# 生产环境
uv sync --frozen --no-dev

# CI 测试环境
uv sync --frozen --extra dev
uv run pytest
```

使用 pip 的 CI 或生产环境，应直接安装已提交的固定版本依赖文件：

```powershell
# 生产环境
python -m pip install -r requirements.txt

# CI 测试环境
python -m pip install -r requirements-dev.txt
python -m pytest
```

## 数据库迁移

项目使用 Alembic 管理数据库结构。配置、命令、开发流程和 SQLite 注意事项请参阅
[Alembic 数据库迁移文档](docs/database-migrations.md)。

其他迭代专题请参阅[开发文档索引](docs/README.md)。

## 运行环境

系统支持开发、测试和生产环境的分层配置。配置文件、加载优先级和生产安全校验请参阅
[多环境配置文档](docs/environment-configuration.md)。

统一日志格式、文件轮转和各环境建议请参阅
[日志配置文档](docs/logging-configuration.md)。

业务异常、参数校验和服务端错误处理请参阅
[统一异常处理文档](docs/exception-handling.md)。

标准错误模型、请求追踪 ID 和 OpenAPI 声明请参阅
[API 错误响应格式](docs/api-error-response.md)。

请求体、路径、查询参数和请求头的校验规则请参阅
[请求参数校验文档](docs/request-validation.md)。

pytest 使用独立数据库的创建、迁移、隔离和清理机制请参阅
[测试专用数据库文档](docs/testing-database.md)。

API 客户端、数据工厂、响应断言和集成测试标记请参阅
[API 集成测试框架](docs/api-integration-testing.md)。

统一 Ruff lint、格式检查和自动修复用法请参阅
[Ruff 代码检查文档](docs/ruff-code-check.md)。

提交前自动文件检查和 Ruff hooks 的安装方式请参阅
[pre-commit 配置文档](docs/pre-commit.md)。

GitHub Actions 自动检查、测试与覆盖率流程请参阅
[GitHub Actions 文档](docs/github-actions.md)。

影视排序标题、别名、上映日期和内容分级字段请参阅
[影视资源核心字段文档](docs/media-core-fields.md)。

影视状态、类型、来源、演职员、分类、时长与评分字段请参阅
[影视元数据字段文档](docs/media-metadata-fields.md)。

海报、背景图、影视标签以及电视剧季/分集模型请参阅
[影视目录层级文档](docs/media-artwork-tags-seasons-episodes.md)。

影片、季和分集的关联查询请参阅
[影片季集关联文档](docs/media-season-episode-association.md)。

收藏、个人评分和私人备注请参阅
[影视个人偏好文档](docs/media-personal-preferences.md)。

影视资源页面解析器的扩展契约请参阅
[资源解析器统一接口文档](docs/resource-parser-interface.md)。

解析器标准输出字段、校验和序列化规则请参阅
[解析结果数据结构文档](docs/parser-result-structure.md)。

根据资源页面域名自动路由解析器的规则请参阅
[解析器 URL 选择文档](docs/parser-url-selection.md)。

不支持网站的错误代码、响应内容和安全规则请参阅
[不支持网站错误处理文档](docs/unsupported-website-error.md)。

普通网页的 JSON-LD、Open Graph 和 HTML 基础信息提取请参阅
[通用网页解析器文档](docs/generic-webpage-parser.md)。

网页标题、简介、海报、上映年份和演职员的详细解析规则请参阅
[网页影片核心信息解析文档](docs/webpage-core-metadata-parsing.md)。

视频下载地址、多清晰度、字幕和电视剧季集结构的解析规则请参阅
[网页媒体资源与季集解析文档](docs/webpage-media-resources-and-series.md)。

资源页面预解析、用户确认以及保存入库流程请参阅
[资源预解析确认保存文档](docs/parse-preview-confirm-save.md)。

解析超时、指数退避和临时失败重试规则请参阅
[解析超时与重试文档](docs/parser-timeout-and-retry.md)。

解析任务追踪日志和成功结果缓存规则请参阅
[解析任务日志与缓存文档](docs/parser-task-logging-and-cache.md)。

并发重复解析合并和解析器单元测试范围请参阅
[防止重复解析与解析器测试文档](docs/duplicate-parsing-and-parser-tests.md)。

影视资源列表的分页参数和响应结构请参阅
[影视资源分页查询文档](docs/media-pagination.md)。

## 项目结构

```text
docs/              # 功能和开发专题文档
migrations/        # Alembic 数据库迁移
src/videocenter/
├── api/          # HTTP 路由与请求依赖
├── core/         # 配置、数据库和日志
├── models/       # 数据库实体
├── schemas/      # API 输入输出模型
├── services/     # 下载、媒体扫描、播放等业务逻辑
└── main.py       # 应用入口
```

默认运行数据写入 `data/`，下载文件保存在 `data/media/`。这些目录不会提交到 Git。

## 主要接口

| 模块 | 接口 |
| --- | --- |
| 健康检查 | `GET /api/v1/health` |
| 影视库 | `GET/POST /api/v1/media` |
| 影视详情 | `GET/PATCH/DELETE /api/v1/media/{id}` |
| 下载任务 | `GET/POST /api/v1/downloads` |
| 取消下载 | `POST /api/v1/downloads/{id}/cancel` |
| 本地扫描 | `POST /api/v1/local-resources/scan` |
| 本地资源 | `GET /api/v1/local-resources` |
| 视频播放 | `GET /api/v1/stream/{resource_id}` |
| 观看历史 | `GET/PUT /api/v1/history` |

## 下一阶段建议

1. 增加 Web 管理界面。
2. 接入 FFmpeg 获取时长、分辨率和封面。
3. 接入可选的 yt-dlp/Aria2 下载提供器。
4. 增加影片元数据抓取、标签、合集与字幕管理。
5. 当系统不再仅限本机使用时，增加身份认证和访问控制。
