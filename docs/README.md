# VideoCenter 开发文档

本目录用于存放各次系统迭代的专题说明，避免在项目根目录的 `README.md` 中堆积过多实现细节。

## 专题文档

- [B01：引入 Alembic 数据库迁移](database-migrations.md)
- [B02：创建当前数据库初始迁移](initial-database-migration.md)
- [B03：开发、测试、生产环境配置](environment-configuration.md)
- [B04：统一日志配置](logging-configuration.md)
- [B05：统一异常处理](exception-handling.md)
- [B06：统一 API 错误响应格式](api-error-response.md)
- [B07：请求参数校验](request-validation.md)
- [B08：测试专用数据库](testing-database.md)
- [B09：API 集成测试框架](api-integration-testing.md)
- [B10：Ruff 代码检查命令](ruff-code-check.md)
- [B11：pre-commit 配置](pre-commit.md)
- [B12：GitHub Actions 自动测试](github-actions.md)
- [M01：完善影视资源字段](media-core-fields.md)
- [M02～M08：影视状态、类型、来源与元数据字段](media-metadata-fields.md)
- [M09～M12：海报、标签、电视剧季与分集](media-artwork-tags-seasons-episodes.md)
- [M13：影片、季、分集关联](media-season-episode-association.md)
- [M14～M15：收藏状态、个人评分和备注](media-personal-preferences.md)
- [R01：资源解析器统一接口](resource-parser-interface.md)
- [R02：解析结果数据结构](parser-result-structure.md)
- [R03：根据 URL 自动选择解析器](parser-url-selection.md)
- [R04：不支持网站的错误处理](unsupported-website-error.md)
- [R05：通用网页基础信息解析](generic-webpage-parser.md)
- [R06～R10：网页影片核心信息解析](webpage-core-metadata-parsing.md)
- [R11～R14：视频、清晰度、字幕与电视剧季集解析](webpage-media-resources-and-series.md)
- [R15～R17：资源预解析、确认与保存](parse-preview-confirm-save.md)
- [R18～R19：解析超时与失败重试](parser-timeout-and-retry.md)
- [R20～R21：解析任务日志与结果缓存](parser-task-logging-and-cache.md)
- [R22～R23：防止重复解析与解析器单元测试](duplicate-parsing-and-parser-tests.md)

后续功能建议继续使用“需求编号 + 功能名称”的方式记录，并在此处增加索引。
