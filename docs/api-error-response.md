# B06：统一 API 错误响应格式

本文档定义 VideoCenter API 对外提供的标准错误协议。

## 标准结构

所有 API 错误使用以下结构：

```json
{
  "error": {
    "code": "MEDIA_NOT_FOUND",
    "message": "影视条目不存在",
    "details": null
  },
  "meta": {
    "request_id": "f95a4a68bb754237aa01e766790ccdb7",
    "timestamp": "2026-06-19T12:00:00Z",
    "path": "/api/v1/media/100"
  }
}
```

错误主体和响应元数据分别由以下 Pydantic 模型定义：

```text
ErrorDetail
ErrorMeta
ErrorResponse
```

模型位于 `src/videocenter/schemas/error.py`。

## error 字段

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `code` | string | 稳定的机器可读错误代码 |
| `message` | string | 可展示给用户的错误信息 |
| `details` | any/null | 参数错误或调试信息等附加详情 |

客户端业务判断必须使用 `code`，不能依赖 `message`。

## meta 字段

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `request_id` | string | 请求追踪标识 |
| `timestamp` | datetime | UTC 错误响应时间 |
| `path` | string | 发生错误的请求路径 |

## 请求追踪 ID

每个请求都会获得请求 ID，并通过响应头返回：

```http
X-Request-ID: f95a4a68bb754237aa01e766790ccdb7
```

错误响应体中的 `meta.request_id` 与响应头完全一致。异常日志也会记录同一个 ID。

客户端可以主动传入 `X-Request-ID`。满足以下规则时服务端会保留该值：

- 长度为 8 到 128；
- 只能包含英文字母、数字、点、下划线和连字符。

无效或缺失的请求 ID 会被替换为服务端生成的 32 位 UUID。

成功响应也会包含 `X-Request-ID` 响应头，但不会改变原有响应体。

## 标准 HTTP 状态

OpenAPI 为所有接口统一声明以下错误响应：

| 状态码 | 场景 |
| --- | --- |
| 400 | 请求参数或业务请求错误 |
| 404 | 请求的资源不存在 |
| 409 | 资源状态冲突 |
| 422 | Pydantic 请求校验失败 |
| 500 | 数据库或未知服务端异常 |

具体业务错误仍通过 `error.code` 进一步区分。

## OpenAPI

`ErrorResponse` 已注册到 OpenAPI components 中。Swagger 页面会在接口错误响应中展示统一模型。

前端可以根据 OpenAPI 自动生成对应类型，无需为每个接口单独定义错误结构。

## 前端处理建议

```javascript
const payload = await response.json();

if (!response.ok) {
  console.error(payload.error.code, payload.meta.request_id);
  showMessage(payload.error.message);
}
```

如果用户报告错误，界面应同时展示或复制 `request_id`，便于从服务端日志定位请求。

## 与 B05 的边界

- B05 负责异常分类、捕获、安全隐藏和日志记录；
- B06 负责响应协议、请求追踪、Pydantic 模型和 OpenAPI 声明；
- 成功响应体保持现状，不在本次迭代中统一包装。
