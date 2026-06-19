# B07：请求参数校验

本文档说明 VideoCenter API 的输入校验规则与开发约定。

## 目标

请求进入业务逻辑和数据库之前，系统应尽早拒绝无效输入，从而避免：

- 无效 ID 引发无意义的数据库查询；
- 纯空格标题或文件名进入数据库；
- 未知字段因拼写错误被静默忽略；
- 播放位置超过视频总时长；
- 非法文件名影响下载文件安全；
- 超长或格式错误的请求头进入播放服务；
- `NaN`、`Infinity` 等非有限数字污染业务数据。

## 公共请求模型

请求模型统一继承：

```text
ApiRequestModel
```

定义在 `src/videocenter/schemas/common.py`，默认规则：

- 禁止请求体出现模型未声明的字段；
- 自动去除字符串首尾空白；
- 禁止 `NaN` 和正负无穷；
- 使用 Pydantic 生成 OpenAPI 约束。

项目还提供可复用类型：

- `PositiveId`：必须大于零的整数 ID；
- `NonBlankText`：去除首尾空格后不能为空；
- `ShortText`：长度为 1 到 255 的非空文本。

## ID 校验

所有路径参数和请求体中的实体 ID 必须大于零：

```text
media_id > 0
resource_id > 0
task_id > 0
```

无效 ID 返回 `VALIDATION_ERROR`，不会进入数据库查询。

## 影视信息

### 新增影视

- `title`：去除首尾空格后长度为 1～255；
- `original_title`：非空时长度为 1～255；
- `description`：最大 10000 字符，纯空格转换为空值；
- `release_year`：1888～2100；
- `poster_url`、`source_page_url`：仅接受 HTTP/HTTPS URL；
- 未声明字段直接拒绝。

### 更新影视

- 请求体至少包含一个待更新字段；
- `title` 和 `media_type` 不允许显式设置为 `null`；
- 其他字段遵循新增影视的相同限制。

## 列表查询

影视搜索参数：

- `query`：1～100 字符，不能只包含空白；
- `offset`：大于或等于零；
- `limit`：1～200。

## 下载任务

- `source_url`：必须是 HTTP/HTTPS URL；
- `media_id`：非空时必须大于零；
- `target_name`：去除首尾空格后长度为 1～255；
- 文件名禁止 `< > : " / \ | ? *`、控制字符和目录分隔符；
- 文件名不能以点或空格结尾。

下载目标只能是文件名，不能通过请求传入相对目录或绝对路径。

## 本地扫描

- `media_id`：非空时必须大于零；
- `path`：非空时长度为 1～2048；
- 路径禁止包含空字符；
- Schema 校验后，服务层仍会检查路径是否位于媒体根目录内。

这里采用“双层校验”：Schema 负责格式，服务层负责文件系统权限和业务边界。

## 观看历史

- `media_id`、`resource_id`：必须大于零；
- `position_seconds`、`duration_seconds`：必须是有限且非负的数字；
- 已知总时长时，播放位置不能超过总时长；
- 本地资源若已绑定影视条目，必须与请求中的 `media_id` 一致。

## 视频 Range 请求

- `resource_id` 必须大于零；
- `Range` 请求头最长 128 字符；
- 只接受单个 `bytes=start-end` 范围；
- 支持续传形式 `bytes=100-`；
- 支持尾部范围 `bytes=-100`；
- 多范围请求会在参数校验阶段拒绝。

## 校验错误响应

所有输入错误使用 B06 标准响应：

```json
{
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "请求参数校验失败",
    "details": [
      {
        "type": "greater_than",
        "loc": ["path", "media_id"],
        "msg": "Input should be greater than 0",
        "input": "0"
      }
    ]
  },
  "meta": {
    "request_id": "request-id",
    "timestamp": "2026-06-19T12:00:00Z",
    "path": "/api/v1/media/0"
  }
}
```

`details[].loc` 用于确定错误来自路径、查询、请求头或请求体。

## 开发约定

- 格式、长度、类型等规则放在 Schema；
- 数据是否存在、资源归属等规则放在业务层；
- 不要在路由中重复手写已有的公共约束；
- 新增字段时同步添加边界测试；
- 确保约束能出现在 OpenAPI 中；
- 不应仅依赖前端校验，服务端始终执行完整校验。
