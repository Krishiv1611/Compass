export type ResumeAction =
  | "approve"
  | "always"
  | "deny"
  | "skip"
  | "execute_plan"
  | "revise_plan"
  | "cancel"
  | "answer";

export type InterruptKind =
  | "tool_approval"
  | "plan_approval"
  | "clarification";

export interface ResumePayload {
  action: ResumeAction;
  feedback?: string;
}
