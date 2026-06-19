# B09：API 集成测试框架

本文档说明 VideoCenter API 集成测试的目录、fixture、数据工厂和断言约定。

## 目标

API 集成测试应验证完整调用链：

```text
HTTP 请求
  → FastAPI 路由与中间件
  → 参数校验和异常处理
  → SQLAlchemy 业务操作
  → 测试数据库
  → HTTP 响应
```

框架提供统一工具，避免每个测试重复创建客户端、手工插入复杂数据或重复解析错误响应。

## 目录结构

```text
tests/
├── conftest.py
├── integration/
│   ├── __init__.py
│   └── test_media_flow.py
└── support/
    ├── __init__.py
    ├── api.py
    └── factories.py
```

- `conftest.py`：全局 fixture 和测试数据库生命周期；
- `integration/`：通过真实 HTTP 调用应用的集成测试；
- `support/api.py`：标准响应断言；
- `support/factories.py`：数据库测试数据工厂。

## api_client

测试通过 `api_client` fixture 调用真实 FastAPI 应用：

```python
def test_health(api_client):
    response = api_client.get("/api/v1/health")
    assert response.status_code == 200
```

该 fixture：

- 使用 FastAPI `TestClient`；
- 自动进入和退出应用生命周期；
- 连接 B08 创建的测试专用数据库；
- 包含实际中间件、异常处理器和路由；
- 每项测试结束后由数据库 fixture 清理数据。

不应在普通集成测试中重复创建 `TestClient(app)`。

测试自定义临时 FastAPI 应用时可以独立使用 `TestClient`，例如专门验证异常处理器行为。

## api_assertions

`ApiAssertions` 提供统一断言。

### 状态和响应体

```python
payload = api_assertions.assert_status(response, 201)
assert payload["title"] == "Movie"
```

状态码不匹配时，断言消息会包含实际响应正文，便于定位失败原因。

对于 `204 No Content`，返回值为 `None`。

### 标准错误

```python
payload = api_assertions.assert_error(
    response,
    status_code=404,
    code="MEDIA_NOT_FOUND",
)
```

该断言同时验证：

- HTTP 状态码；
- `error.code`；
- 响应头与响应体中的 `request_id` 一致；
- 错误响应包含请求路径。

### 参数校验错误

```python
api_assertions.assert_validation_error(
    response,
    ["body", "title"],
)
```

用于验证 B07 的字段错误位置。

## model_factory

`ModelFactory` 用于快速创建已提交到测试数据库的模型。

### 创建影视

```python
media = model_factory.media(
    title="Factory Movie",
    release_year=2024,
)
```

### 创建本地资源

```python
resource = model_factory.local_resource(media=media)
```

工厂只登记数据库记录，不创建真实视频文件。需要播放文件时，测试应在允许的测试目录内显式创建文件。

### 创建下载任务

```python
task = model_factory.download_task(media=media)
```

工厂不会启动后台下载线程。

### 创建观看历史

```python
history = model_factory.watch_history(
    media=media,
    resource=resource,
    position_seconds=60,
)
```

所有工厂方法：

- 提供合法默认值；
- 允许关键字参数覆盖；
- 自动提交并刷新模型；
- 使用随机值避免唯一约束冲突。

## integration 标记

集成测试使用：

```python
pytestmark = pytest.mark.integration
```

`pyproject.toml` 开启了 `--strict-markers`，拼写错误或未登记的标记会直接导致测试失败。

只运行集成测试：

```powershell
uv run pytest -m integration
```

排除集成测试：

```powershell
uv run pytest -m "not integration"
```

运行完整测试：

```powershell
uv run pytest
```

## 示例测试

`tests/integration/test_media_flow.py` 提供两个基础示例：

1. 通过 HTTP 完成影视新增、搜索、修改、删除和错误检查；
2. 使用数据工厂创建影视、资源和历史，再通过 API 查询。

第一个示例展示纯黑盒 API 流程，第二个示例展示“工厂准备数据 + API 验证结果”的组合方式。

## 测试边界

集成测试适合验证：

- 路由与状态码；
- 请求和响应 Schema；
- 数据库写入与查询；
- 中间件和请求 ID；
- 统一异常响应；
- 多个模块之间的关联行为。

以下场景更适合单元测试：

- 纯字符串解析；
- 文件名处理；
- Range 数学计算；
- 不需要 HTTP 和数据库的业务函数。

外部网络、真实下载器和 FFmpeg 应使用可控替身，不能让普通测试依赖互联网或本机工具。

## 编写约定

- 一个测试只验证一条清晰业务链路；
- 测试之间不得依赖执行顺序；
- 使用 `model_factory` 准备前置数据；
- 使用 `api_assertions` 检查标准响应；
- 禁止连接开发或生产数据库；
- 禁止在集成测试中启动真实下载线程；
- 测试失败时应保留足够的状态码、正文和请求 ID 信息；
- 新增主要 API 时，应至少增加成功和关键失败场景。

## 后续扩展

后续可以基于该框架逐项增加：

- 影视 API 完整集成测试；
- 本地资源扫描测试；
- 观看历史测试；
- 下载任务替身和状态流转测试；
- 文件上传或播放测试；
- 身份认证后的客户端 fixture。
