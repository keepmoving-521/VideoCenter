import { apiClient, ApiError } from "./client";

export interface MediaLibraryStats {
  total_media: number;
  favorite_media: number;
  media_with_local_resources: number;
  total_local_resources: number;
  total_download_tasks: number;
  total_tags: number;
  total_seasons: number;
  total_episodes: number;
  by_type: Record<string, number>;
  by_status: Record<string, number>;
}

export interface DownloadSummary {
  id: number;
  status:
    | "waiting"
    | "downloading"
    | "paused"
    | "completed"
    | "failed"
    | "cancelled";
}

export interface HistoryMediaSummary {
  id: number;
  title: string;
  media_type: string;
  release_year: number | null;
  poster_url: string | null;
}

export interface ContinueWatchingItem {
  id: number;
  media_id: number;
  position_seconds: number;
  duration_seconds: number | null;
  watched_at: string;
  media: HistoryMediaSummary;
}

export interface HistoryPage {
  items: ContinueWatchingItem[];
  total: number;
}

export interface DailyWatchStat {
  date: string;
  watched_seconds: number;
  watched_minutes: number;
  watched_media_count: number;
  completed_count: number;
}

export interface DailyWatchStats {
  start_date: string;
  end_date: string;
  items: DailyWatchStat[];
}

export interface BackgroundTask {
  id: number;
  task_type: string;
  status:
    | "waiting"
    | "running"
    | "paused"
    | "completed"
    | "failed"
    | "cancelled";
  title: string;
  progress: number;
  updated_at: string;
  error_message: string | null;
}

export interface BackgroundTaskPage {
  items: BackgroundTask[];
  total: number;
}

export interface HomeDashboardData {
  mediaStats: MediaLibraryStats | null;
  downloads: DownloadSummary[] | null;
  continueWatching: HistoryPage | null;
  weeklyWatchStats: DailyWatchStats | null;
  tasks: BackgroundTaskPage | null;
  errors: HomeDashboardError[];
}

export interface HomeDashboardError {
  section: HomeDashboardSection;
  message: string;
  requestId?: string;
}

type HomeDashboardSection =
  | "media"
  | "downloads"
  | "history"
  | "watchStats"
  | "tasks";

type DashboardRequest<T> = {
  section: HomeDashboardSection;
  promise: Promise<T>;
};

export async function getHomeDashboard(
  signal?: AbortSignal,
): Promise<HomeDashboardData> {
  const { startDate, endDate } = getCurrentWeekRange();
  const requests = [
    {
      section: "media",
      promise: apiClient.get<MediaLibraryStats>("/media/stats", { signal }),
    },
    {
      section: "downloads",
      promise: apiClient.get<DownloadSummary[]>("/downloads", { signal }),
    },
    {
      section: "history",
      promise: apiClient.get<HistoryPage>("/history/continue-watching", {
        query: { page: 1, page_size: 3 },
        signal,
      }),
    },
    {
      section: "watchStats",
      promise: apiClient.get<DailyWatchStats>("/history/stats/daily", {
        query: { start_date: startDate, end_date: endDate },
        signal,
      }),
    },
    {
      section: "tasks",
      promise: apiClient.get<BackgroundTaskPage>("/tasks", {
        query: { page: 1, page_size: 4 },
        signal,
      }),
    },
  ] satisfies DashboardRequest<unknown>[];
  const results = await Promise.allSettled(
    requests.map((request) => request.promise),
  );
  const values = new Map<HomeDashboardSection, unknown>();
  const errors: HomeDashboardError[] = [];

  results.forEach((result, index) => {
    const section = requests[index].section;
    if (result.status === "fulfilled") {
      values.set(section, result.value);
      return;
    }
    if (signal?.aborted) {
      return;
    }
    const error = result.reason;
    errors.push({
      section,
      message:
        error instanceof Error ? error.message : "首页数据加载失败",
      requestId: error instanceof ApiError ? error.requestId : undefined,
    });
  });

  if (signal?.aborted) {
    throw signal.reason;
  }

  return {
    mediaStats:
      (values.get("media") as MediaLibraryStats | undefined) ?? null,
    downloads:
      (values.get("downloads") as DownloadSummary[] | undefined) ?? null,
    continueWatching:
      (values.get("history") as HistoryPage | undefined) ?? null,
    weeklyWatchStats:
      (values.get("watchStats") as DailyWatchStats | undefined) ?? null,
    tasks:
      (values.get("tasks") as BackgroundTaskPage | undefined) ?? null,
    errors,
  };
}

function getCurrentWeekRange(): {
  startDate: string;
  endDate: string;
} {
  const end = new Date();
  const start = new Date(end);
  const day = end.getDay();
  start.setDate(end.getDate() - (day === 0 ? 6 : day - 1));

  return {
    startDate: formatLocalDate(start),
    endDate: formatLocalDate(end),
  };
}

function formatLocalDate(date: Date): string {
  const year = date.getFullYear();
  const month = String(date.getMonth() + 1).padStart(2, "0");
  const day = String(date.getDate()).padStart(2, "0");
  return `${year}-${month}-${day}`;
}
