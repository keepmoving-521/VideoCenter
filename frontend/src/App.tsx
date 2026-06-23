import { useEffect, useState } from "react";

import { getHealth } from "./api/system";

type BackendState = "checking" | "online" | "offline";

function App() {
  const [backendState, setBackendState] =
    useState<BackendState>("checking");

  useEffect(() => {
    let active = true;

    getHealth()
      .then(() => {
        if (active) {
          setBackendState("online");
        }
      })
      .catch(() => {
        if (active) {
          setBackendState("offline");
        }
      });

    return () => {
      active = false;
    };
  }, []);

  const statusText = {
    checking: "正在连接后端服务",
    online: "后端服务已连接",
    offline: "后端服务未启动",
  }[backendState];

  return (
    <main className="app-shell">
      <section className="welcome-card">
        <p className="eyebrow">PRIVATE MEDIA LIBRARY</p>
        <h1>VideoCenter</h1>
        <p className="description">
          私人影视资源管理系统的前端工程已经就绪。
        </p>
        <div className={`service-status service-status--${backendState}`}>
          <span className="status-dot" aria-hidden="true" />
          <span>{statusText}</span>
        </div>
        <p className="next-step">
          后续迭代将在这里逐步加入影视库、下载任务、播放和观看历史页面。
        </p>
      </section>
    </main>
  );
}

export default App;
