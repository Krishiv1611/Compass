import { useCallback, useEffect, useMemo, useState } from "react";
import { lazy, Suspense, useRef } from "react";
import { Code2, GitPullRequest, Globe, History, Loader2, Save, Terminal } from "lucide-react";
import { toast } from "react-toastify";
import { Allotment } from "allotment";
import "allotment/dist/style.css";
import { workspaceApi } from "@/api";
import { useWorkbench } from "@/contexts/WorkbenchContext";
import type { CenterTab } from "@/contexts/WorkbenchContext";
import { useWorkspaceTree } from "@/hooks/useWorkspaceTree";
import type { FileNode } from "@/components/sandbox/FileExplorer";
import FileExplorer from "@/components/sandbox/FileExplorer";
import WorkspaceHeader from "@/components/sandbox/WorkspaceHeader";
import { Button } from "@/components/ui/button";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import ProDrawer from "@/components/workbench/ProDrawer";
import { beginLoad, editFile, emptyEditorState, invalidateWorkspace, isDirty as entryIsDirty, markSaved, selectEntry, shouldReloadEntry, storeLoadedFile } from "./editorState";

const DiffReviewPanel = lazy(() => import("@/components/sandbox/DiffReviewPanel"));
const WebPreview = lazy(() => import("@/components/sandbox/WebPreview"));
const CodeMirrorEditor = lazy(() => import("@/components/sandbox/CodeMirrorEditor"));
const CheckpointsPanel = lazy(() => import("@/components/sandbox/CheckpointsPanel"));
const panelFallback = <div className="flex h-full items-center justify-center gap-2 text-sm text-muted-foreground"><Loader2 className="h-4 w-4 animate-spin" /> Loading panel</div>;

const languageFromName = (name: string) => {
  const extension = name.toLowerCase().split(".").pop();
  return ({ py: "python", ts: "typescript", tsx: "typescript", js: "javascript", jsx: "javascript", json: "json", md: "markdown", css: "css", html: "html" } as Record<string, string>)[extension || ""] || "text";
};

export default function CenterWorkbench({ activeWorkspaceId }: { activeWorkspaceId: string | null }) {
  const { state, dispatch, openFile, openPreview, refreshWorkspace, notifyPatchesChanged } = useWorkbench();
  const { files, projectName, projectSelected, refreshTree } = useWorkspaceTree(activeWorkspaceId);
  const [editorState, setEditorState] = useState(emptyEditorState);
  const [loadingPath, setLoadingPath] = useState<string | null>(null);
  const loadGeneration = useRef(0);
  const loadController = useRef<AbortController | null>(null);
  const [previewFiles, setPreviewFiles] = useState<Record<string, { file?: { contents: string } }> | null>(null);
  const [isDesktop, setIsDesktop] = useState(() => window.matchMedia("(min-width: 1024px)").matches);

  useEffect(() => {
    const media = window.matchMedia("(min-width: 1024px)");
    const update = (event: MediaQueryListEvent) => setIsDesktop(event.matches);
    setIsDesktop(media.matches);
    media.addEventListener("change", update);
    return () => media.removeEventListener("change", update);
  }, []);

  const activeFile = state.activeFile;
  const entry = activeFile && activeWorkspaceId ? selectEntry(editorState, activeWorkspaceId, activeFile.path) : undefined;
  const code = entry?.content ?? "";
  const isDirty = Boolean(activeFile && activeWorkspaceId && entryIsDirty(editorState, activeWorkspaceId, activeFile.path));

  const loadFile = useCallback(async (file: FileNode) => {
    if (file.type !== "file" || !activeWorkspaceId) return;
    if (activeFile && activeFile.path !== file.path && isDirty && !window.confirm(`Discard unsaved changes in ${activeFile.name}?`)) return;
    openFile({ path: file.path, name: file.name, type: "file" });
    if (selectEntry(editorState, activeWorkspaceId, file.path)?.invalidated === false) return;
    loadController.current?.abort();
    const controller = new AbortController();
    loadController.current = controller;
    const generation = ++loadGeneration.current;
    setEditorState(value => beginLoad(value, activeWorkspaceId, file.path, generation));
    setLoadingPath(file.path);
    try {
      const response = await workspaceApi.getFile(activeWorkspaceId, file.path, controller.signal);
      setEditorState(value => storeLoadedFile(value, { workspaceId: activeWorkspaceId, path: file.path, content: response.content, generation }));
    } catch (error) {
      if (controller.signal.aborted) return;
      toast.error(error instanceof Error ? error.message : "Could not read file");
    } finally {
      if (generation === loadGeneration.current) setLoadingPath(null);
    }
  }, [activeFile, activeWorkspaceId, editorState, isDirty, openFile]);

  useEffect(() => {
    if (!activeFile || !activeWorkspaceId || !shouldReloadEntry(editorState, activeWorkspaceId, activeFile.path)) return;
    void loadFile(activeFile);
  }, [activeFile, activeWorkspaceId, editorState, loadFile]);

  const saveFile = async () => {
    if (!activeFile || !activeWorkspaceId || !isDirty) return;
    try {
      await workspaceApi.updateFile(activeWorkspaceId, activeFile.path, code);
      setEditorState(value => markSaved(value, activeWorkspaceId, activeFile.path, code));
      refreshWorkspace();
      toast.success("File saved");
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Could not save file");
    }
  };

  useEffect(() => {
    const onKeyDown = (event: KeyboardEvent) => {
      if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === "s") {
        event.preventDefault();
        void saveFile();
      }
      if ((event.ctrlKey || event.metaKey) && event.key === "`") {
        event.preventDefault();
        dispatch({ type: "setProDrawer", open: !state.proDrawerOpen });
      }
    };
    const onBeforeUnload = (event: BeforeUnloadEvent) => {
      if (!isDirty) return;
      event.preventDefault();
      event.returnValue = "";
    };
    window.addEventListener("keydown", onKeyDown);
    window.addEventListener("beforeunload", onBeforeUnload);
    return () => { window.removeEventListener("keydown", onKeyDown); window.removeEventListener("beforeunload", onBeforeUnload); };
  });

  useEffect(() => {
    if (activeWorkspaceId) setEditorState(value => invalidateWorkspace(value, activeWorkspaceId));
  }, [activeWorkspaceId, state.patchesVersion]);

  // Pre-load preview files whenever workspace or patches change (Live Canvas sync)
  useEffect(() => {
    if (!activeWorkspaceId) {
      setPreviewFiles(null);
      return;
    }
    let cancelled = false;
    workspaceApi.exportWorkspaceJson(activeWorkspaceId)
      .then((data) => {
        if (!cancelled) setPreviewFiles(data as Record<string, { file?: { contents: string } }>);
      })
      .catch(() => {
        // Workspace may still be bootstrapping
      });
    return () => { cancelled = true; };
  }, [activeWorkspaceId, state.patchesVersion, state.refreshWorkspaceVersion]);

  useEffect(() => {
    if (activeWorkspaceId) dispatch({ type: "setWorkspaceDirty", workspaceId: activeWorkspaceId, dirty: isDirty });
  }, [activeWorkspaceId, dispatch, isDirty]);

  const createPath = async (parentPath: string, type: "file" | "folder") => {
    if (!activeWorkspaceId) return;
    const name = window.prompt(type === "file" ? "File name" : "Folder name")?.trim();
    if (!name) return;
    const path = parentPath ? `${parentPath}/${name}` : name;
    try {
      await workspaceApi.createFile(activeWorkspaceId, path, type);
      await refreshTree(activeWorkspaceId);
      if (type === "file") void loadFile({ path, name, type: "file" });
    } catch (error) { toast.error(error instanceof Error ? error.message : "Could not create path"); }
  };

  const renamePath = async (path: string) => {
    if (!activeWorkspaceId) return;
    const currentName = path.split("/").pop() || path;
    const name = window.prompt("New name", currentName)?.trim();
    if (!name || name === currentName) return;
    const parent = path.includes("/") ? path.slice(0, path.lastIndexOf("/")) : "";
    try {
      await workspaceApi.renameFile(activeWorkspaceId, path, parent ? `${parent}/${name}` : name);
      await refreshTree(activeWorkspaceId);
    } catch (error) { toast.error(error instanceof Error ? error.message : "Could not rename path"); }
  };

  const deletePath = async (path: string) => {
    if (!activeWorkspaceId || !window.confirm(`Delete ${path}?`)) return;
    try {
      await workspaceApi.deleteFile(activeWorkspaceId, path);
      await refreshTree(activeWorkspaceId);
    } catch (error) { toast.error(error instanceof Error ? error.message : "Could not delete path"); }
  };

  const preparePreview = async () => {
    if (!activeWorkspaceId) return;
    try {
      setPreviewFiles(await workspaceApi.exportWorkspaceJson(activeWorkspaceId) as Record<string, { file?: { contents: string } }>);
      openPreview();
      dispatch({ type: "setMobileDestination", destination: "editor" });
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Could not prepare preview");
    }
  };

  const activeLanguage = useMemo(() => languageFromName(activeFile?.name || ""), [activeFile?.name]);
  if (!projectSelected || !activeWorkspaceId) return <div className="flex h-full items-center justify-center bg-background px-6 text-center text-sm text-muted-foreground">Select or create a project to open the workbench.</div>;

  const explorer = <FileExplorer files={files} onFileSelect={(file) => void loadFile(file)} activePath={activeFile?.path} projectName={projectName} onCreate={(parent, type) => void createPath(parent, type)} onRename={(path) => void renamePath(path)} onDelete={(path) => void deletePath(path)} />;
  const mainPanel = (
    <Tabs value={state.centerTab} onValueChange={(tab) => dispatch({ type: "setCenterTab", tab: tab as CenterTab })} className="flex h-full flex-col">
      <div className="flex h-10 shrink-0 items-center justify-between border-b border-border px-2">
        <TabsList className="bg-muted/40 p-0.5">
          <TabsTrigger value="preview" className="data-[state=active]:bg-background">
            <Globe className="h-4 w-4 mr-1.5 text-sky-400" />
            <span>Canvas</span>
            {previewFiles && <span className="ml-1.5 h-1.5 w-1.5 rounded-full bg-emerald-400 animate-pulse" title="Live Preview Active" />}
          </TabsTrigger>
          <TabsTrigger value="editor" className="data-[state=active]:bg-background">
            <Code2 className="h-4 w-4 mr-1.5" />
            <span>Editor</span>
            {activeFile && <span className="ml-1 text-[11px] text-muted-foreground font-mono">({activeFile.name})</span>}
          </TabsTrigger>
          <TabsTrigger value="changes" className="data-[state=active]:bg-background">
            <GitPullRequest className="h-4 w-4 mr-1.5" />
            <span>Changes</span>
            {state.pendingPatchCount > 0 && (
              <span className="ml-1 rounded-full bg-sky-500/20 px-1.5 py-0.2 text-[10px] text-sky-400 font-mono font-semibold">
                {state.pendingPatchCount}
              </span>
            )}
          </TabsTrigger>
          <TabsTrigger value="checkpoints" className="data-[state=active]:bg-background">
            <History className="h-4 w-4 mr-1.5" />
            <span>Snapshots</span>
          </TabsTrigger>
        </TabsList>
        {state.centerTab === "editor" && <Button size="sm" variant="ghost" onClick={() => void saveFile()} disabled={!isDirty || !activeFile}>{isDirty && <span className="h-2 w-2 rounded-full bg-warning" aria-label="Unsaved changes" />}<Save className="h-4 w-4" /> Save</Button>}
      </div>
      <div className="min-h-0 flex-1">
        <TabsContent value="editor" className="m-0 h-full">
          {entry?.invalidated && isDirty && <div className="border-b border-warning/40 bg-warning/10 px-3 py-2 text-xs text-warning">This file changed on disk. Save your version or reopen the file to review the newer copy.</div>}
          {loadingPath === activeFile?.path ? <div className="flex h-full items-center justify-center gap-2 text-sm text-muted-foreground"><Loader2 className="h-4 w-4 animate-spin" /> Opening {activeFile?.name}</div> : activeFile ? <Suspense fallback={panelFallback}><CodeMirrorEditor key={`${activeWorkspaceId}:${activeFile.path}`} language={activeLanguage} code={code} onChange={(value) => activeWorkspaceId && setEditorState(items => editFile(items, activeWorkspaceId, activeFile.path, value))} /></Suspense> : <div className="flex h-full items-center justify-center px-6 text-center text-sm text-muted-foreground">Choose a file from Files.</div>}
        </TabsContent>
        <TabsContent value="changes" className="m-0 h-full">
          {state.centerTab === "changes" && <Suspense fallback={panelFallback}><DiffReviewPanel workspaceId={activeWorkspaceId} onResolved={() => { notifyPatchesChanged(); refreshWorkspace(); }} onOpenFile={(path) => { const name = path.split("/").pop() || path; void loadFile({ path, name, type: "file" }); }} /></Suspense>}
        </TabsContent>
        <TabsContent value="preview" className="m-0 h-full">{state.centerTab === "preview" && <Suspense fallback={panelFallback}><WebPreview files={previewFiles || undefined} visible onClose={() => dispatch({ type: "setCenterTab", tab: "editor" })} /></Suspense>}</TabsContent>
        <TabsContent value="checkpoints" className="m-0 h-full">
          {state.centerTab === "checkpoints" && <Suspense fallback={panelFallback}><CheckpointsPanel workspaceId={activeWorkspaceId} /></Suspense>}
        </TabsContent>
      </div>
    </Tabs>
  );

  return (
    <div className="flex h-full min-w-0 flex-col bg-background">
      <div className="flex h-11 shrink-0 items-center justify-between border-b border-border px-3">
        <WorkspaceHeader workspaceId={activeWorkspaceId} projectName={projectName} onRefresh={() => refreshTree(activeWorkspaceId)} />
        <div className="flex items-center gap-2">
          <Button
            variant={state.proDrawerOpen ? "secondary" : "ghost"}
            size="sm"
            onClick={() => dispatch({ type: "setProDrawer", open: !state.proDrawerOpen })}
            title="Toggle Terminal Drawer (Ctrl + `)"
          >
            <Terminal className="h-4 w-4 mr-1" />
            Terminal
            <kbd className="hidden sm:inline-block ml-1 px-1 py-0.2 text-[10px] font-mono bg-muted/60 rounded border border-border/80">Ctrl+`</kbd>
          </Button>
        </div>
      </div>
      <div className="min-h-0 flex-1">
        {isDesktop ? (
          <Allotment defaultSizes={[232, 768]}>
            <Allotment.Pane preferredSize={232} minSize={190} maxSize={380}>{explorer}</Allotment.Pane>
            <Allotment.Pane minSize={320}>{mainPanel}</Allotment.Pane>
          </Allotment>
        ) : state.mobileDestination === "files" ? explorer : mainPanel}
      </div>
      <ProDrawer
        open={state.proDrawerOpen}
        onClose={() => dispatch({ type: "setProDrawer", open: false })}
        workspaceId={activeWorkspaceId}
      />
    </div>
  );
}
