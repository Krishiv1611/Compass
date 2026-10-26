import { useCallback, useEffect, useState } from "react";
import { AlertTriangle, CheckCircle, Clock, FileCode, History, Loader2, RefreshCw, RotateCcw } from "lucide-react";
import { toast } from "react-toastify";
import { checkpointsApi, type CheckpointSummary, type RestorePreview } from "@/api";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { ScrollArea } from "@/components/ui/scroll-area";
import { useWorkbench } from "@/contexts/WorkbenchContext";

export default function CheckpointsPanel({ workspaceId }: { workspaceId: string }) {
  const { state, dispatch } = useWorkbench();
  const [checkpoints, setCheckpoints] = useState<CheckpointSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [restoringId, setRestoringId] = useState<string | null>(null);
  const [activePreview, setActivePreview] = useState<RestorePreview | null>(null);
  const [loadingPreviewId, setLoadingPreviewId] = useState<string | null>(null);

  const loadCheckpoints = useCallback(async () => {
    if (!workspaceId) return;
    setLoading(true);
    try {
      const data = await checkpointsApi.listCheckpoints(workspaceId);
      setCheckpoints(data);
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Failed to load checkpoints");
    } finally {
      setLoading(false);
    }
  }, [workspaceId]);

  useEffect(() => {
    void loadCheckpoints();
  }, [loadCheckpoints, state.checkpointsVersion]);

  const handlePreview = async (checkpointId: string) => {
    if (activePreview?.checkpoint_id === checkpointId) {
      setActivePreview(null);
      return;
    }
    setLoadingPreviewId(checkpointId);
    try {
      const preview = await checkpointsApi.previewRestore(workspaceId, checkpointId);
      setActivePreview(preview);
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Failed to load restore preview");
    } finally {
      setLoadingPreviewId(null);
    }
  };

  const handleRestore = async (checkpointId: string, force = false) => {
    if (!window.confirm("Restore this checkpoint? Unsaved changes in your project may be overwritten.")) {
      return;
    }
    setRestoringId(checkpointId);
    try {
      await checkpointsApi.restoreCheckpoint(workspaceId, checkpointId, force);
      toast.success("Checkpoint restored successfully");
      dispatch({ type: "refreshWorkspace" });
      dispatch({ type: "patchesChanged" });
      setActivePreview(null);
      await loadCheckpoints();
    } catch (err) {
      const msg = err instanceof Error ? err.message : "Failed to restore checkpoint";
      toast.error(msg);
    } finally {
      setRestoringId(null);
    }
  };

  if (loading) {
    return (
      <div className="flex h-full items-center justify-center gap-2 text-sm text-muted-foreground">
        <Loader2 className="h-4 w-4 animate-spin" /> Loading snapshots…
      </div>
    );
  }

  return (
    <div className="flex h-full flex-col bg-background">
      <div className="flex h-11 shrink-0 items-center justify-between border-b border-border px-4">
        <div className="flex items-center gap-2">
          <History className="h-4 w-4 text-primary" />
          <span className="text-sm font-medium">Workspace Checkpoints</span>
          <Badge variant="secondary" className="text-xs">{checkpoints.length}</Badge>
        </div>
        <Button size="icon-sm" variant="ghost" onClick={() => void loadCheckpoints()} title="Refresh checkpoints">
          <RefreshCw className="h-4 w-4" />
        </Button>
      </div>

      <ScrollArea className="flex-1 p-4">
        {checkpoints.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-12 text-center text-sm text-muted-foreground">
            <History className="mb-2 h-8 w-8 opacity-40" />
            <p className="font-medium">No checkpoints recorded yet</p>
            <p className="mt-1 text-xs text-muted-foreground/80 max-w-sm">
              Compass automatically takes non-destructive file snapshots during agent runs and manual edits so you can safely rollback at any time.
            </p>
          </div>
        ) : (
          <div className="space-y-3">
            {checkpoints.map((cp) => {
              const isPreviewOpen = activePreview?.checkpoint_id === cp.id;
              const isRestoring = restoringId === cp.id;
              const dateStr = new Date(cp.created_at).toLocaleString();

              return (
                <div
                  key={cp.id}
                  className="rounded-lg border border-border/60 bg-card/40 p-3.5 transition-colors hover:border-border hover:bg-card/70"
                >
                  <div className="flex items-start justify-between gap-3">
                    <div className="min-w-0 flex-1">
                      <div className="flex items-center gap-2">
                        <span className="font-mono text-xs font-semibold text-primary">
                          {cp.id.slice(0, 12)}
                        </span>
                        {cp.label && (
                          <Badge variant="outline" className="text-[10px] font-normal">
                            {cp.label}
                          </Badge>
                        )}
                      </div>
                      <div className="mt-1 flex items-center gap-1.5 text-xs text-muted-foreground">
                        <Clock className="h-3 w-3" />
                        <span>{dateStr}</span>
                        <span>•</span>
                        <span>{cp.files.length} file{cp.files.length !== 1 ? "s" : ""}</span>
                      </div>
                    </div>

                    <div className="flex items-center gap-1.5 shrink-0">
                      <Button
                        size="sm"
                        variant="ghost"
                        onClick={() => void handlePreview(cp.id)}
                        disabled={loadingPreviewId === cp.id || isRestoring}
                        className="text-xs h-7 px-2"
                      >
                        {loadingPreviewId === cp.id ? (
                          <Loader2 className="h-3 w-3 animate-spin" />
                        ) : (
                          "Preview"
                        )}
                      </Button>
                      <Button
                        size="sm"
                        variant="outline"
                        onClick={() => void handleRestore(cp.id)}
                        disabled={isRestoring}
                        className="text-xs h-7 px-2.5 gap-1 border-primary/30 text-primary hover:bg-primary/10"
                      >
                        {isRestoring ? (
                          <Loader2 className="h-3 w-3 animate-spin" />
                        ) : (
                          <RotateCcw className="h-3 w-3" />
                        )}
                        Restore
                      </Button>
                    </div>
                  </div>

                  {isPreviewOpen && activePreview && (
                    <div className="mt-3 rounded-md border border-border/80 bg-muted/40 p-2.5 text-xs">
                      <div className="font-medium text-foreground mb-1.5 flex items-center gap-1.5">
                        <CheckCircle className="h-3.5 w-3.5 text-success" />
                        Changes to apply ({activePreview.changes.length} files):
                      </div>
                      <ul className="space-y-1 pl-4 list-disc text-muted-foreground font-mono text-[11px]">
                        {activePreview.changes.map((change) => (
                          <li key={change}>{change}</li>
                        ))}
                      </ul>

                      {activePreview.conflicts.length > 0 && (
                        <div className="mt-2.5 rounded border border-destructive/40 bg-destructive/10 p-2 text-destructive">
                          <div className="flex items-center gap-1.5 font-medium">
                            <AlertTriangle className="h-3.5 w-3.5" />
                            Conflicts detected ({activePreview.conflicts.length}):
                          </div>
                          <ul className="mt-1 space-y-0.5 pl-4 list-disc font-mono text-[11px]">
                            {activePreview.conflicts.map((conflict) => (
                              <li key={conflict}>{conflict}</li>
                            ))}
                          </ul>
                          <Button
                            size="sm"
                            variant="destructive"
                            onClick={() => void handleRestore(cp.id, true)}
                            disabled={isRestoring}
                            className="mt-2 text-xs h-6 px-2"
                          >
                            Force Restore
                          </Button>
                        </div>
                      )}
                    </div>
                  )}

                  {!isPreviewOpen && cp.files.length > 0 && (
                    <div className="mt-2 flex flex-wrap gap-1.5">
                      {cp.files.slice(0, 4).map((f) => (
                        <span
                          key={f.path}
                          className="inline-flex items-center gap-1 rounded bg-muted/50 px-1.5 py-0.5 font-mono text-[10px] text-muted-foreground"
                        >
                          <FileCode className="h-2.5 w-2.5" />
                          {f.path.split("/").pop()}
                        </span>
                      ))}
                      {cp.files.length > 4 && (
                        <span className="text-[10px] text-muted-foreground self-center">
                          +{cp.files.length - 4} more
                        </span>
                      )}
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        )}
      </ScrollArea>
    </div>
  );
}
