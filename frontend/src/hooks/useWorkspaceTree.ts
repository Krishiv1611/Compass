import { useState, useCallback, useEffect } from "react";
import { workspaceApi } from "@/api";
import type { FileNode } from "@/components/sandbox/FileExplorer";
import { useWorkbench } from "@/contexts/WorkbenchContext";

export function useWorkspaceTree(activeWorkspaceId: string | null) {
  const { state } = useWorkbench();
  const [files, setFiles] = useState<FileNode[]>([]);
  const [projectName, setProjectName] = useState("No folder open");
  const [projectSelected, setProjectSelected] = useState(false);

  const refreshTree = useCallback(async (wsId: string, signal?: AbortSignal) => {
    try {
      const data = await workspaceApi.getTree(wsId, signal);
      if (signal?.aborted || wsId !== activeWorkspaceId) return;
      setFiles((data.tree || data.children || []) as FileNode[]);
      setProjectSelected(true);
      setProjectName(state.projectName || "Untitled workspace");
    } catch (error) {
      if (signal?.aborted) return;
      console.error(error);
      setProjectSelected(false);
      setProjectName("Failed to load workspace");
      setFiles([]);
    }
  }, [activeWorkspaceId, state.projectName]);

  useEffect(() => {
    if (activeWorkspaceId) {
      setFiles([]);
      setProjectSelected(false);
      const controller = new AbortController();
      void refreshTree(activeWorkspaceId, controller.signal);
      return () => controller.abort();
    } else {
      setFiles([]);
      setProjectSelected(false);
      setProjectName("No folder open");
    }
  }, [activeWorkspaceId, refreshTree, state.refreshWorkspaceVersion]);

  return { files, projectName, projectSelected, refreshTree };
}
