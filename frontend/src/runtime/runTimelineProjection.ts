import type { RunEvent, RunStage, RunStageStatus } from "@/types/run";

const nodeStages: Record<string, RunStage> = {
  input: "context",
  context_injector: "context",
  planner: "plan",
  plan_approval: "plan",
  executor: "edit",
  sub_executor: "edit",
  tools: "edit",
  linter_node: "check",
  evaluator: "check",
};

export const stageForEvent = (event: RunEvent): RunStage | undefined => {
  if (event.type === "done") return "complete";
  if (event.type === "workspace_patch" || event.type === "approval_required") return "review";
  if (event.type === "plan_created" || event.type === "plan_step") return "plan";
  if (event.type === "check_result") return "check";
  if (event.node && nodeStages[event.node]) return nodeStages[event.node];
  if (event.type === "error") return "complete";
  return event.stage;
};

export const durationForEvent = (event: RunEvent) => {
  const duration = event.data?.duration_ms;
  return typeof duration === "number" ? duration : event.duration_ms;
};

export const deriveStageStates = (
  events: RunEvent[],
  visibleStages: RunStage[],
  isRunActive: boolean,
) => {
  const states = new Map<RunStage, RunStageStatus>();
  visibleStages.forEach(stage => states.set(stage, "pending"));

  for (const event of events) {
    const stage = stageForEvent(event);
    if (!stage || !states.has(stage)) continue;
    const index = visibleStages.indexOf(stage);
    visibleStages.slice(0, index).forEach(previous => states.set(previous, "complete"));

    const explicit = typeof event.data?.stage_status === "string"
      ? event.data.stage_status as RunStageStatus
      : event.stage_status;
    if (event.type === "approval_required") states.set(stage, "waiting");
    else if (event.type === "done") visibleStages.forEach(value => states.set(value, "complete"));
    else if (event.type === "error") states.set(stage, "failed");
    else states.set(stage, explicit || "active");
  }

  if (isRunActive && ![...states.values()].some(value => value === "active" || value === "waiting")) {
    states.set(visibleStages[0], "active");
  }
  return states;
};
