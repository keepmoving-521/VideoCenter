import { apiClient } from "./client";

export interface HealthResponse {
  status: string;
}

export function getHealth(): Promise<HealthResponse> {
  return apiClient.get<HealthResponse>("/health", {
    timeoutMs: 5_000,
  });
}
