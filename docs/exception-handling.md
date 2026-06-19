# B05：统一异常处理

本文档说明 VideoCenter 的业务异常体系、全局异常处理和错误响应格式。

## 实现目标

统一异常处理负责：

- 将服务端异常转换为稳定的 HTTP 错误响应；
- 统一处理业务异常、HTTP 异常和参数校验错误；
- 捕获数据库异常和未知异常；
- 生产环境隐藏内部实现细节；
- 使用统一日志记录请求路径、状态码和错误代码；
- 避免在每个路由中重复编写异常响应逻辑。

本次只统一错误响应。成功响应的统一包装属于后续 `B06`。

## 错误响应结构

所有被全局处理器捕获的异常返回：

```json
{
  "error": {
    "code": "MEDIA_NOT_FOUND",
    "message": "影视条目不存在",
    "details": null
  }
}
```

字段说明：

| 字段 | 说明 |
| --- | --- |
| `code` | 稳定的机器可读错误代码 |
| `message` | 面向用户或调用方的错误说明 |
| `details` | 可选的结构化错误详情 |

调用方应优先依据 `code` 处理错误，不应依赖中文消息文本。

## 业务异常

基础异常定义在：

```text
src/videocenter/core/exceptions.py
```

当前提供：

- `AppException`：业务异常基类；
- `BadRequestError`：错误请求，状态码 400；
- `NotFoundError`：资源不存在，状态码 404；
- `ConflictError`：资源状态冲突，状态码 409。

示例：

```python
from videocenter.core.exceptions import NotFoundError

raise NotFoundError(
    "影视条目不存在",
    code="MEDIA_NOT_FOUND",
)
```

业务异常与 FastAPI 解耦，因此服务层可以直接使用，不需要导入 `HTTPException`。

## 已处理的异常类型

### AppException

返回异常中声明的状态码、业务错误代码、消息和详情。

### RequestValidationError

请求参数、路径参数或请求体校验失败时返回：

```json
{
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "请求参数校验失败",
    "details": [
      {
        "type": "greater_than_equal",
        "loc": ["query", "limit"],
        "msg": "Input should be greater than or equal to 1"
      }
    ]
  }
}
```

### HTTPException

兼容现有路由抛出的 FastAPI/Starlette HTTP 异常，错误代码格式为：

```text
HTTP_404
HTTP_403
HTTP_416
```

后续业务代码建议逐步改用业务异常，以获得更精确的错误代码。

### SQLAlchemyError

数据库异常返回：

```json
{
  "error": {
    "code": "DATABASE_ERROR",
    "message": "数据库操作失败",
    "details": null
  }
}
```

异常堆栈会写入服务端日志。

### 未知异常

未被其他处理器匹配的异常返回状态码 500：

```json
{
  "error": {
    "code": "INTERNAL_SERVER_ERROR",
    "message": "服务器内部错误",
    "details": null
  }
}
```

## 开发和生产环境差异

当 `VIDEOCENTER_DEBUG=true` 时，数据库和未知异常的 `details` 会包含异常文本，方便本地调试。

生产环境强制关闭 Debug，因此不会向客户端暴露：

- 数据库语句；
- 文件系统路径；
- 内部异常文本；
- Python 堆栈信息。

完整堆栈仍会记录到服务端日志。

## 日志内容

异常处理器会记录以下上下文：

- `error_code`
- `status_code`
- `request_method`
- `request_path`

数据库异常和未知异常使用 `logger.exception()`，保留完整异常堆栈。

## 错误代码命名建议

业务错误代码使用大写下划线格式：

```text
MEDIA_NOT_FOUND
DOWNLOAD_TASK_NOT_FOUND
LOCAL_RESOURCE_NOT_FOUND
DOWNLOAD_ALREADY_EXISTS
UNSUPPORTED_SOURCE_URL
```

同一个错误场景应长期保持相同的错误代码。

## 后续开发约定

- 服务层优先抛出 `AppException` 子类；
- 路由层不要捕获后重新包装未知异常；
- 只有能够明确恢复或转换语义时才捕获异常；
- 禁止把原始数据库异常直接返回给客户端；
- 新增业务异常时应增加对应测试；
- B06 可以在当前错误结构基础上设计统一 API 响应格式。
