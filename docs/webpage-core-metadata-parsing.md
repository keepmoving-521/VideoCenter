# R06-R10：网页影片核心信息解析

本次迭代完善通用网页解析器对影片核心字段的提取。

## 字段与来源

| 需求 | 字段 | 优先来源 |
| --- | --- | --- |
| R06 | 标题 | JSON-LD `name/headline`、Open Graph、Twitter Card、普通 meta、HTML title |
| R07 | 简介 | JSON-LD `description`、Open Graph、Twitter Card、普通 description |
| R08 | 海报 | JSON-LD `image/thumbnailUrl`、Open Graph、Twitter Card、普通图片 meta |
| R09 | 上映年份 | JSON-LD 发布日期、release date/date/year meta |
| R10 | 演员和导演 | JSON-LD `actor/actors/director`、重复 actor/director/cast meta |

结构化 JSON-LD 数据优先于其他页面标签。演员和导演会合并多个来源、清理首尾空白并按大小写去重。

## 上映年份

解析结果新增独立的 `release_year` 字段：

- 完整上映日期会同时生成对应年份；
- 只有年份时保留 `release_year`，`release_date` 为空；
- 年份范围为 1888～2100；
- 同时提供年份和日期时，两者必须一致；
- 不从页面标题中的数字猜测年份，避免把续集编号误识别为上映年份。

`ParseResult.to_media_values()` 会同时输出 `release_year` 和 `release_date`，可以直接用于影片数据入库。

## 海报地址

相对海报地址会根据网页最终响应地址转换为绝对 URL。例如：

```text
/images/poster.jpg
```

会转换为：

```text
https://example.com/images/poster.jpg
```

本次迭代不修改数据库结构，不需要新增 Alembic 迁移。
