# M01：完善影视资源字段

本文档说明 VideoCenter 影视条目核心字段的扩展、校验和数据库迁移。

## 需求边界

M01 聚焦描述影视作品本身的基础字段：

- 排序标题；
- 影视别名；
- 精确上映日期；
- 内容分级。

以下字段属于后续独立需求，本次没有提前实现：

- 资源状态（M02）；
- 影视类型扩展（M03）；
- 来源网站（M04）；
- 演员、导演（M06）；
- 地区、语言、类别（M07）；
- 时长和评分（M08）；
- 海报与背景图扩展（M09）。

## 新增字段

### sort_title

用于列表排序的规范标题：

```json
{
  "title": "The Matrix",
  "sort_title": "Matrix, The"
}
```

数据库类型为 `VARCHAR(255)`，允许为空，并创建普通索引：

```text
ix_media_sort_title
```

后续实现影视排序时，可以优先使用 `sort_title`，为空时回退到 `title`。

### alternative_titles

保存影视作品的其他译名、简称和发行名称：

```json
{
  "alternative_titles": [
    "骇客任务",
    "22世纪杀人网络"
  ]
}
```

数据库使用 JSON 列，API 使用字符串数组。

规则：

- 默认值为空数组；
- 最多 50 个别名；
- 单个别名去除首尾空格后不能为空；
- 单个别名最长 255 个字符；
- 使用不区分大小写的方式去重；
- 保留首次出现的书写形式和顺序。

例如：

```json
["Alias", " alias ", "第二片名"]
```

最终保存为：

```json
["Alias", "第二片名"]
```

### release_date

保存精确上映日期，格式为 ISO 8601：

```json
{
  "release_date": "2024-05-20"
}
```

数据库类型为 `DATE`。

原有 `release_year` 继续保留，用于只有年份而没有精确日期的数据。当提供 `release_date` 时：

- 未提供 `release_year`：自动从日期提取年份；
- 同时提供且年份一致：接受；
- 同时提供但年份不一致：返回参数校验错误。

更新精确日期时也会同步更新上映年份。

### content_rating

保存作品内容分级，例如：

```text
G
PG
PG-13
R
TV-MA
辅12级
```

数据库类型为 `VARCHAR(32)`，允许为空。API 会去除首尾空格，非空值最长 32 个字符。

内容分级体系因国家和地区不同，本字段暂时保存原始文本，不强制限定为某个枚举。

## API 示例

创建影视条目：

```http
POST /api/v1/media
Content-Type: application/json
```

```json
{
  "title": "The Matrix",
  "sort_title": "Matrix, The",
  "original_title": "The Matrix",
  "alternative_titles": [
    "黑客帝国",
    "骇客任务"
  ],
  "media_type": "movie",
  "release_date": "1999-03-31",
  "content_rating": "R"
}
```

响应会同时返回：

```json
{
  "release_year": 1999,
  "release_date": "1999-03-31"
}
```

更新字段：

```http
PATCH /api/v1/media/{media_id}
```

```json
{
  "sort_title": "Matrix, The",
  "alternative_titles": ["黑客帝国"],
  "content_rating": "R"
}
```

将可空字段设置为 `null` 可以清空该字段。`alternative_titles` 是非空数组字段，清空时应传入：

```json
{
  "alternative_titles": []
}
```

## Schema 到数据库的类型转换

请求 Schema 使用 Python `date` 保存上映日期，SQLAlchemy `Date` 列要求接收日期对象。

影视 Schema 提供 `to_model_values()`：

- 保留 `release_date` 为 Python `date`；
- 将 `HttpUrl` 字段单独转换为字符串；
- 避免使用 JSON 模式序列化导致日期变成字符串。

## 数据库迁移

迁移版本：

```text
Revision ID: 027f97ab3db2
Parent: 81fd73d3a90a
```

迁移文件：

```text
migrations/versions/027f97ab3db2_expand_media_core_fields.py
```

升级：

```powershell
uv run alembic upgrade head
```

迁移为已有影视记录自动写入：

```json
[]
```

作为 `alternative_titles` 默认值，因此旧数据无需人工补全即可升级。

降级：

```powershell
uv run alembic downgrade 81fd73d3a90a
```

降级会删除 M01 新增的四个字段及排序标题索引，相关数据会丢失，执行前必须备份。

## 验证

M01 包含以下验证：

- 核心字段创建和更新 API 集成测试；
- 别名去重、长度和空值校验；
- 上映日期和年份一致性校验；
- URL 与日期数据库类型转换测试；
- 旧影视记录迁移后数据保留测试；
- 迁移升级和降级测试；
- Alembic 模型一致性检查。
