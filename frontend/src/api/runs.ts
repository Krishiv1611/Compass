import api from "./client";
import type { RunEvent } from "@/types/run";

export interface RunHistoryResponse {
  items?: Array<{ id: string; events?: RunEvent[] }>;
}

export function eventsFromRunHistory(history: RunHistoryResponse): RunEvent[] {
  return history.items?.[0]?.events ?? [];
}

export const runsApi = {
  getSessionRuns: async (sessionId: string) => {
    const response = await api.get(`/sessions/${sessionId}/runs`);
    return response.data as RunHistoryResponse;
  },
  cancelRun: async (sessionId: string, runId: string) => {
    const response = await api.post(
      `/sessions/${sessionId}/runs/${runId}/cancel`
    );
    return response.data;
  },
};
