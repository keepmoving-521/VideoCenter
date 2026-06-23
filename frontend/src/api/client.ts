const DEFAULT_API_BASE_URL = "/api/v1";
const DEFAULT_TIMEOUT_MS = 15_000;
const REQUEST_ID_HEADER = "X-Request-ID";

export type QueryValue =
  | string
  | number
  | boolean
  | null
  | undefined
  | readonly (string | number | boolean)[];

export type QueryParams = Record<string, QueryValue>;
export type ResponseType = "auto" | "json" | "text" | "blob" | "response";

export interface ApiErrorDetail {
  code: string;
  message: string;
  details: unknown;
}

export interface ApiErrorMeta {
  request_id: string;
  timestamp: string;
  path: string;
}

export interface ApiErrorResponse {
  error: ApiErrorDetail;
  meta: ApiErrorMeta;
}

export interface ApiClientConfig {
  baseUrl?: string;
  timeoutMs?: number;
  fetcher?: typeof fetch;
}

export interface ApiRequestOptions
  extends Omit<RequestInit, "body" | "method"> {
  body?: unknown;
  query?: QueryParams;
  responseType?: ResponseType;
  timeoutMs?: number;
}

interface ApiErrorOptions {
  code: string;
  status: number;
  details?: unknown;
  requestId?: string;
  path?: string;
  cause?: unknown;
}

export class ApiError extends Error {
  readonly code: string;
  readonly status: number;
  readonly details: unknown;
  readonly requestId?: string;
  readonly path?: string;

  constructor(message: string, options: ApiErrorOptions) {
    super(message, { cause: options.cause });
    this.name = "ApiError";
    this.code = options.code;
    this.status = options.status;
    this.details = options.details;
    this.requestId = options.requestId;
    this.path = options.path;
  }
}

export class ApiTimeoutError extends ApiError {
  constructor(timeoutMs: number, cause?: unknown) {
    super(`API 请求超时（${timeoutMs}ms）`, {
      code: "REQUEST_TIMEOUT",
      status: 0,
      cause,
    });
    this.name = "ApiTimeoutError";
  }
}

export class ApiNetworkError extends ApiError {
  constructor(cause?: unknown) {
    super("无法连接到后端服务", {
      code: "NETWORK_ERROR",
      status: 0,
      cause,
    });
    this.name = "ApiNetworkError";
  }
}

export class ApiClient {
  readonly baseUrl: string;
  readonly timeoutMs: number;

  private readonly fetcher: typeof fetch;

  constructor(config: ApiClientConfig = {}) {
    this.baseUrl = normalizeBaseUrl(
      config.baseUrl ?? DEFAULT_API_BASE_URL,
    );
    this.timeoutMs = normalizeTimeout(
      config.timeoutMs,
      DEFAULT_TIMEOUT_MS,
    );
    this.fetcher = config.fetcher ?? fetch;
  }

  get<T>(
    path: string,
    options?: ApiRequestOptions,
  ): Promise<T> {
    return this.request<T>("GET", path, options);
  }

  post<T>(
    path: string,
    body?: unknown,
    options?: ApiRequestOptions,
  ): Promise<T> {
    return this.request<T>("POST", path, { ...options, body });
  }

  put<T>(
    path: string,
    body?: unknown,
    options?: ApiRequestOptions,
  ): Promise<T> {
    return this.request<T>("PUT", path, { ...options, body });
  }

  patch<T>(
    path: string,
    body?: unknown,
    options?: ApiRequestOptions,
  ): Promise<T> {
    return this.request<T>("PATCH", path, { ...options, body });
  }

  delete<T = void>(
    path: string,
    options?: ApiRequestOptions,
  ): Promise<T> {
    return this.request<T>("DELETE", path, options);
  }

  async request<T>(
    method: string,
    path: string,
    options: ApiRequestOptions = {},
  ): Promise<T> {
    const {
      body,
      headers: initialHeaders,
      query,
      responseType = "auto",
      signal,
      timeoutMs: requestTimeout,
      ...requestInit
    } = options;
    const timeoutMs = normalizeTimeout(requestTimeout, this.timeoutMs);
    const controller = new AbortController();
    const headers = new Headers(initialHeaders);
    let timedOut = false;
    const timeoutId = globalThis.setTimeout(() => {
      timedOut = true;
      controller.abort();
    }, timeoutMs);

    const abortFromCaller = () => controller.abort(signal?.reason);
    if (signal?.aborted) {
      abortFromCaller();
    } else {
      signal?.addEventListener("abort", abortFromCaller, { once: true });
    }

    if (!headers.has("Accept")) {
      headers.set("Accept", "application/json");
    }
    if (!headers.has(REQUEST_ID_HEADER)) {
      headers.set(REQUEST_ID_HEADER, createRequestId());
    }

    const requestBody = prepareBody(body, headers);
    const url = buildUrl(this.baseUrl, path, query);

    try {
      const response = await this.fetcher(url, {
        ...requestInit,
        body: requestBody,
        headers,
        method,
        signal: controller.signal,
      });

      if (!response.ok) {
        throw await createResponseError(response);
      }

      return await parseSuccessResponse<T>(response, responseType);
    } catch (error) {
      if (error instanceof ApiError) {
        throw error;
      }
      if (timedOut) {
        throw new ApiTimeoutError(timeoutMs, error);
      }
      if (signal?.aborted) {
        throw error;
      }
      throw new ApiNetworkError(error);
    } finally {
      globalThis.clearTimeout(timeoutId);
      signal?.removeEventListener("abort", abortFromCaller);
    }
  }
}

function normalizeBaseUrl(baseUrl: string): string {
  const normalized = baseUrl.trim().replace(/\/+$/, "");
  return normalized || DEFAULT_API_BASE_URL;
}

function normalizeTimeout(
  timeoutMs: number | undefined,
  fallback: number,
): number {
  return Number.isFinite(timeoutMs) && (timeoutMs ?? 0) > 0
    ? Math.floor(timeoutMs as number)
    : fallback;
}

function buildUrl(
  baseUrl: string,
  path: string,
  query?: QueryParams,
): string {
  const normalizedPath = path.startsWith("/") ? path : `/${path}`;
  const url = `${baseUrl}${normalizedPath}`;
  const search = new URLSearchParams();

  for (const [key, value] of Object.entries(query ?? {})) {
    if (value === null || value === undefined) {
      continue;
    }
    const values = Array.isArray(value) ? value : [value];
    for (const item of values) {
      search.append(key, String(item));
    }
  }

  const queryString = search.toString();
  return queryString ? `${url}?${queryString}` : url;
}

function prepareBody(
  body: unknown,
  headers: Headers,
): BodyInit | null | undefined {
  if (body === undefined || body === null) {
    return body;
  }
  if (
    typeof body === "string" ||
    body instanceof Blob ||
    body instanceof FormData ||
    body instanceof URLSearchParams ||
    body instanceof ArrayBuffer ||
    ArrayBuffer.isView(body)
  ) {
    return body as BodyInit;
  }
  if (!headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }
  return JSON.stringify(body);
}

async function parseSuccessResponse<T>(
  response: Response,
  responseType: ResponseType,
): Promise<T> {
  if (responseType === "response") {
    return response as T;
  }
  if (response.status === 204 || response.status === 205) {
    return undefined as T;
  }
  if (responseType === "blob") {
    return (await response.blob()) as T;
  }
  if (responseType === "text") {
    return (await response.text()) as T;
  }

  const contentType = response.headers.get("Content-Type") ?? "";
  if (responseType === "json" || contentType.includes("application/json")) {
    return (await response.json()) as T;
  }
  return (await response.text()) as T;
}

async function createResponseError(response: Response): Promise<ApiError> {
  const payload = await readErrorPayload(response);
  const requestId =
    payload?.meta.request_id ??
    response.headers.get(REQUEST_ID_HEADER) ??
    undefined;

  return new ApiError(
    payload?.error.message ?? `API 请求失败：${response.status}`,
    {
      code: payload?.error.code ?? `HTTP_${response.status}`,
      status: response.status,
      details: payload?.error.details,
      requestId,
      path: payload?.meta.path,
    },
  );
}

async function readErrorPayload(
  response: Response,
): Promise<ApiErrorResponse | null> {
  const contentType = response.headers.get("Content-Type") ?? "";
  if (!contentType.includes("application/json")) {
    return null;
  }

  try {
    const payload: unknown = await response.json();
    return isApiErrorResponse(payload) ? payload : null;
  } catch {
    return null;
  }
}

function isApiErrorResponse(value: unknown): value is ApiErrorResponse {
  if (!isRecord(value) || !isRecord(value.error) || !isRecord(value.meta)) {
    return false;
  }
  return (
    typeof value.error.code === "string" &&
    typeof value.error.message === "string" &&
    typeof value.meta.request_id === "string" &&
    typeof value.meta.timestamp === "string" &&
    typeof value.meta.path === "string"
  );
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null;
}

function createRequestId(): string {
  return globalThis.crypto?.randomUUID?.() ??
    `web-${Date.now()}-${Math.random().toString(16).slice(2)}`;
}

function readConfiguredTimeout(): number {
  const value = Number(import.meta.env.VITE_API_TIMEOUT_MS);
  return normalizeTimeout(value, DEFAULT_TIMEOUT_MS);
}

export const apiClient = new ApiClient({
  baseUrl: import.meta.env.VITE_API_BASE_URL,
  timeoutMs: readConfiguredTimeout(),
});

export function apiRequest<T>(
  path: string,
  options?: ApiRequestOptions & { method?: string },
): Promise<T> {
  const { method = "GET", ...requestOptions } = options ?? {};
  return apiClient.request<T>(method, path, requestOptions);
}
