# R15-R17：资源预解析、确认与保存

本次迭代打通资源页面进入影视库的完整流程。

## API 流程

### 1. 预解析

```http
POST /api/v1/parsing/preview
```

```json
{
  "source_url": "https://example.com/movie/1",
  "preferred_language": "zh-CN"
}
```

响应包含标准解析结果、`preview_id` 和过期时间。预解析结果默认保留 30 分钟。

### 2. 确认解析结果

```http
POST /api/v1/parsing/confirm
```

客户端可以修改标题、简介、年份、标签和季集等字段，再提交完整结果：

```json
{
  "preview_id": "预解析令牌",
  "result": {
    "...": "修改后的完整 ParseResult"
  }
}
```

来源页面地址不能在确认阶段修改。确认成功后返回 `confirmation_id`。

### 3. 保存入库

```http
POST /api/v1/parsing/save
```

```json
{
  "confirmation_id": "确认令牌"
}
```

保存操作在一个数据库事务中创建：

- 影片；
- 新标签及影片标签关联；
- 电视剧季；
- 电视剧分集。

相同来源页面不能重复保存，错误码为 `PARSED_MEDIA_ALREADY_EXISTS`。确认令牌成功保存后即失效，重复使用返回 `PARSE_CONFIRMATION_ALREADY_USED`。

## 下载资源边界

响应会统计解析出的影片级和分集级视频、字幕数量。当前迭代不会自动创建或启动下载任务，因为下载清晰度选择、字幕保存位置以及分集下载任务关联将在下载模块后续迭代处理。

## 运行方式

预解析和确认令牌当前保存在应用进程内存中，适合当前单机私人部署。应用重启或多进程部署时令牌不会共享；未来如需多实例运行，应将工作流状态迁移到数据库或 Redis。

本次迭代不修改数据库结构，不需要新增 Alembic 迁移。
