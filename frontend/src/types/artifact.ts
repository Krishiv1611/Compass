import type { JsonValue } from "./run";

export type ArtifactStatus = "pending" | "active" | "completed" | "failed";

export interface PlanStepArtifact {
  id: string;
  text: string;
  status: ArtifactStatus;
}

export interface ToolArtifact {
  id: string;
  name: string;
  args: Record<string, JsonValue>;
  result: JsonValue | undefined;
  status: "running" | "completed" | "error";
}

export interface CheckArtifact {
  id: string;
  name: string;
  status: string;
  duration_ms: number | null;
  details: JsonValue;
}

export type WorkerStatus =
  | "pending"
  | "running"
  | "completed"
  | "failed"
  | "blocked"
  | "cancelled"
  | "invalid";

export interface WorkerArtifact {
  task_id: string;
  title: string;
  status: WorkerStatus;
  duration_ms: number;
  evidence_count: number;
  summary?: string;
}

export interface RunWalkthroughArtifact {
  plan: string | null;
  worker_contributions: string[];
  changed_files: string[];
  checks: CheckArtifact[];
  usage: Record<string, JsonValue>;
  unresolved_conflicts: string[];
  terminal_status: string | null;
}

export interface RunArtifact {
  plan: string | null;
  steps: PlanStepArtifact[];
  tools: ToolArtifact[];
  changed_files: string[];
  checks: CheckArtifact[];
  workers: WorkerArtifact[];
  unresolved_conflicts: string[];
  usage: Record<string, JsonValue>;
  terminal_status: string | null;
  final_summary: string | null;
  walkthrough: RunWalkthroughArtifact;
}

export interface RuntimeMetricsArtifact {
  total_input_tokens?: number;
  total_output_tokens?: number;
  total_tokens?: number;
  estimated_cost_usd?: number | null;
  calls_by_node?: Record<string, number>;
  spans?: Record<string, { calls?: number; errors?: number; duration_ms?: number }>;
  tags?: Record<string, string>;
  usage_by_node?: Record<string, { input_tokens?: number; output_tokens?: number; total_tokens?: number }>;
}
