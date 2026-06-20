# R05：通用网页基础信息解析

R05 增加低优先级的 `GenericWebPageParser`。当 URL 没有专用网站解析器时，它可以从普通 HTML 页面提取影视条目的基础信息。

## 支持的数据来源

解析优先级如下：

1. Schema.org JSON-LD；
2. Open Graph；
3. Twitter Card；
4. 标准 HTML 标题和 description。

当前可提取：

- 标题和简介；
- 网站名称和规范页面地址；
- 影视类型；
- 上映日期；
- 上映年份；
- 导演、演员和类别；
- 时长和评分；
- 海报地址。

JSON-LD 支持 `Movie`、`TVSeries`、`CreativeWorkSeries`、`VideoObject` 和 `Episode` 等常见类型。相对规范链接和图片地址会转换为绝对地址。

## 默认注册器

```python
from videocenter.services.parsers import create_default_parser_registry

registry = create_default_parser_registry()
result = await registry.parse_url("https://example.com/movie/1")
```

通用解析器的优先级为 `-100`，且不声明固定域名。因此，未来加入的专用网站解析器会优先执行，只有专用解析器不匹配时才使用通用解析。

## 网页获取限制

内置获取器：

- 请求超时为 20 秒；
- 最大读取 2 MiB；
- 只接受 HTML/XHTML；
- 使用独立的 VideoCenter User-Agent；
- 根据响应字符集解码，无法解码的字符会安全替换。

解析器构造函数允许注入异步网页获取器，便于测试以及未来替换代理、缓存或限流实现。

本次迭代不修改数据库结构，不需要新增 Alembic 迁移，也不新增第三方依赖。

标题、简介、海报、上映年份以及演职员的详细候选字段和优先级参见
[R06-R10 网页影片核心信息解析](webpage-core-metadata-parsing.md)。

视频下载地址、多清晰度、字幕以及电视剧季集结构参见
[R11-R14 网页媒体资源与季集解析](webpage-media-resources-and-series.md)。
