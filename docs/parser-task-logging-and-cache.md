# R20-R21：解析任务日志与结果缓存

解析调度层现在为每次调用生成可追踪任务日志，并缓存成功的解析结果。

## 解析任务日志

预解析响应新增 `parse_task_id`，可用于关联服务端日志：

```json
{
  "parse_task_id": "32 位任务 ID",
  "preview_id": "预解析确认令牌",
  "expires_at": "过期时间",
  "result": {}
}
```

日志覆盖以下事件：

| `parse_event` | 含义 |
| --- | --- |
| `started` | 解析任务开始 |
| `attempt_started` | 单次尝试开始 |
| `retry` | 临时失败，即将重试 |
| `completed` | 解析成功 |
| `cache_hit` | 直接使用缓存结果 |
| `duplicate_wait` | 等待相同页面正在执行的解析任务 |
| `timeout` | 所有尝试均超时 |
| `failed` | 解析失败或重试耗尽 |

结构化字段包括任务 ID、解析器名称、目标域名、尝试次数、耗时和重试等待时间。日志不会记录完整资源 URL，避免查询参数中的令牌或隐私信息泄露。

## 解析结果缓存

缓存键由以下内容组成：

- 解析器名称；
- 规范化后的资源 URL；
- 首选语言。

只有成功结果会写入缓存。超时、网络失败和数据校验失败均不会缓存。

默认配置：

```env
VIDEOCENTER_PARSER_CACHE_ENABLED=true
VIDEOCENTER_PARSER_CACHE_TTL_SECONDS=1800
VIDEOCENTER_PARSER_CACHE_MAX_ENTRIES=500
```

缓存超过最大条目数时淘汰最久未使用的结果；读取过期结果时自动删除。

## 部署边界

当前缓存保存在应用进程内存中：

- 应用重启后缓存清空；
- 多进程之间不共享；
- 适合当前单机私人部署。

未来采用多实例部署时，可将缓存替换为 Redis，同时保持注册器调用接口不变。

相同页面并发解析的任务合并机制参见
[R22-R23 防止重复解析与解析器单元测试](duplicate-parsing-and-parser-tests.md)。

本次迭代不修改数据库结构，不需要新增 Alembic 迁移。
