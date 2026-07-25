import { useCallback, useEffect, useState } from "react";
import { GitBranch, GitCommitHorizontal, Loader2, RefreshCcw } from "lucide-react";
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
  const { state } = useWorkbench();

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

  return (
    <div className="flex min-w-0 items-center gap-3">
      <span className="max-w-48 truncate text-sm font-semibold" title={projectName}>{projectName}</span>
      <span className="hidden items-center gap-1 font-mono text-xs text-muted-foreground sm:flex">
        <GitBranch className="h-3.5 w-3.5" /> {context?.git_branch || workspace?.git_branch || "local"}
      </span>
      <span className="hidden items-center gap-1 font-mono text-xs text-muted-foreground md:flex">
        <GitCommitHorizontal className="h-3.5 w-3.5" /> {(context?.git_head || workspace?.git_head)?.slice(0, 8) || "unindexed"}
      </span>
      {loading && <Loader2 className="h-3.5 w-3.5 animate-spin text-muted-foreground" />}
      {onRefresh && (
        <Button variant="ghost" size="icon-sm" onClick={() => { onRefresh(); void load(); }} aria-label="Refresh project files" title="Refresh project files">
          <RefreshCcw className="h-3.5 w-3.5" />
        </Button>
      )}
    </div>
  );
}
