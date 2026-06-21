# F09～F11：视频文件类型与文件名识别

本次迭代为本地视频扫描增加文件名识别能力。系统不会自动创建或修改影视条目，
而是先将识别结果保存到本地资源，供后续自动匹配影片、季和分集功能使用。

## 识别内容

- 根据文件扩展名发现视频文件，并保存 MIME 类型。
- 普通视频默认识别为电影。
- 支持通过 `S02E07`、`2x07`、`第2季第7集` 等格式识别电视剧分集。
- 从文件名提取清理后的标题和上映年份。
- 自动移除常见清晰度、片源和编码信息，例如 `1080p`、`WEB-DL`、`BluRay`、`x265`。

识别结果保存在 `local_resources`：

- `detected_media_type`
- `parsed_title`
- `parsed_release_year`
- `parsed_season_number`
- `parsed_episode_number`

## 使用方式

启动一次媒体目录扫描即可完成识别：

```http
POST /api/v1/local-resources/scan
Content-Type: application/json

{
  "path": "data/media",
  "incremental": true
}
```

通过 `GET /api/v1/local-resources` 查看识别字段。升级前已经登记的资源会在下一次
增量扫描时补充识别结果，之后未发生变化的文件仍会被正常跳过。

下载完成自动登记的本地资源也会执行相同的文件名识别。

## 数据库升级

```powershell
uv run alembic upgrade head
```

或使用 pip 虚拟环境：

```powershell
alembic upgrade head
```
