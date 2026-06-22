# Q02：统一后台任务状态定义

系统为所有后台任务建立统一状态语义、流转规则和旧任务状态映射。后续任务列表、调度、
暂停、取消、重试和恢复功能都应使用本规范。

## 状态语义

| 状态 | 含义 |
| --- | --- |
| `waiting` | 已创建或重试后重新排队，尚未被执行者领取 |
| `running` | 已被执行者领取并正在工作 |
| `paused` | 保留进度但暂时停止，仅支持暂停的任务可进入 |
| `completed` | 成功完成，不再允许状态变化 |
| `failed` | 本次尝试失败；有剩余次数时可重新排队 |
| `cancelled` | 已取消，不再允许状态变化 |

`completed` 和 `cancelled` 是不可逆终态。`failed` 不是绝对终态，因为任务可能仍有重试
次数。

## 状态流转

```text
waiting ──> running ──> completed
   │            ├─────> failed ──> waiting
   │            ├─────> paused ──> running / waiting
   └────────────┴─────> cancelled
```

- 不允许从 `waiting` 直接完成或失败；
- 暂停必须满足 `pause_supported = true`；
- 取消必须满足 `cancellable = true`；
- `failed → waiting` 会增加 `attempt`，且不能超过 `max_attempts`；
- 重复设置相同状态是幂等操作。

统一状态流转服务会同步维护开始、完成、心跳、执行者、错误和取消请求字段。成功完成时将
进度设置为 `100`，并在已知总数量时将已处理数量设置为总数量。

## 旧状态映射

现有扫描、分析和 HLS 状态可以按同名值直接映射。下载状态中的 `downloading` 统一映射为
`running`，其余下载状态保持同名语义。

## 数据库

本次迭代没有修改数据库结构，不需要新增 Alembic 迁移。
