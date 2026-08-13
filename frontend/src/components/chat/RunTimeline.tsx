import { useEffect, useMemo, useState } from "react";
import {
  Activity,
  AlertTriangle,
  CheckCircle2,
  ChevronDown,
  ChevronRight,
  Circle,
  FileText,
  Loader2,
  Wrench,
  XCircle,
} from "lucide-react";
import { useRunEvents, type LiveRunEvent } from "@/contexts/RunContext";
import { useWorkbench } from "@/contexts/WorkbenchContext";
import type { JsonValue, RunStage } from "@/types/run";
import PlanChecklist from "./PlanChecklist";
import ToolCallCard from "./ToolCallCard";
import { eventsFromRunHistory, runsApi, type CapabilityReport, type RunDiagnostics } from "@/api/runs";
import { deriveStageStates, durationForEvent, stageForEvent } from "@/runtime/runTimelineProjection";
import type { RuntimeMetricsArtifact } from "@/types/artifact";

const stageLabels: Record<RunStage, string> = {
  context: "Context",
  plan: "Plan",
  edit: "Edit",
  check: "Check",
  review: "Review",
  complete: "Complete",
};

const secretKey = /token|secret|password|authorization|credential|api[-_]?key/i;
const sanitize = (value: JsonValue, depth = 0): JsonValue => {
  if (depth > 3) return "[nested]";
  if (typeof value === "string") return value.length > 500 ? `${value.slice(0, 500)}...` : value;
  if (Array.isArray(value)) return value.slice(0, 20).map((item) => sanitize(item, depth + 1));
  if (value && typeof value === "object") {
    return Object.fromEntries(Object.entries(value).slice(0, 30).map(([key, item]) => [
      key,
      secretKey.test(key) ? "[redacted]" : sanitize(item, depth + 1),
    ]));
  }
  return value;
};

const eventLabel = (event: LiveRunEvent) => {
  if (event.type === "approval_required") return "Waiting for approval";
  if (event.type === "workspace_patch") return "Prepared project changes";
  if (event.type === "plan_created") return "Prepared a plan";
  if (event.type === "done") return "Run completed";
  if (event.type === "error") return typeof event.content === "string" ? event.content : "Run failed";
  if (event.type === "status" && typeof event.content === "string") return event.content;
  const tool = event.tool_call?.name;
  if (tool) return `Used ${tool.replaceAll("_", " ")}`;
  return event.type.replaceAll("_", " ");
};

function ActivityRow({ event }: { event: LiveRunEvent }) {
  const [expanded, setExpanded] = useState(false);
  const failed = event.type === "error";
  const waiting = event.type === "approval_required";
  const complete = event.type === "done" || event.type === "tool_result";
  const Icon = failed ? XCircle : waiting ? AlertTriangle : complete ? CheckCircle2 : event.affected_files?.length ? FileText : Wrench;
  const details = event.tool_call?.args || event.data;
  const durationMs = durationForEvent(event);
  return (
    <div className="border-b border-border py-2 last:border-0">
      <div className="flex items-start gap-2">
        <Icon className={`mt-0.5 h-3.5 w-3.5 shrink-0 ${failed ? "text-destructive" : waiting ? "text-warning" : complete ? "text-success" : "text-muted-foreground"}`} />
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-2 text-xs">
            <span className="min-w-0 flex-1 truncate font-medium">{eventLabel(event)}</span>
            {durationMs != null && <span className="font-mono text-muted-foreground">{Math.round(durationMs)}ms</span>}
          </div>
          {!!event.affected_files?.length && <p className="mt-1 truncate font-mono text-xs text-muted-foreground">{event.affected_files.join(", ")}</p>}
        </div>
        {details && (
          <button type="button" onClick={() => setExpanded((value) => !value)} className="rounded p-0.5 text-muted-foreground hover:text-foreground" aria-label={expanded ? "Hide event details" : "Show event details"}>
            {expanded ? <ChevronDown className="h-3.5 w-3.5" /> : <ChevronRight className="h-3.5 w-3.5" />}
          </button>
        )}
      </div>
      {expanded && details && <pre className="mt-2 max-h-40 overflow-auto border-l-2 border-border pl-3 font-mono text-xs text-muted-foreground">{JSON.stringify(sanitize(details), null, 2)}</pre>}
    </div>
  );
}

function RuntimeMetricsSummary({ usage, history }: { usage: Record<string, JsonValue>; history: RunDiagnostics | null }) {
  const metrics = usage as RuntimeMetricsArtifact;
  const calls = history?.calls ?? Object.values(metrics.calls_by_node ?? {}).reduce((sum, value) => sum + value, 0);
  const spans = Object.entries(metrics.spans ?? {});
  if (!metrics.total_tokens && !calls && !spans.length && !history) return null;
  const categories = history?.categories ?? spans.reduce<Record<string, number>>((result, [name, span]) => {
    const lowered = name.toLowerCase();
    const category = lowered.endsWith(".model") || lowered.includes("provider") ? "provider_wait_ms"
      : lowered.includes("tool") ? "tool_time_ms"
      : lowered.includes("approval") || lowered.includes(".wait") ? "approval_wait_ms"
      : ["persist", "database", "checkpoint", "db."].some(marker => lowered.includes(marker)) ? "persistence_ms"
      : "local_compute_ms";
    result[category] = (result[category] ?? 0) + (span.duration_ms ?? 0);
    return result;
  }, {});
  const totalTokens = history?.tokens.total ?? metrics.total_tokens ?? 0;
  const estimatedCost = history?.cost.estimated_usd ?? metrics.estimated_cost_usd;
  const costStatus = history?.cost.status ?? (estimatedCost == null ? "unavailable" : estimatedCost === 0 ? "free" : "estimated");
  const categoryLabels: Record<string, string> = { provider_wait_ms: "provider", local_compute_ms: "local", tool_time_ms: "tools", approval_wait_ms: "approval", persistence_ms: "persistence" };
  const provider = history?.provider ?? metrics.tags?.provider;
  const model = history?.model ?? metrics.tags?.model;
  const cache = history?.cache ?? Object.fromEntries(Object.entries(metrics.tags ?? {}).filter(([name]) => name.endsWith("_cache")).map(([name, value]) => [name.replace(/_cache$/, ""), value]));
  return (
    <div className="border-b border-border py-2 text-xs">
      <div><span className="font-medium">Run metrics</span>{(provider || model) && <span className="ml-2 text-muted-foreground">{provider || "provider"} / {model || "model"}</span>}</div>
      <div className="mt-1 font-mono text-muted-foreground">{totalTokens} tokens · {calls} model calls · {costStatus === "unavailable" ? "cost unavailable" : costStatus === "free" ? "free" : `$${Number(estimatedCost).toFixed(6)} estimated`}</div>
      <div className="mt-1 flex flex-wrap gap-x-3 gap-y-1 font-mono text-muted-foreground">{Object.entries(categories).filter(([, duration]) => duration > 0).map(([name, duration]) => <span key={name}>{categoryLabels[name] || name} {Math.round(duration)}ms</span>)}</div>
      {!!spans.length && <details className="mt-1 text-muted-foreground"><summary className="cursor-pointer">Per-stage timing</summary><div className="mt-1 flex flex-wrap gap-x-3 gap-y-1 font-mono">{spans.map(([name, span]) => <span key={name}>{name} {Math.round(span.duration_ms ?? 0)}ms</span>)}</div></details>}
      {!!Object.keys(cache).length && <div className="mt-1 text-muted-foreground">Cache: {Object.entries(cache).map(([name, value]) => `${name} ${value}`).join(" · ")}</div>}
    </div>
  );
}

function CapabilitySummary({ report }: { report: CapabilityReport | null }) {
  if (!report) return null;
  return <div className="border-b border-border py-2 text-xs"><span className="font-medium">Capabilities</span><span className="ml-2 text-muted-foreground">{report.permission_profile} permissions</span>{report.unavailable.length ? <p className="mt-1 text-warning">Unavailable: {report.unavailable.join(", ")}</p> : <p className="mt-1 text-success">All configured capabilities available</p>}</div>;
}

export default function RunTimeline({
  sessionId,
  showEmpty = false,
}: {
  sessionId: string | null;
  showEmpty?: boolean;
}) {
  const { currentRunEvents, artifact, isRunActive, firstEventLatencyMs, hydrateRun } = useRunEvents();
  const { state } = useWorkbench();
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [historicalDiagnostics, setHistoricalDiagnostics] = useState<RunDiagnostics | null>(null);
  const [capabilities, setCapabilities] = useState<CapabilityReport | null>(null);

  useEffect(() => {
    setHistoricalDiagnostics(null);
    setCapabilities(null);
  }, [sessionId]);

  useEffect(() => {
    if (!sessionId || isRunActive) return;
    let current = true;
    runsApi.getSessionRuns(sessionId)
      .then(history => {
        if (current) {
          hydrateRun(sessionId, eventsFromRunHistory(history));
          setHistoricalDiagnostics(history.items?.[0]?.diagnostics ?? null);
          setCapabilities(history.capabilities ?? null);
        }
      })
      .catch(() => { /* Transcript loading remains usable without activity history. */ });
    return () => { current = false; };
  }, [hydrateRun, isRunActive, sessionId]);

  const visibleStages = useMemo<RunStage[]>(() => {
    const stages: RunStage[] = ["context"];
    if (state.mode === "plan" || state.mode === "goal") stages.push("plan");
    if (state.mode !== "ask") stages.push("edit");
    if (artifact.checks.length || currentRunEvents.some((event) => stageForEvent(event) === "check")) stages.push("check");
    if (state.pendingPatchCount || currentRunEvents.some((event) => stageForEvent(event) === "review")) stages.push("review");
    stages.push("complete");
    return stages;
  }, [artifact.checks.length, currentRunEvents, state.mode, state.pendingPatchCount]);

  const stageState = useMemo(() => {
    return deriveStageStates(currentRunEvents, visibleStages, isRunActive);
  }, [currentRunEvents, isRunActive, visibleStages]);

  if (!currentRunEvents.length && !isRunActive) {
    if (!showEmpty) return null;
    return (
      <section className="flex min-h-0 flex-1 flex-col items-center justify-center px-6 text-center" aria-label="Run activity">
        <Activity className="mb-3 h-6 w-6 text-muted-foreground" />
        <h2 className="text-sm font-medium">No run activity yet</h2>
        <p className="mt-1 max-w-72 text-xs text-muted-foreground">
          Start a task to see stages, tools, affected files, and results here.
        </p>
      </section>
    );
  }

  return (
    <section className="border-t border-border bg-card" aria-label="Run progress">
      <div className="flex min-h-11 items-center gap-2 px-3">
        <div className="flex min-w-0 flex-1 items-center overflow-x-auto">
          {visibleStages.map((stage, index) => {
            const status = stageState.get(stage) || "pending";
            return (
              <div key={stage} className="flex shrink-0 items-center">
                <span className={`flex items-center gap-1 rounded-full border px-2 py-1 text-xs ${
                  status === "complete" ? "border-success/40 bg-success/10 text-success" :
                  status === "active" ? "border-primary/40 bg-primary/10 text-primary" :
                  status === "waiting" ? "border-warning/40 bg-warning/10 text-warning" :
                  status === "failed" ? "border-destructive/40 bg-destructive/10 text-destructive" :
                  "border-border text-muted-foreground"
                }`}>
                  {status === "complete" ? <CheckCircle2 className="h-3 w-3" /> : status === "active" ? <Loader2 className="h-3 w-3 animate-spin" /> : <Circle className="h-3 w-3" />}
                  {stageLabels[stage]}
                </span>
                {index < visibleStages.length - 1 && <span className="mx-1 h-px w-3 bg-border" />}
              </div>
            );
          })}
        </div>
        <button type="button" onClick={() => setDrawerOpen((value) => !value)} className="flex shrink-0 items-center gap-1 rounded px-2 py-1 text-xs text-muted-foreground hover:bg-muted hover:text-foreground">
          <Activity className="h-3.5 w-3.5" /> Activity {drawerOpen ? <ChevronDown className="h-3.5 w-3.5" /> : <ChevronRight className="h-3.5 w-3.5" />}
        </button>
      </div>
      {drawerOpen && (
        <div className="max-h-[36vh] overflow-y-auto border-t border-border px-3">
          {firstEventLatencyMs != null && <div className="border-b border-border py-2 text-xs text-muted-foreground">First event in <span className="font-mono">{firstEventLatencyMs}ms</span></div>}
          <RuntimeMetricsSummary usage={artifact.usage} history={isRunActive ? null : historicalDiagnostics} />
          <CapabilitySummary report={capabilities} />
          {artifact.plan && <PlanChecklist plan={artifact.plan} completedSteps={artifact.steps.flatMap((step, index) => step.status === "completed" ? [index + 1] : [])} />}
          {artifact.tools.map(tool => <ToolCallCard key={tool.id} toolName={tool.name} args={tool.args} result={tool.result} status={tool.status} />)}
          {!!artifact.changed_files.length && <div className="border-b border-border py-2 text-xs"><span className="font-medium">Changed files</span><p className="mt-1 font-mono text-muted-foreground">{artifact.changed_files.join(", ")}</p></div>}
          {artifact.checks.map(check => <div key={check.id} className="border-b border-border py-2 text-xs"><span className="font-medium">{check.name}</span><span className={`ml-2 ${check.status === "passed" ? "text-success" : "text-destructive"}`}>{check.status}</span>{check.duration_ms != null && <span className="ml-2 font-mono text-muted-foreground">{Math.round(check.duration_ms)}ms</span>}</div>)}
          {currentRunEvents.map((event, index) => <ActivityRow key={event.id || `${event.type}-${index}`} event={event} />)}
        </div>
      )}
    </section>
  );
}
