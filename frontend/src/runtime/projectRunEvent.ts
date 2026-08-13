import type { RunArtifact, PlanStepArtifact } from "@/types/artifact";
import type { JsonValue, RunEvent } from "@/types/run";

export function emptyRunArtifact(): RunArtifact {
  return {
    plan: null,
    steps: [],
    tools: [],
    changed_files: [],
    checks: [],
    usage: {},
    terminal_status: null,
    final_summary: null,
  };
}

function planSteps(plan: string): PlanStepArtifact[] {
  const lines = plan.split(/\r?\n/).map(line => line.trim()).filter(Boolean);
  const numbered = lines.flatMap(line => {
    const match = line.match(/^\d+[.)]\s*(.+)$/);
    return match ? [match[1].trim()] : [];
  });
  const values = numbered.length ? numbered : plan.trim() ? [plan.trim()] : [];
  return values.map((text, index) => ({ id: `step-${index + 1}`, text, status: "pending" }));
}

const dataOf = (event: RunEvent): Record<string, JsonValue> => event.data ?? {};

export function projectRunEvent(artifact: RunArtifact, event: RunEvent): RunArtifact {
  const result = structuredClone(artifact);
  const data = dataOf(event);

  if (event.type === "plan_created" && typeof event.content === "string") {
    result.plan = event.content;
    result.steps = planSteps(event.content);
  } else if (event.type === "plan_step") {
    const step = data.step;
    const status = data.status;
    if (typeof step === "number" && step > 0 && step <= result.steps.length &&
        typeof status === "string" && ["pending", "active", "completed", "failed"].includes(status)) {
      result.steps[step - 1].status = status as PlanStepArtifact["status"];
    }
  } else if (event.type === "tool_call" && event.tool_call?.id && event.tool_call.name) {
    const existing = result.tools.find(tool => tool.id === event.tool_call?.id);
    if (existing) {
      existing.name = event.tool_call.name;
      existing.args = event.tool_call.args ?? {};
    } else {
      result.tools.push({
        id: event.tool_call.id,
        name: event.tool_call.name,
        args: event.tool_call.args ?? {},
        result: undefined,
        status: "running",
      });
    }
  } else if (event.type === "tool_result" && event.tool_call_id) {
    const existing = result.tools.find(tool => tool.id === event.tool_call_id);
    if (existing) {
      existing.result = event.content;
      existing.status = data.status === "error" ? "error" : "completed";
    }
  } else if (event.type === "workspace_patch") {
    const files = data.affected_files;
    if (Array.isArray(files)) {
      for (const path of files) {
        if (typeof path === "string" && !result.changed_files.includes(path)) result.changed_files.push(path);
      }
    }
  } else if (event.type === "check_result") {
    result.checks.push({
      id: `check-${event.seq ?? result.checks.length + 1}`,
      name: typeof event.content === "string" ? event.content : event.node ?? "Check",
      status: typeof data.status === "string" ? data.status : "unknown",
      duration_ms: typeof data.duration_ms === "number" ? data.duration_ms : null,
      details: data.details ?? null,
    });
  } else if (event.type === "usage") {
    result.usage = { ...data };
  } else if (event.type === "run_waiting") {
    result.terminal_status = typeof data.status === "string" ? data.status : "waiting_for_approval";
  } else if (event.type === "done") {
    result.terminal_status = typeof data.status === "string" ? data.status : "completed";
    if (data.token_usage && typeof data.token_usage === "object" && !Array.isArray(data.token_usage)) {
      result.usage = { ...data.token_usage };
    }
    result.final_summary = typeof event.content === "string"
      ? event.content
      : typeof data.assistant_content === "string" ? data.assistant_content : null;
  } else if (event.type === "error") {
    result.terminal_status = "failed";
    result.final_summary = typeof event.content === "string" ? event.content : null;
  }

  return result;
}
