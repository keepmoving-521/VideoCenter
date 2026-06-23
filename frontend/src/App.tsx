import { useEffect, useState, type ReactNode } from "react";

import {
  getHomeDashboard,
  type BackgroundTask,
  type ContinueWatchingItem,
  type HomeDashboardData,
} from "./api/home";
import { getHealth } from "./api/system";

type BackendState = "checking" | "online" | "offline";

const BACKEND_HEALTH_CHECK_INTERVAL_MS = 10_000;

interface NavigationItem {
  id: string;
  label: string;
  description: string;
  icon: ReactNode;
}

const navigationItems: NavigationItem[] = [
  {
    id: "home",
    label: "首页",
    description: "概览与快捷入口",
    icon: <HomeIcon />,
  },
  {
    id: "library",
    label: "影视库",
    description: "浏览与管理影片",
    icon: <LibraryIcon />,
  },
  {
    id: "downloads",
    label: "下载管理",
    description: "下载队列与进度",
    icon: <DownloadIcon />,
  },
  {
    id: "local",
    label: "本地资源",
    description: "媒体目录与文件",
    icon: <FolderIcon />,
  },
  {
    id: "tasks",
    label: "任务中心",
    description: "后台任务状态",
    icon: <ActivityIcon />,
  },
  {
    id: "history",
    label: "观看历史",
    description: "进度与统计",
    icon: <HistoryIcon />,
  },
];

function App() {
  const [backendState, setBackendState] =
    useState<BackendState>("checking");
  const [activeNavigation, setActiveNavigation] = useState("home");
  const [sidebarOpen, setSidebarOpen] = useState(false);

  useEffect(() => {
    let active = true;

    async function checkBackendHealth() {
      try {
        await getHealth();
        if (active) {
          setBackendState("online");
        }
      } catch {
        if (active) {
          setBackendState("offline");
        }
      }
    }

    void checkBackendHealth();
    const healthCheckTimer = window.setInterval(
      () => void checkBackendHealth(),
      BACKEND_HEALTH_CHECK_INTERVAL_MS,
    );

    return () => {
      active = false;
      window.clearInterval(healthCheckTimer);
    };
  }, []);

  const statusText = {
    checking: "正在连接",
    online: "服务正常",
    offline: "后端离线",
  }[backendState];
  const activeItem =
    navigationItems.find((item) => item.id === activeNavigation) ??
    navigationItems[0];

  function selectNavigation(id: string) {
    setActiveNavigation(id);
    setSidebarOpen(false);
  }

  return (
    <div className="app-layout">
      <button
        className={`sidebar-backdrop ${sidebarOpen ? "is-visible" : ""}`}
        type="button"
        aria-label="关闭导航菜单"
        onClick={() => setSidebarOpen(false)}
      />

      <aside className={`sidebar ${sidebarOpen ? "is-open" : ""}`}>
        <div className="brand">
          <span className="brand-mark" aria-hidden="true">
            <PlayIcon />
          </span>
          <span className="brand-copy">
            <strong>VideoCenter</strong>
            <small>私人影视库</small>
          </span>
          <button
            className="icon-button sidebar-close"
            type="button"
            aria-label="关闭导航菜单"
            onClick={() => setSidebarOpen(false)}
          >
            <CloseIcon />
          </button>
        </div>

        <nav className="primary-navigation" aria-label="主导航">
          <p className="navigation-label">工作区</p>
          {navigationItems.map((item) => (
            <button
              className={`navigation-item ${
                activeNavigation === item.id ? "is-active" : ""
              }`}
              type="button"
              key={item.id}
              onClick={() => selectNavigation(item.id)}
            >
              <span className="navigation-icon" aria-hidden="true">
                {item.icon}
              </span>
              <span>
                <strong>{item.label}</strong>
                <small>{item.description}</small>
              </span>
            </button>
          ))}
        </nav>

        <div className="sidebar-footer">
          <div className={`backend-state backend-state--${backendState}`}>
            <span className="status-dot" aria-hidden="true" />
            <span>
              <strong>{statusText}</strong>
              <small>FastAPI · 127.0.0.1:8000</small>
            </span>
          </div>
          <button className="settings-button" type="button">
            <SettingsIcon />
            <span>系统设置</span>
          </button>
        </div>
      </aside>

      <div className="workspace">
        <header className="topbar">
          <div className="topbar-title">
            <button
              className="icon-button menu-button"
              type="button"
              aria-label="打开导航菜单"
              aria-expanded={sidebarOpen}
              onClick={() => setSidebarOpen(true)}
            >
              <MenuIcon />
            </button>
            <div>
              <p>VideoCenter</p>
              <h1>{activeItem.label}</h1>
            </div>
          </div>

          <div className="topbar-actions">
            <label className="search-box">
              <SearchIcon />
              <input
                type="search"
                placeholder="搜索影片、演员或标签"
                aria-label="搜索影片、演员或标签"
              />
              <kbd>⌘ K</kbd>
            </label>
            <button
              className="icon-button notification-button"
              type="button"
              aria-label="查看通知"
            >
              <BellIcon />
              <span className="notification-dot" />
            </button>
            <div className="profile-chip" aria-label="当前用户">
              <span>VC</span>
              <div>
                <strong>私人空间</strong>
                <small>本地用户</small>
              </div>
            </div>
          </div>
        </header>

        <main className="main-content">
          {activeNavigation === "home" ? (
            <HomeContent backendState={backendState} />
          ) : (
            <PlaceholderContent
              item={activeItem}
              onBackHome={() => setActiveNavigation("home")}
            />
          )}
        </main>
      </div>
    </div>
  );
}

function HomeContent({ backendState }: { backendState: BackendState }) {
  const [dashboard, setDashboard] = useState<HomeDashboardData | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (backendState === "offline") {
      setLoading(false);
      return;
    }

    const controller = new AbortController();

    setLoading(true);
    getHomeDashboard(controller.signal)
      .then(setDashboard)
      .catch((error: unknown) => {
        if (!controller.signal.aborted) {
          setDashboard({
            mediaStats: null,
            downloads: null,
            continueWatching: null,
            weeklyWatchStats: null,
            tasks: null,
            errors: [
              {
                section: "media",
                message:
                  error instanceof Error
                    ? error.message
                    : "首页数据加载失败",
              },
            ],
          });
        }
      })
      .finally(() => {
        if (!controller.signal.aborted) {
          setLoading(false);
        }
      });

    return () => controller.abort();
  }, [backendState]);

  const activeDownloads =
    dashboard?.downloads?.filter((download) =>
      ["waiting", "downloading", "paused"].includes(download.status),
    ).length ?? null;
  const weeklyMinutes =
    dashboard?.weeklyWatchStats?.items.reduce(
      (total, item) => total + item.watched_minutes,
      0,
    ) ?? null;
  const overviewCards = [
    {
      label: "影视条目",
      value: formatDashboardNumber(dashboard?.mediaStats?.total_media, loading),
      hint:
        dashboard?.mediaStats === null && !loading
          ? "影视库数据暂不可用"
          : `${dashboard?.mediaStats?.favorite_media ?? 0} 部已收藏`,
      tone: "violet",
    },
    {
      label: "进行中下载",
      value: formatDashboardNumber(activeDownloads, loading),
      hint:
        dashboard?.downloads === null && !loading
          ? "下载数据暂不可用"
          : `共 ${dashboard?.downloads?.length ?? 0} 个下载任务`,
      tone: "blue",
    },
    {
      label: "本地视频",
      value: formatDashboardNumber(
        dashboard?.mediaStats?.total_local_resources,
        loading,
      ),
      hint:
        dashboard?.mediaStats === null && !loading
          ? "本地资源数据暂不可用"
          : `${dashboard?.mediaStats?.media_with_local_resources ?? 0} 部影视可播放`,
      tone: "teal",
    },
    {
      label: "本周观看",
      value: formatWatchDuration(weeklyMinutes, loading),
      hint:
        dashboard?.weeklyWatchStats === null && !loading
          ? "观看统计暂不可用"
          : `${dashboard?.weeklyWatchStats?.items.reduce(
              (total, item) => total + item.watched_media_count,
              0,
            ) ?? 0} 次影片观看`,
      tone: "amber",
    },
  ];
  const continueItems = dashboard?.continueWatching?.items ?? [];
  const taskItems = dashboard?.tasks?.items ?? [];

  return (
    <div className="page-stack">
      <section className="hero-panel">
        <div className="hero-content">
          <p className="eyebrow">PRIVATE MEDIA LIBRARY</p>
          <h2>欢迎回到你的影视空间</h2>
          <p>
            统一整理网络资源、本地视频、下载任务和观看进度。所有内容都留在你的设备上。
          </p>
          <div className="hero-actions">
            <button className="primary-button" type="button">
              <PlusIcon />
              添加影视资源
            </button>
            <button className="secondary-button" type="button">
              <FolderIcon />
              扫描本地目录
            </button>
          </div>
        </div>
        <div className="hero-artwork" aria-hidden="true">
          <div className="poster poster-one" />
          <div className="poster poster-two" />
          <div className="poster poster-three" />
          <span className="hero-play">
            <PlayIcon />
          </span>
        </div>
      </section>

      <section aria-labelledby="overview-heading">
        <div className="section-heading">
          <div>
            <p className="section-kicker">LIBRARY OVERVIEW</p>
            <h2 id="overview-heading">系统概览</h2>
          </div>
          <span
            className={`connection-pill connection-pill--${backendState}`}
          >
            <span className="status-dot" />
            {loading
              ? "正在更新数据"
              : dashboard?.errors.length
                ? `${dashboard.errors.length} 项数据暂不可用`
                : "数据已更新"}
          </span>
        </div>
        <div className="overview-grid">
          {overviewCards.map((card) => (
            <article
              className={`overview-card overview-card--${card.tone}`}
              key={card.label}
            >
              <span className="overview-label">{card.label}</span>
              <strong>{card.value}</strong>
              <small>{card.hint}</small>
            </article>
          ))}
        </div>
      </section>

      <section className="dashboard-grid">
        <article className="content-card">
          <div className="card-heading">
            <div>
              <p className="section-kicker">CONTINUE WATCHING</p>
              <h2>继续观看</h2>
            </div>
            <button className="text-button" type="button">
              查看全部 <ArrowIcon />
            </button>
          </div>
          {loading ? (
            <DashboardLoading label="正在读取播放进度" />
          ) : continueItems.length ? (
            <div className="continue-list">
              {continueItems.map((item) => (
                <ContinueWatchingRow item={item} key={item.id} />
              ))}
            </div>
          ) : (
            <div className="empty-state compact">
              <span className="empty-icon">
                <PlayIcon />
              </span>
              <div>
                <strong>
                  {dashboard?.continueWatching === null
                    ? "播放记录暂不可用"
                    : "还没有播放记录"}
                </strong>
                <p>
                  {dashboard?.continueWatching === null
                    ? "请确认后端服务状态后刷新页面。"
                    : "开始观看影片后，这里会显示上次的播放位置。"}
                </p>
              </div>
            </div>
          )}
        </article>

        <article className="content-card task-card">
          <div className="card-heading">
            <div>
              <p className="section-kicker">BACKGROUND TASKS</p>
              <h2>任务动态</h2>
            </div>
            <span className="live-badge">实时</span>
          </div>
          {loading ? (
            <DashboardLoading label="正在读取任务状态" />
          ) : taskItems.length ? (
            <div className="task-list">
              {taskItems.map((task) => (
                <TaskRow task={task} key={task.id} />
              ))}
            </div>
          ) : (
            <div className="task-placeholder">
              <span className="task-pulse" />
              <div>
                <strong>
                  {dashboard?.tasks === null
                    ? "任务数据暂不可用"
                    : "暂无任务记录"}
                </strong>
                <p>
                  {dashboard?.tasks === null
                    ? "请确认后端服务状态后刷新页面。"
                    : "下载、扫描和转码进度会显示在这里。"}
                </p>
              </div>
            </div>
          )}
        </article>
      </section>
    </div>
  );
}

function ContinueWatchingRow({ item }: { item: ContinueWatchingItem }) {
  const progress =
    item.duration_seconds && item.duration_seconds > 0
      ? Math.min(100, (item.position_seconds / item.duration_seconds) * 100)
      : 0;

  return (
    <article className="continue-item">
      <div
        className="continue-poster"
        style={
          item.media.poster_url
            ? { backgroundImage: `url("${item.media.poster_url}")` }
            : undefined
        }
      >
        {!item.media.poster_url && <LibraryIcon />}
      </div>
      <div className="continue-copy">
        <strong>{item.media.title}</strong>
        <span>
          {item.media.release_year ?? "年份未知"} ·{" "}
          {formatPlaybackPosition(item.position_seconds)}
        </span>
        <div className="progress-track" aria-label={`播放进度 ${Math.round(progress)}%`}>
          <span style={{ width: `${progress}%` }} />
        </div>
      </div>
      <button className="continue-play" type="button" aria-label={`继续播放 ${item.media.title}`}>
        <PlayIcon />
      </button>
    </article>
  );
}

function TaskRow({ task }: { task: BackgroundTask }) {
  const statusLabel = {
    waiting: "等待中",
    running: "运行中",
    paused: "已暂停",
    completed: "已完成",
    failed: "失败",
    cancelled: "已取消",
  }[task.status];

  return (
    <article className="task-item">
      <span className={`task-status task-status--${task.status}`} />
      <div>
        <strong>{task.title}</strong>
        <span>{statusLabel} · {Math.round(task.progress)}%</span>
      </div>
      <time dateTime={task.updated_at}>{formatRelativeTime(task.updated_at)}</time>
    </article>
  );
}

function DashboardLoading({ label }: { label: string }) {
  return (
    <div className="dashboard-loading" role="status">
      <span className="loading-spinner" />
      <span>{label}</span>
    </div>
  );
}

function formatDashboardNumber(
  value: number | null | undefined,
  loading: boolean,
): string {
  if (loading) {
    return "···";
  }
  return value === null || value === undefined
    ? "—"
    : new Intl.NumberFormat("zh-CN").format(value);
}

function formatWatchDuration(
  minutes: number | null,
  loading: boolean,
): string {
  if (loading) {
    return "···";
  }
  if (minutes === null) {
    return "—";
  }
  if (minutes < 60) {
    return `${Math.round(minutes)} 分钟`;
  }
  return `${(minutes / 60).toFixed(minutes >= 600 ? 0 : 1)} 小时`;
}

function formatPlaybackPosition(seconds: number): string {
  const totalMinutes = Math.floor(seconds / 60);
  const hours = Math.floor(totalMinutes / 60);
  const minutes = totalMinutes % 60;
  return hours ? `看到 ${hours} 小时 ${minutes} 分` : `看到 ${minutes} 分钟`;
}

function formatRelativeTime(value: string): string {
  const timestamp = new Date(value).getTime();
  const elapsedMinutes = Math.max(
    0,
    Math.floor((Date.now() - timestamp) / 60_000),
  );
  if (elapsedMinutes < 1) {
    return "刚刚";
  }
  if (elapsedMinutes < 60) {
    return `${elapsedMinutes} 分钟前`;
  }
  const elapsedHours = Math.floor(elapsedMinutes / 60);
  if (elapsedHours < 24) {
    return `${elapsedHours} 小时前`;
  }
  return `${Math.floor(elapsedHours / 24)} 天前`;
}

function PlaceholderContent({
  item,
  onBackHome,
}: {
  item: NavigationItem;
  onBackHome: () => void;
}) {
  return (
    <section className="placeholder-page">
      <span className="placeholder-icon">{item.icon}</span>
      <p className="section-kicker">PAGE FOUNDATION</p>
      <h2>{item.label}</h2>
      <p>{item.description}页面将在后续迭代中接入。</p>
      <button className="secondary-button" type="button" onClick={onBackHome}>
        返回首页
      </button>
    </section>
  );
}

function Icon({
  children,
  viewBox = "0 0 24 24",
}: {
  children: ReactNode;
  viewBox?: string;
}) {
  return (
    <svg
      viewBox={viewBox}
      fill="none"
      stroke="currentColor"
      strokeWidth="1.8"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
    >
      {children}
    </svg>
  );
}

function HomeIcon() {
  return (
    <Icon>
      <path d="m3 10 9-7 9 7" />
      <path d="M5 9v11h14V9" />
      <path d="M9 20v-6h6v6" />
    </Icon>
  );
}

function LibraryIcon() {
  return (
    <Icon>
      <rect x="3" y="4" width="18" height="16" rx="2" />
      <path d="M7 4v16M17 4v16M3 9h4M17 9h4M3 15h4M17 15h4" />
    </Icon>
  );
}

function DownloadIcon() {
  return (
    <Icon>
      <path d="M12 3v12" />
      <path d="m7 10 5 5 5-5" />
      <path d="M5 21h14" />
    </Icon>
  );
}

function FolderIcon() {
  return (
    <Icon>
      <path d="M3 6h7l2 2h9v11H3z" />
    </Icon>
  );
}

function ActivityIcon() {
  return (
    <Icon>
      <path d="M3 12h4l2-6 4 12 2-6h6" />
    </Icon>
  );
}

function HistoryIcon() {
  return (
    <Icon>
      <path d="M3 12a9 9 0 1 0 3-6.7L3 8" />
      <path d="M3 3v5h5M12 7v5l3 2" />
    </Icon>
  );
}

function SettingsIcon() {
  return (
    <Icon>
      <circle cx="12" cy="12" r="3" />
      <path d="M19.4 15a1.7 1.7 0 0 0 .3 1.9l.1.1-2.8 2.8-.1-.1a1.7 1.7 0 0 0-1.9-.3 1.7 1.7 0 0 0-1 1.6v.2h-4V21a1.7 1.7 0 0 0-1-1.6 1.7 1.7 0 0 0-1.9.3l-.1.1L4.2 17l.1-.1a1.7 1.7 0 0 0 .3-1.9A1.7 1.7 0 0 0 3 14H2.8v-4H3a1.7 1.7 0 0 0 1.6-1 1.7 1.7 0 0 0-.3-1.9L4.2 7 7 4.2l.1.1a1.7 1.7 0 0 0 1.9.3A1.7 1.7 0 0 0 10 3V2.8h4V3a1.7 1.7 0 0 0 1 1.6 1.7 1.7 0 0 0 1.9-.3l.1-.1L19.8 7l-.1.1a1.7 1.7 0 0 0-.3 1.9 1.7 1.7 0 0 0 1.6 1h.2v4H21a1.7 1.7 0 0 0-1.6 1Z" />
    </Icon>
  );
}

function SearchIcon() {
  return (
    <Icon>
      <circle cx="11" cy="11" r="7" />
      <path d="m20 20-4-4" />
    </Icon>
  );
}

function BellIcon() {
  return (
    <Icon>
      <path d="M18 8a6 6 0 0 0-12 0c0 7-3 7-3 9h18c0-2-3-2-3-9" />
      <path d="M10 21h4" />
    </Icon>
  );
}

function MenuIcon() {
  return (
    <Icon>
      <path d="M4 7h16M4 12h16M4 17h16" />
    </Icon>
  );
}

function CloseIcon() {
  return (
    <Icon>
      <path d="m6 6 12 12M18 6 6 18" />
    </Icon>
  );
}

function PlayIcon() {
  return (
    <Icon>
      <path d="m8 5 11 7-11 7z" />
    </Icon>
  );
}

function PlusIcon() {
  return (
    <Icon>
      <path d="M12 5v14M5 12h14" />
    </Icon>
  );
}

function ArrowIcon() {
  return (
    <Icon>
      <path d="M5 12h14M14 7l5 5-5 5" />
    </Icon>
  );
}

export default App;
