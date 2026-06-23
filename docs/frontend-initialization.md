# W01：初始化前端项目

前端工程位于 `frontend/`，采用 React、TypeScript、Vite 和 ESLint。前后端保持独立依赖和
启动命令，便于分别开发和部署。

## 环境要求

- Node.js 24；
- npm 11。

## 安装依赖

```powershell
Set-Location frontend
npm ci
```

`package-lock.json` 应提交代码仓库。CI 和其他开发环境使用 `npm ci`，确保严格按照锁文件
安装。

更新依赖时使用 `npm install`，确认构建通过后同时提交 `package.json` 和
`package-lock.json`。

## 启动开发环境

先在项目根目录启动后端：

```powershell
uv run uvicorn videocenter.main:app --reload
```

再启动前端：

```powershell
Set-Location frontend
Copy-Item .env.example .env
npm run dev
```

访问 <http://127.0.0.1:5173>。

Vite 会将 `/api` 请求代理到 `http://127.0.0.1:8000`。如后端地址不同，可修改：

```dotenv
VITE_BACKEND_PROXY_TARGET=http://127.0.0.1:8000
```

前端 API 前缀默认为 `/api/v1`，可通过 `VITE_API_BASE_URL` 调整。

## 项目结构

```text
frontend/
├── src/
│   ├── api/          # API 请求封装
│   ├── App.tsx       # 应用根组件
│   ├── main.tsx      # React 入口
│   └── styles.css    # 全局样式
├── .env.example
├── eslint.config.js
├── index.html
├── package.json
├── tsconfig*.json
└── vite.config.ts
```

当前启动页会调用后端健康检查，用于验证开发代理和 API 客户端配置。

## 质量检查和构建

```powershell
npm run lint
npm run typecheck
npm run build
```

构建文件生成到 `frontend/dist/`，该目录和 `node_modules/` 不提交仓库。

GitHub Actions 已增加独立前端任务，使用 `npm ci` 后执行代码检查、类型检查和生产构建。
