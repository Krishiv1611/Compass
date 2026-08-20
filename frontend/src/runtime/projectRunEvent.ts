import type {
  PlanStepArtifact,
  RunArtifact,
  RunWalkthroughArtifact,
  WorkerArtifact,
  WorkerStatus,
} from "@/types/artifact";
import type { JsonValue, RunEvent } from "@/types/run";

const emptyWalkthrough = (): RunWalkthroughArtifact => ({
  plan: null,
  worker_contributions: [],
  changed_files: [],
  checks: [],
  usage: {},
  unresolved_conflicts: [],
  terminal_status: null,
});

export function emptyRunArtifact(): RunArtifact {
  return {
    plan: null,
    steps: [],
    tools: [],
    changed_files: [],
    checks: [],
    workers: [],
    unresolved_conflicts: [],
    usage: {},
    terminal_status: null,
    final_summary: null,
    walkthrough: emptyWalkthrough(),
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

const workerEventTypes = new Set([
  "agent_started",
  "agent_progress",
  "agent_completed",
  "agent_failed",
]);

const workerStatuses = new Set<WorkerStatus>([
  "pending",
  "running",
  "completed",
  "failed",
  "blocked",
  "cancelled",
  "invalid",
]);

const fallbackWorkerStatus = (eventType: string): WorkerStatus => {
  if (eventType === "agent_completed") return "completed";
  if (eventType === "agent_failed") return "failed";
  return "running";
};

function updateWorker(result: RunArtifact, event: RunEvent, data: Record<string, JsonValue>) {
  if (!workerEventTypes.has(event.type) || typeof data.task_id !== "string" || !data.task_id.trim()) return;

  const current = result.workers.find(worker => worker.task_id === data.task_id);
  const status = typeof data.status === "string" && workerStatuses.has(data.status as WorkerStatus)
    ? data.status as WorkerStatus
    : current?.status ?? fallbackWorkerStatus(event.type);
  const streamedSummary = typeof event.content === "string" ? event.content : data.summary;
  const summary = typeof streamedSummary === "string" && streamedSummary.trim()
    ? streamedSummary.trim().slice(0, 2_000)
    : current?.summary;
  const worker: WorkerArtifact = {
    task_id: data.task_id,
    title: typeof data.title === "string" && data.title.trim() ? data.title.trim() : current?.title ?? data.task_id,
    status,
    duration_ms: typeof data.duration_ms === "number" && Number.isFinite(data.duration_ms)
      ? Math.max(0, data.duration_ms)
      : current?.duration_ms ?? 0,
    evidence_count: typeof data.evidence_count === "number" && Number.isFinite(data.evidence_count)
      ? Math.max(0, Math.floor(data.evidence_count))
      : current?.evidence_count ?? 0,
    ...(summary ? { summary } : {}),
  };
  const index = result.workers.findIndex(item => item.task_id === worker.task_id);
  if (index >= 0) result.workers[index] = worker;
  else result.workers.push(worker);
}

function refreshWalkthrough(result: RunArtifact) {
  result.walkthrough = {
    plan: result.plan,
    worker_contributions: result.workers.flatMap(worker =>
      worker.summary ? [`${worker.title}: ${worker.summary}`] : [],
    ),
    changed_files: [...result.changed_files],
    checks: structuredClone(result.checks),
    usage: { ...result.usage },
    unresolved_conflicts: [...result.unresolved_conflicts],
    terminal_status: result.terminal_status,
  };
}

export function projectRunEvent(artifact: RunArtifact, event: RunEvent): RunArtifact {
  const result = structuredClone(artifact);
  const data = dataOf(event);

  if (workerEventTypes.has(event.type)) {
    updateWorker(result, event, data);
  } else if (event.type === "plan_created" && typeof event.content === "string") {
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
    const id = String(data.id ?? `check-${event.seq ?? result.checks.length + 1}`);
    const value = {
      id,
      name: typeof event.content === "string" ? event.content : event.node ?? "Check",
      status: typeof data.status === "string" ? data.status : "unknown",
      duration_ms: typeof data.duration_ms === "number" ? data.duration_ms : null,
      details: data.details ?? null,
    };
    const index = result.checks.findIndex(check => check.id === id);
    if (index >= 0) result.checks[index] = value;
    else result.checks.push(value);
  } else if (event.type === "usage") {
    result.usage = { ...data };
  } else if (event.type === "status" && Array.isArray(data.conflicts)) {
    result.unresolved_conflicts = data.conflicts.filter(
      (conflict): conflict is string => typeof conflict === "string",
    );
  } else if (event.type === "run_waiting") {
    result.terminal_status = typeof data.status === "string" ? data.status : "waiting_for_approval";
  } else if (event.type === "done") {
    result.terminal_status = typeof data.status === "string" ? data.status : "completed";
    const usage = data.metrics ?? data.token_usage;
    if (usage && typeof usage === "object" && !Array.isArray(usage)) {
      result.usage = { ...usage };
    }
    result.final_summary = typeof event.content === "string"
      ? event.content
      : typeof data.assistant_content === "string" ? data.assistant_content : null;
    if (Array.isArray(data.unresolved_conflicts)) {
      result.unresolved_conflicts = data.unresolved_conflicts.filter(
        (conflict): conflict is string => typeof conflict === "string",
      );
    }
  } else if (event.type === "error") {
    result.terminal_status = "failed";
    result.final_summary = typeof event.content === "string" ? event.content : null;
  }

  refreshWalkthrough(result);

  return result;
}
