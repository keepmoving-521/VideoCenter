# R03：根据 URL 自动选择解析器

R03 为解析器注册器增加正式的 URL 路由规则。调用方只需提交影视资源页面地址，不需要了解具体应使用哪个站点解析器。

## 解析器声明域名

具体解析器通过 `supported_hosts` 声明支持的域名：

```python
class ExampleParser(ResourceParser):
    name = "example"
    priority = 100
    supported_hosts = ("example.com", "example-video.com")
```

域名声明会自动匹配其子域名，例如 `example.com` 同时匹配：

- `example.com`
- `www.example.com`
- `m.example.com`

不会错误匹配 `example.com.attacker.test` 之类的相似域名。

## 选择顺序

注册器按以下顺序选择解析器：

1. 找出声明域名且与 URL 域名匹配的解析器。
2. 按 `priority` 从高到低调用其 `supports()`。
3. 如果没有域名解析器可用，再尝试未声明域名的通用解析器。
4. 没有任何解析器支持时抛出错误码为 `UNSUPPORTED_WEBSITE` 的
   `UnsupportedWebsiteError`；旧名称 `ParserNotFoundError` 继续兼容。

域名解析器优先于通用解析器，即使通用解析器的数值优先级更高，避免宽泛规则抢占专用站点解析器。

## 调用方式

只选择解析器：

```python
parser = registry.select_url("https://www.example.com/movie/1")
```

自动选择并解析：

```python
result = await registry.parse_url(
    "https://www.example.com/movie/1",
    preferred_language="zh-CN",
)
```

## URL 规范化

进入选择流程前会统一处理 URL：

- 协议和域名转换为小写。
- 国际化域名转换为 IDNA 格式。
- 移除 HTTP 80、HTTPS 443 默认端口。
- 移除页面片段 `#fragment`。
- 空路径规范化为 `/`。
- 拒绝包含用户名、密码或非法端口的地址。

本次迭代不修改数据库结构，不需要新增 Alembic 迁移。
