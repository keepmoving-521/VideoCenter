# R01：资源解析器统一接口

R01 定义“影视资源页面地址 → 标准影视数据”的扩展契约。本迭代只提供基础接口和注册机制，不包含任何具体网站解析实现。

## 核心对象

| 对象 | 作用 |
| --- | --- |
| `ParseRequest` | 解析请求，包含资源页面地址和首选语言 |
| `ResourceParser` | 所有站点解析器必须实现的抽象基类 |
| `ParseResult` | 标准影片解析结果 |
| `ParsedSeason` | 标准季信息 |
| `ParsedEpisode` | 标准分集信息 |
| `ParsedDownload` | 可下载视频资源 |
| `ParserRegistry` | 注册解析器并按优先级选择匹配实现 |

接口位于 `src/videocenter/services/parsers/`。

## 实现解析器

```python
from videocenter.services.parsers import ParseRequest, ParseResult, ResourceParser


class ExampleParser(ResourceParser):
    name = "example"
    priority = 100

    def supports(self, request: ParseRequest) -> bool:
        return "example.com" in request.source_url

    async def parse(self, request: ParseRequest) -> ParseResult:
        return ParseResult(
            title="影片名称",
            source_site="Example",
            source_page_url=request.source_url,
        )
```

`supports()` 只判断地址是否适用，不应发送网络请求。`parse()` 是异步方法，可在后续实现中进行页面请求、接口访问和数据转换。

## 注册和调用

```python
registry = ParserRegistry()
registry.register(ExampleParser())

result = await registry.parse(
    ParseRequest(source_url="https://example.com/movie/1")
)
```

多个解析器都支持同一地址时，优先选择 `priority` 数值较大的解析器；优先级相同则按解析器名称排序。名称重复会拒绝注册，没有匹配实现时抛出 `ParserNotFoundError`。

解析结果支持影片、季、分集和下载地址的嵌套表达，同时保留 `extra` 字段承载暂未标准化的站点数据。

本次迭代不修改数据库结构，不需要新增 Alembic 迁移。
