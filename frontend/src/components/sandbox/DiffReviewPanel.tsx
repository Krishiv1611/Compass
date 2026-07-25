import { useCallback, useEffect, useMemo, useState } from "react";
import ReactDiffViewer from "react-diff-viewer-continued";
import {
  Check,
  CheckCircle2,
  ChevronDown,
  ChevronRight,
  FileCode2,
  Loader2,
  RotateCcw,
  X,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { toast } from "react-toastify";
import { useTheme } from "@/components/ThemeProvider";
import { patchesApi } from "@/api";
import { useWorkbench } from "@/contexts/WorkbenchContext";
import type { WorkspacePatch } from "@/types/patch";

interface PatchReviewProps {
  workspaceId: string;
  onResolved?: () => void;
  onOpenFile?: (path: string) => void;
}

type FileChange = {
  patchId: string;
  path: string;
  type: string;
  before: string;
  after: string;
  status: "pending" | "applied" | "rejected" | "reverted";
  createdAt?: string;
  diff?: string;
};

const diffStats = (change: FileChange) => {
  if (change.diff) {
    const lines = change.diff.split(/\r?\n/);
    return {
      additions: lines.filter((line) => line.startsWith("+") && !line.startsWith("+++")).length,
      deletions: lines.filter((line) => line.startsWith("-") && !line.startsWith("---")).length,
    };
  }
  const before = change.before.split(/\r?\n/);
  const after = change.after.split(/\r?\n/);
  let prefix = 0;
  while (prefix < before.length && prefix < after.length && before[prefix] === after[prefix]) prefix += 1;
  let suffix = 0;
  while (
    suffix < before.length - prefix &&
    suffix < after.length - prefix &&
    before[before.length - suffix - 1] === after[after.length - suffix - 1]
  ) suffix += 1;
  return {
    additions: Math.max(0, after.length - prefix - suffix),
    deletions: Math.max(0, before.length - prefix - suffix),
  };
};

export default function DiffReviewPanel({ workspaceId, onResolved, onOpenFile }: PatchReviewProps) {
  const [patches, setPatches] = useState<WorkspacePatch[]>([]);
  const [loading, setLoading] = useState(true);
  const [expanded, setExpanded] = useState<Record<string, boolean>>({});
  const [busy, setBusy] = useState<string | null>(null);
  const { resolvedTheme } = useTheme();
  const { state, notifyPatchesChanged, refreshWorkspace } = useWorkbench();

  const fetchPatches = useCallback(async () => {
    try {
      setPatches(await patchesApi.getPatches(workspaceId));
    } catch {
      toast.error("Failed to load project changes", { toastId: "patch-load-error" });
    } finally {
      setLoading(false);
    }
  }, [workspaceId]);

  useEffect(() => {
    fetchPatches();
  }, [fetchPatches, state.patchesVersion]);

  const changes = useMemo<FileChange[]>(() =>
    patches.flatMap((patch) => (patch.changes || []).map((change) => ({
      patchId: patch.id,
      path: change.path,
      type: change.type || "edit",
      before: change.before ?? "",
      after: change.after ?? change.content ?? "",
      status: change.status || patch.status || "pending",
      createdAt: patch.created_at,
      diff: change.diff,
    }))), [patches]);

  const pending = changes.filter((change) => change.status === "pending");
  const totals = changes.reduce((result, change) => {
    const stats = diffStats(change);
    return { additions: result.additions + stats.additions, deletions: result.deletions + stats.deletions };
  }, { additions: 0, deletions: 0 });

  const finish = async () => {
    await fetchPatches();
    onResolved?.();
    notifyPatchesChanged();
    refreshWorkspace();
  };

  const resolveFile = async (change: FileChange, action: "apply" | "reject" | "undo") => {
    const key = `${change.patchId}:${change.path}:${action}`;
    setBusy(key);
    try {
      await patchesApi.resolvePatchFile(workspaceId, change.patchId, change.path, action);
      toast.success(action === "apply" ? "File applied" : action === "reject" ? "File rejected" : "File reverted");
      await finish();
    } catch (error) {
      toast.error(error instanceof Error ? error.message : `Could not ${action} file`);
    } finally {
      setBusy(null);
    }
  };

  const resolveAll = async (action: "apply" | "reject") => {
    setBusy(action);
    try {
      if (action === "apply") await patchesApi.acceptAllPatches(workspaceId);
      else await patchesApi.rejectAllPatches(workspaceId);
      toast.success(action === "apply" ? "All changes applied" : "All changes rejected");
      await finish();
    } catch (error) {
      toast.error(error instanceof Error ? error.message : `Could not ${action} changes`);
    } finally {
      setBusy(null);
    }
  };

  if (loading) {
    return <div className="flex h-full items-center justify-center gap-2 text-sm text-muted-foreground"><Loader2 className="h-4 w-4 animate-spin" /> Loading changes</div>;
  }

  return (
    <div className="flex h-full flex-col overflow-hidden bg-background">
      <div className="flex flex-wrap items-center justify-between gap-3 border-b border-border bg-muted/20 px-4 py-3">
        <div>
          <div className="flex items-center gap-2">
            <h2 className="text-sm font-semibold">Project changes</h2>
            <Badge variant={pending.length ? "default" : "secondary"}>{pending.length} pending</Badge>
          </div>
          <div className="mt-1 flex gap-3 font-mono text-xs text-muted-foreground">
            <span className="text-success">+{totals.additions}</span>
            <span className="text-destructive">-{totals.deletions}</span>
            <span>{changes.length} files</span>
          </div>
        </div>
        {pending.length > 0 && (
          <div className="flex items-center gap-2">
            <Button size="sm" variant="outline" onClick={() => resolveAll("reject")} disabled={!!busy}>
              <X className="mr-1 h-3.5 w-3.5" /> Reject all
            </Button>
            <Button size="sm" onClick={() => resolveAll("apply")} disabled={!!busy}>
              <Check className="mr-1 h-3.5 w-3.5" /> Apply all
            </Button>
          </div>
        )}
      </div>

      <div className="min-h-0 flex-1 overflow-y-auto">
        {changes.length === 0 ? (
          <div className="flex h-full items-center justify-center px-6 text-center text-sm text-muted-foreground">No project changes to review.</div>
        ) : changes.map((change) => {
          const key = `${change.patchId}:${change.path}`;
          const isExpanded = expanded[key] ?? change.status === "pending";
          const actionBusy = busy?.startsWith(key);
          return (
            <section key={key} className="border-b border-border">
              <div className="flex min-h-12 items-center gap-2 px-3">
                <button type="button" className="rounded p-1 hover:bg-muted" onClick={() => setExpanded((state) => ({ ...state, [key]: !isExpanded }))} title={isExpanded ? "Collapse diff" : "Expand diff"}>
                  {isExpanded ? <ChevronDown className="h-3.5 w-3.5" /> : <ChevronRight className="h-3.5 w-3.5" />}
                </button>
                <button type="button" className="flex min-w-0 flex-1 items-center gap-2 text-left" onClick={() => onOpenFile?.(change.path)}>
                  <FileCode2 className="h-4 w-4 shrink-0 text-muted-foreground" />
                  <span className="truncate font-mono text-xs">{change.path}</span>
                  <StatusBadge status={change.status} />
                </button>
                <div className="flex shrink-0 items-center gap-1">
                  {change.status === "pending" && (
                    <>
                      <Button variant="ghost" size="icon-sm" onClick={() => resolveFile(change, "reject")} disabled={actionBusy} title="Reject file"><X className="h-3.5 w-3.5 text-destructive" /></Button>
                      <Button variant="ghost" size="icon-sm" onClick={() => resolveFile(change, "apply")} disabled={actionBusy} title="Apply file"><Check className="h-3.5 w-3.5 text-success" /></Button>
                    </>
                  )}
                  {change.status === "applied" && (
                    <Button variant="ghost" size="icon-sm" onClick={() => resolveFile(change, "undo")} disabled={actionBusy} title="Undo file"><RotateCcw className="h-3.5 w-3.5" /></Button>
                  )}
                </div>
              </div>
              {isExpanded && (
                <div className="overflow-x-auto border-t border-border text-xs">
                  <ReactDiffViewer
                    oldValue={change.before}
                    newValue={change.after}
                    splitView
                    useDarkTheme={resolvedTheme === "dark"}
                    leftTitle="Original"
                    rightTitle="Proposed"
                  />
                </div>
              )}
            </section>
          );
        })}
      </div>
    </div>
  );
}

function StatusBadge({ status }: { status: FileChange["status"] }) {
  const labels = {
    pending: "Pending",
    applied: "Applied",
    rejected: "Rejected",
    reverted: "Reverted",
  };
  return (
    <Badge variant="outline" className={`ml-auto h-5 shrink-0 text-xs ${
      status === "applied" ? "border-success/40 text-success" :
      status === "pending" ? "border-warning/40 text-warning" :
      "text-muted-foreground"
    }`}>
      {status === "applied" && <CheckCircle2 className="mr-1 h-3 w-3" />}
      {labels[status]}
    </Badge>
  );
}
