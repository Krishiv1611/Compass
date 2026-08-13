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

export interface RunArtifact {
  plan: string | null;
  steps: PlanStepArtifact[];
  tools: ToolArtifact[];
  changed_files: string[];
  checks: CheckArtifact[];
  usage: Record<string, JsonValue>;
  terminal_status: string | null;
  final_summary: string | null;
}
