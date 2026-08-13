export type JsonValue =
  | string
  | number
  | boolean
  | null
  | JsonValue[]
  | { [key: string]: JsonValue };

export type RunStage = "context" | "plan" | "edit" | "check" | "review" | "complete";
export type RunStageStatus = "pending" | "active" | "waiting" | "complete" | "failed";

export interface RunEvent {
  id?: string;
  type: string;
  content?: JsonValue;
  data?: Record<string, JsonValue>;
  tool_call?: {
    id?: string;
    name?: string;
    args?: Record<string, JsonValue>;
    result?: JsonValue;
  };
  tool_call_id?: string;
  run_id?: string;
  session_id?: string;
  node?: string;
  seq?: number;
  stage?: RunStage;
  stage_status?: RunStageStatus;
  duration_ms?: number;
  affected_files?: string[];
  created_at?: string;
}

export interface RunState {
  events: RunEvent[];
  isActive: boolean;
  sessionId: string | null;
  startedAt: string | null;
}
