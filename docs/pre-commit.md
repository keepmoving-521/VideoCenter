# B11：pre-commit 配置

本文档说明 VideoCenter 提交前检查的安装、执行和维护方式。

## 目标

pre-commit 在代码进入 Git 历史前自动执行轻量检查，用于尽早发现：

- 尾部空格和缺失的文件结尾换行；
- YAML、TOML、JSON 语法错误；
- 未清理的 Git 合并冲突标记；
- 意外加入的大文件；
- 文件内部混合使用 CRLF 和 LF；
- Ruff lint 问题；
- Ruff 格式问题。

pre-commit 不能替代完整测试。提交前仍建议运行：

```powershell
uv run pytest
```

## 配置文件

配置位于项目根目录：

```text
.pre-commit-config.yaml
```

Hook 版本均固定，确保不同开发环境执行相同检查。

## 已配置的 hooks

### 文件基础检查

来自 `pre-commit/pre-commit-hooks`：

- `trailing-whitespace`
- `end-of-file-fixer`
- `check-yaml`
- `check-toml`
- `check-json`
- `check-merge-conflict`
- `check-added-large-files`
- `mixed-line-ending`

单个新增文件默认不得超过 1024 KB。视频、图片等大型媒体文件不应提交到代码仓库。

`mixed-line-ending` 只禁止同一个文件混合使用多种行尾，不强制 Windows 和 Linux 开发者统一使用某一种行尾。

### Python 检查

来自 `astral-sh/ruff-pre-commit`：

- `ruff-check --fix`
- `ruff-format`

Ruff 会先修复安全的 lint 问题，再执行格式化。如果 hook 修改了文件，本次提交会停止，需要检查修改后重新暂存并提交。

## 安装

安装开发依赖：

```powershell
uv sync --frozen --extra dev
```

安装 Git hook：

```powershell
uv run videocenter-hooks-install
```

使用 pip 虚拟环境时：

```powershell
python -m pip install -r requirements-dev.txt
videocenter-hooks-install
```

安装成功后，`.git/hooks/pre-commit` 会在每次 `git commit` 前自动执行。
首次执行 hooks 时需要访问 GitHub 下载配置中固定版本的环境，之后会复用本地缓存。

## 手动执行

检查全部已跟踪文件：

```powershell
uv run videocenter-hooks-run
```

也可以直接使用 pre-commit：

```powershell
uv run pre-commit run --all-files
```

只执行 Ruff hook：

```powershell
uv run pre-commit run ruff-check --all-files
uv run pre-commit run ruff-format --all-files
```

## 项目内缓存

VideoCenter 提供的 `videocenter-hooks-*` 命令默认将 hook 环境放在：

```text
.pre-commit-cache/
```

该目录已加入 `.gitignore`，不会提交到仓库。这也避免系统全局 pre-commit 缓存权限或损坏影响项目。

如果已经设置 `PRE_COMMIT_HOME`，项目命令会尊重该环境变量。

## 提交流程

推荐流程：

```powershell
uv run videocenter-lint
uv run pytest
git add .
git commit -m "..."
```

如果 pre-commit 修改文件：

1. 查看修改内容；
2. 重新运行测试或 lint；
3. 重新执行 `git add`；
4. 再次提交。

不要使用 `git commit --no-verify` 绕过检查，除非明确知道原因并准备后续修复。

## 更新 hooks

查看可升级版本：

```powershell
uv run pre-commit autoupdate --dry-run
```

更新配置：

```powershell
uv run pre-commit autoupdate
uv run videocenter-hooks-run
uv run pytest
```

更新后应检查 `.pre-commit-config.yaml` 的版本变化，并与测试结果一同提交。

## CI 使用

即使本地安装了 Git hook，CI 仍应独立执行检查：

```powershell
uv sync --frozen --extra dev
uv run videocenter-hooks-run
uv run pytest
```

本地 hook 可以被人为绕过，CI 才是合并前的最终保障。

## 当前验证

B11 已完成：

- pre-commit 加入开发依赖和锁文件；
- 配置文件语法校验通过；
- Git pre-commit hook 安装验证通过；
- 文件基础 hooks 已执行并清理历史格式问题；
- Ruff lint、Ruff format 和完整测试通过；
- Ruff hooks 与 B10 配置一致；
- 添加安装和全量检查命令；
- 添加配置内容和命令单元测试。
