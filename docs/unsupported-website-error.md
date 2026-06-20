# R04：不支持网站的错误处理

R04 为资源解析流程增加统一的“不支持网站”业务异常。当 URL 合法，但没有任何已注册解析器能够处理其网站时，抛出 `UnsupportedWebsiteError`。

## 错误协议

通过 FastAPI 返回时使用 HTTP 400 和统一错误结构：

```json
{
  "error": {
    "code": "UNSUPPORTED_WEBSITE",
    "message": "暂不支持网站：unsupported.example",
    "details": {
      "hostname": "unsupported.example",
      "supported_hosts": [
        "example.com"
      ]
    }
  },
  "meta": {
    "request_id": "请求追踪 ID",
    "timestamp": "错误发生时间",
    "path": "请求路径"
  }
}
```

客户端应通过稳定代码 `UNSUPPORTED_WEBSITE` 判断错误类型。`supported_hosts` 可用于提示用户当前能够解析的网站。

## 安全处理

错误响应只公开目标域名，不回显完整资源 URL。这样可以避免 URL 查询参数中的访问令牌、会话信息或其他隐私数据进入响应。

异常对象内部仍保留：

- `source_url`：规范化后的完整地址，供服务端日志使用；
- `hostname`：目标域名；
- `supported_hosts`：注册器当前声明支持的域名。

## 兼容性

早期版本使用的 `ParserNotFoundError` 仍然保留，并继承自 `UnsupportedWebsiteError`。旧代码捕获 `ParserNotFoundError` 时无需修改；新业务代码可以统一捕获 `UnsupportedWebsiteError`。

本次迭代不修改数据库结构，不需要新增 Alembic 迁移。
