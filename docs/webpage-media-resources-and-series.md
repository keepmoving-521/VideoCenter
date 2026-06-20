# R11-R14：视频、清晰度、字幕与电视剧季集解析

本次迭代扩展通用网页解析器，使解析结果不仅包含影片资料，也能表达可下载媒体资源和电视剧层级。

## R11-R13 媒体资源

支持的数据来源：

- JSON-LD `contentUrl`、`video`、`associatedMedia` 和 `encoding`；
- HTML5 `<video src>` 与 `<source src>`；
- Open Graph `og:video`、`og:video:secure_url`；
- HTML5 `<track kind="subtitles/captions">`；
- JSON-LD `subtitle/subtitles/caption/captions`；
- `subtitle`、`video:subtitle` 等普通 meta。

视频清晰度可来自：

- JSON-LD `videoQuality`、`quality`、`height`；
- HTML `data-quality`、`label`、`res`、`height`；
- Open Graph `og:video:height`。

同一资源类型下的相同 URL 会自动去重。播放器嵌入地址 `embedUrl` 不会作为下载地址，因为它通常是播放页面而不是可直接下载的媒体文件。

字幕使用 `ParsedResourceType.SUBTITLE`，并尽量保留：

- 字幕语言；
- 标签名称；
- MIME 类型；
- 绝对下载地址。

## R14 电视剧季集

JSON-LD 中的以下结构会转换为标准层级：

```text
TVSeries
└── containsSeason / season
    └── episode / episodes
        └── video / contentUrl / subtitle
```

解析结果新增：

- `ParseResult.season_count`：页面声明的季总数；
- `ParsedSeason.episode_count`：页面声明的分集总数；
- `ParseResult.seasons`：实际解析出的季；
- `ParsedSeason.episodes`：实际解析出的分集；
- `ParsedEpisode.downloads`：该集的视频清晰度和字幕。

声明总数不能小于实际解析出的对象数量。缺少季号或集号时，会按页面出现顺序从 1 开始生成；缺少分集标题时生成“第 N 集”。

## 限制

通用解析器只处理页面中直接公开的资源地址，不执行 JavaScript、不解密媒体地址，也不绕过登录、DRM、付费或访问控制。

本次迭代不修改数据库结构，不需要新增 Alembic 迁移或第三方依赖。
