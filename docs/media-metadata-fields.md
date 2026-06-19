# M02～M08：影视状态、类型、来源与元数据字段

本文档记录 M02 至 M08 的合并迭代。本次升级完善影视条目的生命周期、作品分类、来源信息、演职员、地区语言类别、时长和评分。

## M02：影视资源状态

新增 `status` 字段，表示影视条目在本地系统中的资源生命周期。

可选值：

| 值 | 说明 |
| --- | --- |
| `pending` | 已创建条目，尚未开始下载或入库 |
| `downloading` | 正在下载资源 |
| `available` | 已有可用的本地资源 |
| `missing` | 记录存在，但本地文件缺失 |
| `archived` | 已归档，不参与常规处理 |

默认值为 `pending`。数据库使用枚举列并建立 `ix_media_status` 索引。

示例：

```json
{
  "status": "available"
}
```

当前版本允许通过影视新增和更新接口直接设置状态。后续下载、本地扫描流程可以自动维护该字段。

## M03：影片类型

原有作品类型扩展为：

| 值 | 说明 |
| --- | --- |
| `movie` | 电影 |
| `series` | 电视剧或系列节目 |
| `documentary` | 纪录片 |
| `animation` | 动画作品 |
| `variety_show` | 综艺节目 |
| `short_film` | 短片 |
| `other` | 其他 |

数据库继续使用 `media_type` 字段和 `ix_media_media_type` 索引。

类型是作品的主要形态，与 M07 的 `genres` 不同。例如：

```json
{
  "media_type": "movie",
  "genres": ["科幻", "动作"]
}
```

## M04：影片来源网站

新增 `source_site` 字段，记录资源页面所属的网站或提供方名称：

```json
{
  "source_site": "Example Video"
}
```

规则：

- 可为空；
- 去除首尾空格；
- 长度不超过 100；
- 数据库建立 `ix_media_source_site` 索引。

该字段保存可读名称，不建议保存完整域名或 URL。

## M05：原始资源页面地址

原有 `source_url` 字段重命名为：

```text
source_page_url
```

新名称明确表示“用户输入、解析影视信息的原始网页地址”，与下载任务中的直接媒体地址 `DownloadTask.source_url` 区分。

示例：

```json
{
  "source_page_url": "https://example.com/videos/123"
}
```

规则：

- 必须是 HTTP 或 HTTPS URL；
- 数据库最大长度 2048；
- 迁移使用列重命名，现有 `source_url` 数据不会丢失。

为兼容旧客户端，请求体暂时仍接受旧字段名：

```json
{
  "source_url": "https://example.com/videos/123"
}
```

响应和后续新代码统一使用 `source_page_url`。

## M06：导演和演员

新增：

```text
directors
actors
```

API 示例：

```json
{
  "directors": ["导演甲", "导演乙"],
  "actors": ["演员甲", "演员乙"]
}
```

规则：

- 使用 JSON 字符串数组保存；
- 默认空数组；
- 导演最多 100 人；
- 演员最多 500 人；
- 单项去除首尾空格；
- 单项最大长度 255；
- 不区分大小写去重；
- 保留首次出现的顺序和书写形式。

本次采用 JSON 数组满足轻量级个人影视库需求。需要人物详情、头像和跨作品关联时，可以在后续迭代拆分为独立人物表。

## M07：地区、语言和类别

新增：

```text
regions
languages
genres
```

示例：

```json
{
  "regions": ["中国大陆", "美国"],
  "languages": ["汉语普通话", "英语"],
  "genres": ["剧情", "科幻"]
}
```

规则：

- 每个字段最多 50 项；
- 单项最大长度 100；
- 去除首尾空格；
- 不区分大小写去重；
- 默认空数组。

这里的 `genres` 表示题材类别；它与 M03 的单值作品类型相互独立。

## M08：影片时长和评分

新增：

```text
duration_minutes
rating
```

### 时长

`duration_minutes` 使用整数分钟：

```json
{
  "duration_minutes": 125
}
```

规则：

- 可为空；
- 必须大于 0；
- API 上限为 100000；
- 数据库约束 `ck_media_duration_positive` 防止绕过 API 写入无效值。

精确到秒的视频时长仍由 `LocalResource.duration_seconds` 保存。影视条目的分钟时长用于元数据展示，二者职责不同。

### 评分

`rating` 统一使用 0～10 分：

```json
{
  "rating": 8.6
}
```

规则：

- 可为空；
- 最小值 0；
- 最大值 10；
- 数据库约束 `ck_media_rating_range`。

本字段表示外部或综合评分。个人评分将在后续独立需求中实现。

## 完整请求示例

```http
POST /api/v1/media
Content-Type: application/json
```

```json
{
  "title": "示例纪录片",
  "media_type": "documentary",
  "status": "available",
  "source_site": "Example Video",
  "source_page_url": "https://example.com/videos/123",
  "directors": ["导演甲"],
  "actors": ["演员甲", "演员乙"],
  "regions": ["中国大陆"],
  "languages": ["汉语普通话"],
  "genres": ["纪录片", "科技"],
  "duration_minutes": 95,
  "rating": 8.6
}
```

## 数据库迁移

迁移版本：

```text
Revision ID: 8bcdd86d27ba
Parent: 027f97ab3db2
```

迁移文件：

```text
migrations/versions/8bcdd86d27ba_expand_media_metadata_fields.py
```

迁移行为：

- 旧影视条目状态设为 `PENDING`；
- JSON 列自动填充空数组；
- `source_url` 原地重命名为 `source_page_url`；
- 扩展 `media_type` 可选值；
- 创建状态和来源网站索引；
- 创建时长和评分数据库约束。

升级：

```powershell
uv run alembic upgrade head
```

降级：

```powershell
uv run alembic downgrade 027f97ab3db2
```

降级时：

- `source_page_url` 重命名回 `source_url`，地址数据保留；
- 新增作品类型统一转换为 `OTHER`；
- M02～M08 新增字段的数据会被删除。

执行降级前必须备份数据库。

## 验证

本次迭代验证：

- 全字段影视创建和更新 API；
- 状态和类型枚举；
- 来源页面旧字段别名兼容；
- 字符串列表清理和去重；
- 时长和评分范围校验；
- 旧来源 URL 迁移保留；
- 新字段默认值；
- 数据库索引和检查约束；
- 迁移升级与降级；
- Alembic 模型一致性。
