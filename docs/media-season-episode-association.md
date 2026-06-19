# M13：影片、季、分集关联

M13 将已有的数据库父子关系开放为可直接查询的影视目录树。

## 关联关系

```text
影片（media）
└── 季（seasons，按 season_number 排序）
    └── 分集（episodes，按 episode_number 排序）
```

- 每个季通过 `media_id` 关联一个影片。
- 每个分集通过 `season_id` 关联一个季。
- 分集详情可沿季关系得到所属影片。
- 删除影片会级联删除季和分集；删除季会级联删除分集。

## 查询接口

| 功能 | 接口 |
| --- | --- |
| 查询影片完整季集目录 | `GET /api/v1/media/{media_id}/hierarchy` |
| 查询季及其全部分集 | `GET /api/v1/seasons/{season_id}` |
| 查询分集及上级关联 | `GET /api/v1/episodes/{episode_id}` |

影片目录响应按季号、集号升序排列。分集详情除 `season_id` 外，还会返回所属影片的 `media_id` 和 `season_number`，便于客户端直接构造导航路径。

本次迭代没有修改数据库结构，因此不新增 Alembic 迁移文件。
