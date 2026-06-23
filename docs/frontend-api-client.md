# W03：封装后端 API 请求

前端通过 `frontend/src/api/client.ts` 统一访问 FastAPI 后端。业务模块不应直接调用
`fetch`，而应复用导出的 `apiClient`。

## 默认配置

```dotenv
VITE_API_BASE_URL=/api/v1
VITE_API_TIMEOUT_MS=15000
```

- `VITE_API_BASE_URL`：API 基础地址，默认 `/api/v1`；
- `VITE_API_TIMEOUT_MS`：默认请求超时，单位为毫秒；
- 开发环境中的 `/api` 请求继续由 Vite 代理到 FastAPI。

## 基本用法

```typescript
import { apiClient } from "./client";

interface MediaDetail {
  id: number;
  title: string;
}

export function getMedia(mediaId: number) {
  return apiClient.get<MediaDetail>(`/media/${mediaId}`);
}

export function createMedia(payload: { title: string }) {
  return apiClient.post<MediaDetail>("/media", payload);
}
```

客户端提供 `get`、`post`、`put`、`patch`、`delete` 和底层 `request` 方法。

## 查询参数

`query` 会忽略 `null` 和 `undefined`，数组会转换成重复参数：

```typescript
apiClient.get("/media", {
  query: {
    page: 1,
    page_size: 20,
    status: ["downloaded", "ready"],
  },
});
```

## 请求体

普通对象会自动序列化成 JSON，并设置 `Content-Type: application/json`。字符串、
`FormData`、`Blob`、`URLSearchParams` 和二进制请求体会原样发送。

```typescript
apiClient.patch(`/media/${mediaId}`, {
  title: "新标题",
  is_favorite: true,
});
```

## 响应类型

默认根据响应 `Content-Type` 自动选择 JSON 或文本解析。可通过 `responseType` 显式指定：

```typescript
apiClient.get<string>("/stream/subtitles/1", {
  responseType: "text",
});

apiClient.get<Blob>("/media/1/poster", {
  responseType: "blob",
});
```

`204 No Content` 和 `205 Reset Content` 会返回 `undefined`。需要直接处理原始响应时使用
`responseType: "response"`。

## 错误处理

后端标准错误会转换为 `ApiError`：

```typescript
import { ApiError, apiClient } from "./client";

try {
  await apiClient.get("/media/999");
} catch (error) {
  if (error instanceof ApiError) {
    console.error(error.code);
    console.error(error.message);
    console.error(error.requestId);
  }
}
```

`ApiError` 包含：

| 属性 | 说明 |
| --- | --- |
| `status` | HTTP 状态码；网络错误和超时为 `0` |
| `code` | 后端稳定错误码或前端错误码 |
| `message` | 可展示的错误消息 |
| `details` | 后端附加错误详情 |
| `requestId` | 请求追踪 ID |
| `path` | 后端记录的请求路径 |

超时会抛出 `ApiTimeoutError`，无法连接后端会抛出 `ApiNetworkError`。调用方主动取消请求
时保留浏览器原始取消异常，便于业务区分用户取消与网络失败。

## 请求追踪

客户端默认给每个请求生成 `X-Request-ID`。如果调用方已经提供该请求头，则保留调用方的
值。服务端错误响应中的请求 ID 会写入 `ApiError.requestId`，便于排查日志。

## 自定义客户端

上传、长耗时任务或测试场景可以创建独立客户端：

```typescript
const longTaskClient = new ApiClient({
  baseUrl: "/api/v1",
  timeoutMs: 60_000,
});
```

单次请求的 `timeoutMs` 优先于客户端默认值。
