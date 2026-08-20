import { useState } from "react";
import {
  AlertTriangle,
  CheckCircle2,
  ChevronDown,
  ChevronRight,
  Circle,
  Loader2,
  XCircle,
} from "lucide-react";

import type { RunWalkthroughArtifact, WorkerArtifact, WorkerStatus } from "@/types/artifact";

const statusTone: Record<WorkerStatus, string> = {
  pending: "border-border bg-muted/40 text-muted-foreground",
  running: "border-primary/40 bg-primary/10 text-primary",
  completed: "border-success/40 bg-success/10 text-success",
  failed: "border-destructive/40 bg-destructive/10 text-destructive",
  blocked: "border-warning/40 bg-warning/10 text-warning",
  cancelled: "border-border bg-muted/40 text-muted-foreground",
  invalid: "border-warning/40 bg-warning/10 text-warning",
};

const statusRail: Record<WorkerStatus, string> = {
  pending: "bg-border-strong",
  running: "bg-primary",
  completed: "bg-success",
  failed: "bg-destructive",
  blocked: "bg-warning",
  cancelled: "bg-border-strong",
  invalid: "bg-warning",
};

function StatusIcon({ status }: { status: WorkerStatus }) {
  if (status === "running") return <Loader2 aria-hidden="true" className="h-3 w-3 animate-spin" />;
  if (status === "completed") return <CheckCircle2 aria-hidden="true" className="h-3 w-3" />;
  if (status === "failed") return <XCircle aria-hidden="true" className="h-3 w-3" />;
  if (status === "blocked" || status === "invalid") return <AlertTriangle aria-hidden="true" className="h-3 w-3" />;
  return <Circle aria-hidden="true" className="h-3 w-3" />;
}

const statusLabel = (status: WorkerStatus) => status[0].toUpperCase() + status.slice(1);

const formatDuration = (durationMs: number) => {
  if (durationMs < 1_000) return `${Math.round(durationMs)}ms`;
  return `${(durationMs / 1_000).toFixed(1)}s`;
};

export default function WorkerTimeline({ workers }: { workers: WorkerArtifact[] }) {
  const [expandedTaskIds, setExpandedTaskIds] = useState<Set<string>>(() => new Set());

  if (!workers.length) return null;

  const activeCount = workers.filter(worker => worker.status === "running").length;
  const toggleSummary = (taskId: string) => {
    setExpandedTaskIds(current => {
      const next = new Set(current);
      if (next.has(taskId)) next.delete(taskId);
      else next.add(taskId);
      return next;
    });
  };

  return (
    <section className="border-t border-border bg-card" aria-label="Worker activity">
      <div className="flex h-8 items-center justify-between border-b border-border px-3 text-[11px]">
        <span className="font-medium text-foreground">Crew</span>
        <span className="font-mono text-muted-foreground">
          {activeCount ? `${activeCount} active · ` : ""}{workers.length} assigned
        </span>
      </div>
      <ul className="divide-y divide-border">
        {workers.map(worker => {
          const expanded = expandedTaskIds.has(worker.task_id);
          const summaryId = `worker-${worker.task_id}-summary`;
          return (
            <li key={worker.task_id} className="flex min-h-11 bg-card">
              <span aria-hidden="true" className={`w-0.5 shrink-0 ${statusRail[worker.status]}`} />
              <div className="min-w-0 flex-1 px-3 py-2">
                <div className="flex min-w-0 flex-wrap items-center gap-x-2 gap-y-1">
                  <span className="min-w-0 flex-1 truncate text-xs font-medium text-foreground" title={worker.title}>
                    {worker.title}
                  </span>
                  <span className={`inline-flex min-w-20 shrink-0 items-center justify-center gap-1 rounded-full border px-2 py-0.5 text-[11px] ${statusTone[worker.status]}`}>
                    <StatusIcon status={worker.status} />
                    {statusLabel(worker.status)}
                  </span>
                  <span className="w-14 shrink-0 text-right font-mono text-[11px] tabular-nums text-muted-foreground">
                    {formatDuration(worker.duration_ms)}
                  </span>
                  <span className="w-20 shrink-0 text-right font-mono text-[11px] tabular-nums text-muted-foreground">
                    {worker.evidence_count} evidence
                  </span>
                  {worker.summary && (
                    <button
                      type="button"
                      className="inline-flex h-6 w-6 shrink-0 items-center justify-center rounded text-muted-foreground hover:bg-muted hover:text-foreground"
                      aria-controls={summaryId}
                      aria-expanded={expanded}
                      aria-label={`${expanded ? "Hide" : "Show"} summary for ${worker.title}`}
                      onClick={() => toggleSummary(worker.task_id)}
                    >
                      {expanded ? <ChevronDown aria-hidden="true" className="h-3.5 w-3.5" /> : <ChevronRight aria-hidden="true" className="h-3.5 w-3.5" />}
                    </button>
                  )}
                </div>
                {expanded && worker.summary && (
                  <p id={summaryId} className="mt-2 border-l border-border pl-3 text-xs leading-5 text-muted-foreground">
                    {worker.summary}
                  </p>
                )}
              </div>
            </li>
          );
        })}
      </ul>
    </section>
  );
}

export function FinalWalkthrough({ walkthrough }: { walkthrough: RunWalkthroughArtifact }) {
  if (!walkthrough.terminal_status) return null;
  const totalTokens = typeof walkthrough.usage.total_tokens === "number"
    ? walkthrough.usage.total_tokens
    : null;
  return (
    <details className="border-b border-border py-2 text-xs" open>
      <summary className="cursor-pointer font-medium">Final walkthrough · {walkthrough.terminal_status}</summary>
      <dl className="mt-2 grid grid-cols-[5rem_1fr] gap-x-2 gap-y-1 text-muted-foreground">
        <dt>Plan</dt><dd className="whitespace-pre-wrap">{walkthrough.plan || "none"}</dd>
        <dt>Workers</dt><dd>{walkthrough.worker_contributions.join("; ") || "none"}</dd>
        <dt>Files</dt><dd className="font-mono">{walkthrough.changed_files.join(", ") || "none"}</dd>
        <dt>Checks</dt><dd>{walkthrough.checks.map(check => `${check.name}=${check.status}`).join(", ") || "none"}</dd>
        <dt>Usage</dt><dd className="font-mono">{totalTokens == null ? "unavailable" : `${totalTokens} tokens`}</dd>
        <dt>Conflicts</dt><dd className={walkthrough.unresolved_conflicts.length ? "text-warning" : ""}>{walkthrough.unresolved_conflicts.join("; ") || "none"}</dd>
      </dl>
    </details>
  );
}
