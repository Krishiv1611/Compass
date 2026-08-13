import api from "./client";
import type { RunEvent } from "@/types/run";

export interface RunHistoryResponse {
  items?: Array<{ id: string; events?: RunEvent[]; diagnostics?: RunDiagnostics }>;
  capabilities?: CapabilityReport;
}

export interface RunDiagnostics {
  provider?: string | null;
  model?: string | null;
  calls: number;
  tokens: { input: number; output: number; total: number };
  cost: { status: "unavailable" | "free" | "estimated"; estimated_usd: number | null };
  categories: Record<string, number>;
  stages: Array<{ name: string; duration_ms: number; calls: number; errors: number; category: string }>;
  cache: Record<string, string>;
}

export interface CapabilityReport {
  provider: { name: string; model: string; credential_configured: boolean };
  execution_target: string;
  permission_profile: string;
  capabilities: Record<string, { available: boolean; reason: string }>;
  unavailable: string[];
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
