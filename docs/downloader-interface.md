# D01：下载器统一接口

D01 定义“下载地址 → 本地文件”的统一扩展契约。本次迭代只建立接口和标准数据结构，
不替换当前 HTTP 下载任务实现，也不增加数据库字段。

## 核心对象

| 对象 | 作用 |
| --- | --- |
| `DownloadRequest` | 下载输入，包含地址、目标路径、请求头、超时和分块大小 |
| `Downloader` | 所有下载器必须实现的抽象基类 |
| `DownloadProgress` | 标准进度信息 |
| `DownloadResult` | 下载完成后的标准结果 |
| `DownloadCancellationToken` | 线程安全的协作式取消令牌 |
| `DownloadError` | 下载器异常基类 |
| `DownloadCancelledError` | 下载被取消时的标准异常 |

接口位于 `src/videocenter/services/downloaders/`。

## 实现下载器

```python
from videocenter.services.downloaders import (
    DownloadProgress,
    DownloadProgressState,
    DownloadResult,
    Downloader,
)


class ExampleDownloader(Downloader):
    name = "example"
    priority = 100

    def download(
        self,
        request,
        *,
        progress_callback=None,
        cancellation_token=None,
    ):
        if cancellation_token is not None:
            cancellation_token.raise_if_cancelled()

        # 执行实际下载，并在分块写入后报告进度。
        if progress_callback is not None:
            progress_callback(
                DownloadProgress(
                    state=DownloadProgressState.DOWNLOADING,
                    downloaded_bytes=1024,
                    total_bytes=2048,
                )
            )

        return DownloadResult(
            target_path=request.target_path,
            file_size=2048,
            mime_type="video/mp4",
        )
```

## 契约约定

- `supports()` 只判断下载器能否处理请求，不应开始下载。
- `download()` 是阻塞方法，由任务调度层决定在线程或进程中执行。
- 下载器应通过 `progress_callback` 报告进度。
- 长时间操作应定期调用 `cancellation_token.raise_if_cancelled()`。
- 下载成功必须返回 `DownloadResult`，失败应抛出 `DownloadError` 的子类。
- 下载地址仅允许 HTTP/HTTPS，且不能包含用户名或密码。

当前默认 `supports()` 根据 `supported_schemes` 判断，后续下载器可以覆盖该方法，
加入域名、资源格式或运行环境检查。

本次迭代不修改数据库结构，不需要新增 Alembic 迁移。
