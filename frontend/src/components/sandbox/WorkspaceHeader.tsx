import { useCallback, useEffect, useState } from "react";
import { Download, GitBranch, GitCommitHorizontal, History, Loader2, RefreshCcw } from "lucide-react";
import { toast } from "react-toastify";
import { Button } from "@/components/ui/button";
import { workspaceApi } from "@/api";
import type { Workspace, WorkspaceContext } from "@/types/project";
import { useWorkbench } from "@/contexts/WorkbenchContext";

export default function WorkspaceHeader({
  workspaceId,
  projectName,
  onRefresh,
}: {
  workspaceId: string;
  projectName: string;
  onRefresh?: () => void;
}) {
  const [workspace, setWorkspace] = useState<Workspace | null>(null);
  const [context, setContext] = useState<WorkspaceContext | null>(null);
  const [loading, setLoading] = useState(false);
  const [downloading, setDownloading] = useState(false);
  const { state, dispatch } = useWorkbench();

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const [workspaces, nextContext] = await Promise.all([
        workspaceApi.listWorkspaces(),
        workspaceApi.getContext(workspaceId),
      ]);
      setWorkspace(workspaces.find((item) => item.id === workspaceId) || null);
      setContext(nextContext);
    } finally {
      setLoading(false);
    }
  }, [workspaceId]);

  useEffect(() => { void load(); }, [load, state.refreshWorkspaceVersion]);

  const handleDownload = async () => {
    setDownloading(true);
    try {
      await workspaceApi.downloadWorkspace(workspaceId);
      toast.success("Project downloaded as ZIP");
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Failed to download project ZIP");
    } finally {
      setDownloading(false);
    }
  };

  return (
    <div className="flex min-w-0 items-center gap-2 sm:gap-2.5">
      <span className="max-w-44 truncate text-sm font-semibold text-foreground" title={projectName}>
        {projectName}
      </span>
      <span className="hidden items-center gap-1.5 rounded bg-muted/60 px-2 py-0.5 font-mono text-[11px] text-muted-foreground border border-border/80 sm:inline-flex">
        <GitBranch className="h-3 w-3 text-sky-400" />
        <span>{context?.git_branch || workspace?.git_branch || "main"}</span>
      </span>
      <span className="hidden items-center gap-1 rounded bg-muted/40 px-1.5 py-0.5 font-mono text-[11px] text-muted-foreground/80 md:inline-flex">
        <GitCommitHorizontal className="h-3 w-3" />
        <span>{(context?.git_head || workspace?.git_head)?.slice(0, 7) || "clean"}</span>
      </span>
      {loading && <Loader2 className="h-3.5 w-3.5 animate-spin text-muted-foreground" />}
      {onRefresh && (
        <Button variant="ghost" size="icon-sm" onClick={() => { onRefresh(); void load(); }} aria-label="Refresh project files" title="Refresh project files">
          <RefreshCcw className="h-3.5 w-3.5 text-muted-foreground hover:text-foreground" />
        </Button>
      )}
      <Button
        variant="ghost"
        size="icon-sm"
        onClick={() => void handleDownload()}
        disabled={downloading}
        aria-label="Export project as ZIP"
        title="Download project ZIP"
      >
        {downloading ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Download className="h-3.5 w-3.5 text-muted-foreground hover:text-foreground" />}
      </Button>
      <Button
        variant="ghost"
        size="icon-sm"
        onClick={() => dispatch({ type: "setCenterTab", tab: "checkpoints" })}
        aria-label="View snapshots"
        title="Snapshots & Revisions"
      >
        <History className="h-3.5 w-3.5 text-sky-400 hover:text-sky-300" />
      </Button>
    </div>
  );
}
