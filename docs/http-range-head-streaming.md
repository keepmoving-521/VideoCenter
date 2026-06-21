# P01～P02：HTTP Range 与视频 HEAD 请求

在线播放接口支持标准单段 HTTP Range 请求，并提供 HEAD 请求用于播放器预检。

## 完整视频请求

```http
GET /api/v1/stream/{resource_id}
```

未提供 `Range` 时返回 `200 OK` 和完整文件。

## 单段 Range

支持以下形式：

```http
Range: bytes=0-1048575
Range: bytes=1048576-
Range: bytes=-1048576
```

分别表示：

- 指定开始和结束位置；
- 从指定位置读取到文件末尾；
- 读取文件末尾指定字节数。

合法请求返回 `206 Partial Content`，响应包含：

- `Accept-Ranges: bytes`
- `Content-Range`
- 当前区间的 `Content-Length`
- `ETag`
- `Last-Modified`

结束位置超过文件大小时会自动收缩到文件末尾。

多段 Range、格式错误、开始位置越界以及空文件 Range 请求返回：

```http
416 Range Not Satisfiable
Content-Range: bytes */{file_size}
```

当前版本明确不支持逗号分隔的多段 Range。

## HEAD 请求

```http
HEAD /api/v1/stream/{resource_id}
```

HEAD 不读取和返回视频正文，但会返回与 GET 一致的：

- HTTP 状态；
- MIME 类型；
- 文件或区间长度；
- Range 能力；
- 缓存校验信息。

HEAD 同样支持单段 `Range`。合法区间返回 `206`，无 Range 返回 `200`。

本次功能只调整在线播放协议处理，不涉及数据库迁移。
