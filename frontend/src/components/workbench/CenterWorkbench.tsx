import { useCallback, useEffect, useMemo, useState } from "react";
import { Code2, GitPullRequest, Globe, Loader2, Save } from "lucide-react";
import { toast } from "react-toastify";
import { Allotment } from "allotment";
import "allotment/dist/style.css";
import { workspaceApi } from "@/api";
import { useWorkbench } from "@/contexts/WorkbenchContext";
import { useWorkspaceTree } from "@/hooks/useWorkspaceTree";
import type { FileNode } from "@/components/sandbox/FileExplorer";
import FileExplorer from "@/components/sandbox/FileExplorer";
import WorkspaceHeader from "@/components/sandbox/WorkspaceHeader";
import CodeMirrorEditor from "@/components/sandbox/CodeMirrorEditor";
import DiffReviewPanel from "@/components/sandbox/DiffReviewPanel";
import WebPreview from "@/components/sandbox/WebPreview";
import { Button } from "@/components/ui/button";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";

const languageFromName = (name: string) => {
  const extension = name.toLowerCase().split(".").pop();
  return ({ py: "python", ts: "typescript", tsx: "typescript", js: "javascript", jsx: "javascript", json: "json", md: "markdown", css: "css", html: "html" } as Record<string, string>)[extension || ""] || "text";
};

export default function CenterWorkbench({ activeWorkspaceId }: { activeWorkspaceId: string | null }) {
  const { state, dispatch, openFile, openPreview, refreshWorkspace, notifyPatchesChanged } = useWorkbench();
  const { files, projectName, projectSelected, refreshTree } = useWorkspaceTree(activeWorkspaceId);
  const [codeByPath, setCodeByPath] = useState<Record<string, string>>({});
  const [savedByPath, setSavedByPath] = useState<Record<string, string>>({});
  const [loadingPath, setLoadingPath] = useState<string | null>(null);
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
  const code = activeFile ? codeByPath[activeFile.path] ?? "" : "";
  const isDirty = Boolean(activeFile && code !== (savedByPath[activeFile.path] ?? ""));

  const loadFile = useCallback(async (file: FileNode) => {
    if (file.type !== "file" || !activeWorkspaceId) return;
    openFile({ path: file.path, name: file.name, type: "file" });
    if (Object.hasOwn(codeByPath, file.path)) return;
    setLoadingPath(file.path);
    try {
      const response = await workspaceApi.getFile(activeWorkspaceId, file.path);
      setCodeByPath((items) => ({ ...items, [file.path]: response.content }));
      setSavedByPath((items) => ({ ...items, [file.path]: response.content }));
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Could not read file");
    } finally {
      setLoadingPath(null);
    }
  }, [activeWorkspaceId, codeByPath, openFile]);

  useEffect(() => {
    if (!activeFile || !activeWorkspaceId || Object.hasOwn(codeByPath, activeFile.path)) return;
    void loadFile(activeFile);
  }, [activeFile, activeWorkspaceId, codeByPath, loadFile]);

  const saveFile = async () => {
    if (!activeFile || !activeWorkspaceId || !isDirty) return;
    try {
      await workspaceApi.updateFile(activeWorkspaceId, activeFile.path, code);
      setSavedByPath((items) => ({ ...items, [activeFile.path]: code }));
      refreshWorkspace();
      toast.success("File saved");
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Could not save file");
    }
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

  const explorer = <FileExplorer files={files} onFileSelect={(file) => void loadFile(file)} activePath={activeFile?.path} projectName={projectName} />;
  const mainPanel = (
    <Tabs value={state.centerTab} onValueChange={(tab) => dispatch({ type: "setCenterTab", tab: tab as "editor" | "changes" | "preview" })} className="flex h-full flex-col">
      <div className="flex h-10 shrink-0 items-center justify-between border-b border-border px-2">
        <TabsList>
          <TabsTrigger value="editor"><Code2 className="h-4 w-4" /> Editor</TabsTrigger>
          <TabsTrigger value="changes"><GitPullRequest className="h-4 w-4" /> Changes</TabsTrigger>
          <TabsTrigger value="preview"><Globe className="h-4 w-4" /> Preview</TabsTrigger>
        </TabsList>
        {state.centerTab === "editor" && <Button size="sm" variant="ghost" onClick={() => void saveFile()} disabled={!isDirty || !activeFile}><Save className="h-4 w-4" /> Save</Button>}
      </div>
      <div className="min-h-0 flex-1">
        <TabsContent value="editor" className="m-0 h-full">
          {loadingPath === activeFile?.path ? <div className="flex h-full items-center justify-center gap-2 text-sm text-muted-foreground"><Loader2 className="h-4 w-4 animate-spin" /> Opening {activeFile?.name}</div> : activeFile ? <CodeMirrorEditor key={activeFile.path} language={activeLanguage} code={code} onChange={(value) => setCodeByPath((items) => ({ ...items, [activeFile.path]: value }))} /> : <div className="flex h-full items-center justify-center px-6 text-center text-sm text-muted-foreground">Choose a file from Files.</div>}
        </TabsContent>
        <TabsContent value="changes" className="m-0 h-full">
          <DiffReviewPanel workspaceId={activeWorkspaceId} onResolved={() => { notifyPatchesChanged(); refreshWorkspace(); }} onOpenFile={(path) => { const name = path.split("/").pop() || path; void loadFile({ path, name, type: "file" }); }} />
        </TabsContent>
        <TabsContent value="preview" className="m-0 h-full"><WebPreview files={previewFiles || undefined} visible onClose={() => dispatch({ type: "setCenterTab", tab: "editor" })} /></TabsContent>
      </div>
    </Tabs>
  );

  return (
    <div className="flex h-full min-w-0 flex-col bg-background">
      <div className="flex h-11 shrink-0 items-center justify-between border-b border-border px-3">
        <WorkspaceHeader workspaceId={activeWorkspaceId} projectName={projectName} onRefresh={() => refreshTree(activeWorkspaceId)} />
        <Button variant="ghost" size="sm" onClick={() => void preparePreview()}><Globe className="h-4 w-4" /> Preview</Button>
      </div>
      <div className="min-h-0 flex-1">
        {isDesktop ? (
          <Allotment defaultSizes={[232, 768]}>
            <Allotment.Pane preferredSize={232} minSize={190} maxSize={380}>{explorer}</Allotment.Pane>
            <Allotment.Pane minSize={320}>{mainPanel}</Allotment.Pane>
          </Allotment>
        ) : state.mobileDestination === "files" ? explorer : mainPanel}
      </div>
    </div>
  );
}