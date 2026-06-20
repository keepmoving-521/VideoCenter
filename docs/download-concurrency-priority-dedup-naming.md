# D12～D15：并发数、任务优先级、重复检测与文件名规则

## 并发下载数量

下载队列使用固定工作线程数量：

```env
VIDEOCENTER_DOWNLOAD_WORKER_COUNT=1
```

允许范围为 `1～16`。修改后需要重启应用。每个工作线程同一时间执行一个下载任务，
因此该值就是最大并发下载数量。

## 下载任务优先级

创建任务时可传入 `priority`：

```json
{
  "source_url": "https://example.com/movie.mp4",
  "priority": 50
}
```

- 允许范围为 `-100～100`，默认值为 `0`。
- 数值越大，越先从等待队列中取出。
- 相同优先级按照入队顺序执行。
- 已经开始下载的任务不会被后来创建的高优先级任务抢占。

## 防止重复下载

创建任务前会规范化下载地址，并检查相同 `source_url` 的任务。

只要已有任务不是 `cancelled`，新请求就返回 HTTP 409：

```json
{
  "error": {
    "code": "DOWNLOAD_ALREADY_EXISTS",
    "details": {
      "task_id": 12,
      "status": "completed"
    }
  }
}
```

失败任务应使用重试接口，已取消任务则允许重新创建。

## 自动目标文件名

`target_name` 现在是可选字段。未提供时按以下规则生成：

1. 已关联影视时，使用影视标题作为可读名称。
2. 未关联影视时，使用下载 URL 中的文件名。
3. URL 没有文件名时使用 `download`。
4. 追加下载地址 SHA-256 的前 10 位，避免不同链接产生相同文件名。
5. 保留 URL 中安全的扩展名。
6. 替换 Windows 非法文件名字符，最终长度不超过 512。

示例：

```text
My Great Movie-a1b2c3d4e5.mp4
```

显式传入 `target_name` 时仍使用用户指定名称，并执行原有安全校验。

## 数据迁移

迁移 `ce532e7c91a4` 新增 `priority` 字段、范围约束和索引：

```powershell
uv run alembic upgrade head
```
