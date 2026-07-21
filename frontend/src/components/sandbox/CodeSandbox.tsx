import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { createPortal } from "react-dom";
import {
  Check,
  Code2,
  Copy,
  FileCode2,
  FolderDown,
  FolderOpen,
  Info,
  Loader2,
  RotateCcw,
  Save,
  PanelLeftClose,
  PanelRightClose,
  PanelLeftOpen,
  Globe,
  MessageSquare,
  Terminal as TerminalIcon,
} from "lucide-react";
import { toast } from "react-toastify";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import FileExplorer, { type FileNode } from "./FileExplorer";
import { useTheme } from "@/components/ThemeProvider";
import { workspaceApi } from "@/api";
import Modal from "@/components/ui/modal";
import DiffReviewPanel from "./DiffReviewPanel";
import WorkspaceLanding from "./WorkspaceLanding";
import WorkspaceHeader from "./WorkspaceHeader";
import CodeMirrorEditor from "./CodeMirrorEditor";
import WebPreview from "./WebPreview";
import AgentStatePanel from "./AgentStatePanel";
import { Allotment } from "allotment";
import "allotment/dist/style.css";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";

interface CodeSandboxProps {
  initialCode?: string;
  language?: string;
  sessionId: string | null;
  ensureSession: (title?: string) => Promise<string>;
  chatPanel?: React.ReactNode;
  timelinePanel?: React.ReactNode;
}

const ignoredNames = new Set([
  "node_modules", ".git", ".venv", "__pycache__", "dist", "build", ".next",
  ".turbo", ".cache", "coverage", ".nyc_output",
]);

const languageFromName = (name: string, fallback: string) => {
  const lower = name.toLowerCase();
  if (lower.endsWith(".py")) return "python";
  if (lower.endsWith(".tsx") || lower.endsWith(".ts")) return "typescript";
  if (lower.endsWith(".jsx") || lower.endsWith(".js")) return "javascript";
  if (lower.endsWith(".json")) return "json";
  if (lower.endsWith(".md")) return "markdown";
  if (lower.endsWith(".css")) return "css";
  if (lower.endsWith(".html")) return "html";
  if (lower.endsWith(".sql")) return "sql";
  return fallback;
};

const findFirstFile = (nodes: FileNode[]): FileNode | null => {
  for (const node of nodes) {
    if (node.type === "file") return node;
    const child = findFirstFile(node.children || []);
    if (child) return child;
  }
  return null;
};


export default function CodeSandbox({ initialCode = "", language = "typescript", sessionId, ensureSession, chatPanel, timelinePanel }: CodeSandboxProps) {
  const [activeWorkspaceId, setActiveWorkspaceId] = useState<string | null>(null);
  const [projectSelected, setProjectSelected] = useState(false);
  const [projectName, setProjectName] = useState("No folder open");
  const [files, setFiles] = useState<FileNode[]>([]);
  const [activeFile, setActiveFile] = useState<FileNode | null>(null);
  const [code, setCode] = useState(initialCode);
  const [originalCode, setOriginalCode] = useState(initialCode);
  const [copied, setCopied] = useState(false);
  const [showPatches, setShowPatches] = useState(false);
  const [showEditor, setShowEditor] = useState(false);
  const [showPreview, setShowPreview] = useState(false);
  const [previewFiles, setPreviewFiles] = useState<any>(null);
  const [pendingPatchCount, setPendingPatchCount] = useState(0);
  const [activeTab, setActiveTab] = useState("sandbox");
  const [showChat, setShowChat] = useState(true);
  const [headerNode, setHeaderNode] = useState<HTMLElement | null>(null);

  useEffect(() => {
    setHeaderNode(document.getElementById("header-actions"));
  }, []);

  // Dialog states
  const [createDialog, setCreateDialog] = useState<{parentPath: string, type: "file"|"folder"} | null>(null);
  const [createName, setCreateName] = useState("");
  
  const [renameDialog, setRenameDialog] = useState<string | null>(null);
  const [renameName, setRenameName] = useState("");
  
  const [deleteDialog, setDeleteDialog] = useState<string | null>(null);

  const [isLoadingFile, setIsLoadingFile] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const { theme } = useTheme();

  const activeLanguage = useMemo(
    () => languageFromName(activeFile?.name || "", language),
    [activeFile?.name, language]
  );
  const isDirty = code !== originalCode;

  const exportFiles = async () => {
    if (activeWorkspaceId) {
      try {
        const fsTree = await workspaceApi.exportWorkspaceJson(activeWorkspaceId);
        setPreviewFiles(fsTree);
      } catch (error) {
        toast.error("Failed to load preview files");
      }
    }
  };

  const handleTogglePreview = () => {
    if (!showPreview) {
      exportFiles();
      setShowPreview(true);
      setShowChat(false);
    } else {
      setShowPreview(false);
      setShowChat(true);
    }
  };

  const handleToggleChat = () => {
    if (!showChat) {
      setShowChat(true);
      setShowPreview(false);
    } else {
      setShowChat(false);
    }
  };

  const loadFile = useCallback(async (file: FileNode) => {
    if (file.type !== "file") return;
    if (!activeWorkspaceId) return;
    setIsLoadingFile(true);
    try {
      const response = await workspaceApi.getFile(activeWorkspaceId, file.path);
      const text = response.content;
      setActiveFile(file);
      setCode(text);
      setOriginalCode(text);
      setShowEditor(true);
      setShowChat(false);
    } catch (error: any) {
      toast.error(error?.response?.data?.detail || error?.message || "Could not read file");
    } finally {
      setIsLoadingFile(false);
    }
  }, [language, activeWorkspaceId]);

  const applyProject = useCallback((nodes: FileNode[], name: string) => {
    setFiles(nodes);
    setProjectName(name);
    setProjectSelected(true);
    const firstFile = findFirstFile(nodes);
    if (firstFile) {
      loadFile(firstFile);
    } else {
      setActiveFile(null);
      setCode("");
      setOriginalCode("");
    }
  }, [loadFile]);

  const refreshPatchCount = useCallback(async (wsId: string) => {
    try {
      const patches = await workspaceApi.getPatches(wsId);
      setPendingPatchCount(patches.filter((patch: any) => patch.status === "pending").length);
    } catch {
      setPendingPatchCount(0);
    }
  }, []);

  const refreshTree = useCallback(async (wsId: string) => {
    try {
      const treeRes = await workspaceApi.getTree(wsId);
      setFiles(treeRes.tree);
    } catch (error) {
      console.error(error);
    }
  }, []);

  useEffect(() => {
    let mounted = true;
    if (sessionId) {
      workspaceApi.listWorkspaces(sessionId).then(res => {
        if (mounted && res && res.length > 0) {
          const ws = res[0];
          setActiveWorkspaceId(ws.id);
          refreshPatchCount(ws.id);
          refreshTree(ws.id).then(() => {
            if (mounted) {
              setProjectName(ws.name || "Server Workspace");
              setProjectSelected(true);
            }
          });
        } else if (mounted) {
          setProjectSelected(false);
          setActiveWorkspaceId(null);
        }
      }).catch(console.error);
    } else {
      setProjectSelected(false);
      setActiveWorkspaceId(null);
    }
    return () => { mounted = false; };
  }, [refreshPatchCount, refreshTree, sessionId]);

  useEffect(() => {
    const handleWorkspaceUpdated = () => {
      if (activeWorkspaceId) {
        refreshTree(activeWorkspaceId);
        refreshPatchCount(activeWorkspaceId);
      }
    };
    window.addEventListener("workspace-updated", handleWorkspaceUpdated);
    return () => window.removeEventListener("workspace-updated", handleWorkspaceUpdated);
  }, [activeWorkspaceId, refreshTree, refreshPatchCount]);

  const executeCreate = async (e?: React.FormEvent) => {
    e?.preventDefault();
    if (!activeWorkspaceId || !createDialog || !createName.trim()) return;
    const { parentPath, type } = createDialog;
    const name = createName.trim();
    const newPath = parentPath ? `${parentPath}/${name}` : name;
    try {
      await workspaceApi.createFile(activeWorkspaceId, newPath, type);
      await refreshTree(activeWorkspaceId);
      toast.success(`Created ${type} ${name}`);
    } catch (error: any) {
      toast.error(error?.response?.data?.detail || `Could not create ${type}`);
    } finally {
      setCreateDialog(null);
      setCreateName("");
    }
  };

  const handleCreate = (parentPath: string, type: "file" | "folder") => {
    if (!activeWorkspaceId) return;
    setCreateDialog({ parentPath, type });
    setCreateName("");
  };

  const executeRename = async (e?: React.FormEvent) => {
    e?.preventDefault();
    if (!activeWorkspaceId || !renameDialog || !renameName.trim()) return;
    const oldPath = renameDialog;
    const newName = renameName.trim();
    const newPath = oldPath.substring(0, oldPath.lastIndexOf("/") + 1) + newName;
    if (oldPath === newPath) {
      setRenameDialog(null);
      return;
    }
    try {
      await workspaceApi.renameFile(activeWorkspaceId, oldPath, newPath);
      await refreshTree(activeWorkspaceId);
      toast.success("Renamed successfully");
      if (activeFile?.path === oldPath) {
        setActiveFile(null);
        setCode("");
        setOriginalCode("");
      }
    } catch (error: any) {
      toast.error(error?.response?.data?.detail || "Could not rename");
    } finally {
      setRenameDialog(null);
      setRenameName("");
    }
  };

  const handleRename = (oldPath: string) => {
    if (!activeWorkspaceId) return;
    setRenameDialog(oldPath);
    setRenameName(oldPath.split("/").pop() || "");
  };

  const executeDelete = async () => {
    if (!activeWorkspaceId || !deleteDialog) return;
    const path = deleteDialog;
    try {
      await workspaceApi.deleteFile(activeWorkspaceId, path);
      await refreshTree(activeWorkspaceId);
      toast.success("Deleted successfully");
      if (activeFile?.path === path || activeFile?.path.startsWith(path + "/")) {
        setActiveFile(null);
        setCode("");
        setOriginalCode("");
      }
    } catch (error: any) {
      toast.error(error?.response?.data?.detail || "Could not delete");
    } finally {
      setDeleteDialog(null);
    }
  };

  const handleDelete = (path: string) => {
    if (!activeWorkspaceId) return;
    setDeleteDialog(path);
  };

  const openFolder = useCallback(() => {
    fileInputRef.current?.click();
  }, []);

  useEffect(() => {
    const requestOpenFolder = () => {
      openFolder();
    };
    window.addEventListener("open-folder-request", requestOpenFolder);
    return () => window.removeEventListener("open-folder-request", requestOpenFolder);
  }, [openFolder]);

  const handleFolderUpload = async (event: React.ChangeEvent<HTMLInputElement>) => {
    const rawFiles = event.target.files;
    if (!rawFiles?.length) return;
    
    // Filter out ignored directories to prevent massive uploads (e.g. node_modules, .git)
    const filesToUpload: File[] = [];
    for (let i = 0; i < rawFiles.length; i++) {
      const file = rawFiles[i];
      const relPath = file.webkitRelativePath || file.name;
      const parts = relPath.split('/');
      // Skip only specific known-large/irrelevant directories, NOT all dotfiles
      if (!parts.some(part => ignoredNames.has(part))) {
        filesToUpload.push(file);
      }
    }

    if (!filesToUpload.length) {
      toast.error("No valid files found to upload (all were ignored).");
      event.target.value = "";
      return;
    }
    
    try {
      const activeSessionId = await ensureSession("Code Workspace");
      toast.info(`Uploading ${filesToUpload.length} files to server...`);
      
      const uploadRes = await workspaceApi.uploadFolder(activeSessionId, filesToUpload);
      setActiveWorkspaceId(uploadRes.workspace_id);
      refreshPatchCount(uploadRes.workspace_id);
      
      const first = filesToUpload[0] as File & { webkitRelativePath?: string };
      const folderName = first.webkitRelativePath?.split("/")[0] || "Server Workspace";
      
      const treeRes = await workspaceApi.getTree(uploadRes.workspace_id);
      applyProject(treeRes.tree, folderName);
      toast.success(`Opened ${folderName}`);
    } catch (error: any) {
      toast.error(error?.response?.data?.detail || error?.message || "Could not upload workspace");
    } finally {
      event.target.value = "";
    }
  };

  const handleCopy = async () => {
    await navigator.clipboard.writeText(code);
    setCopied(true);
    setTimeout(() => setCopied(false), 1600);
  };

  const handleReset = () => {
    setCode(originalCode);
    if (activeFile) toast.info(`Reset ${activeFile.path}`);
  };

  const handleSave = useCallback(async () => {
    if (!activeFile || !activeWorkspaceId) return;
    if (!isDirty) return;
    
    try {
      await workspaceApi.updateFile(activeWorkspaceId, activeFile.path, code);
      setOriginalCode(code);
      toast.success("Saved");
    } catch (error: any) {
      toast.error(error?.response?.data?.detail || error?.message || "Could not save file");
    }
  }, [activeFile, activeWorkspaceId, code, isDirty]);

  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if ((e.ctrlKey || e.metaKey) && e.key === 's') {
        e.preventDefault();
        handleSave();
      }
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [handleSave]);

  const inspectFile = () => {
    if (!activeFile) return;
    toast.info(`File: ${activeFile.path} | Language: ${activeLanguage} | Lines: ${code.split("\n").length}`);
  };

  // Auto-refresh tree when agent signals "done"
  useEffect(() => {
    const handleAgentDone = () => {
      if (activeWorkspaceId) {
        refreshTree(activeWorkspaceId);
        refreshPatchCount(activeWorkspaceId);
      }
    };
    window.addEventListener("agent-done", handleAgentDone);
    window.addEventListener("refresh-workspace-tree", handleAgentDone);
    window.addEventListener("patches-changed", handleAgentDone);
    return () => {
      window.removeEventListener("agent-done", handleAgentDone);
      window.removeEventListener("refresh-workspace-tree", handleAgentDone);
      window.removeEventListener("patches-changed", handleAgentDone);
    };
  }, [activeWorkspaceId, refreshPatchCount, refreshTree]);

  useEffect(() => {
    const openReview = () => {
      setShowPatches(true);
      setShowEditor(true);
    };
    window.addEventListener("review-patches-request", openReview);
    return () => window.removeEventListener("review-patches-request", openReview);
  }, []);

  useEffect(() => {
    const handleSetTab = (e: any) => {
      if (e.detail?.tab) setActiveTab(e.detail.tab);
    };
    window.addEventListener("set-sandbox-tab", handleSetTab);
    return () => window.removeEventListener("set-sandbox-tab", handleSetTab);
  }, []);

  if (!projectSelected) {
    return (
      <Allotment>
        <Allotment.Pane>
          <div className="flex h-full flex-col overflow-hidden bg-card border-r border-border">
            <input
              ref={fileInputRef}
              type="file"
              multiple
              className="hidden"
              onChange={handleFolderUpload}
              {...{ webkitdirectory: "" }}
            />
            <div className="flex h-11 items-center justify-between border-b border-border px-3">
              <div className="flex items-center gap-2 text-xs font-semibold uppercase tracking-[0.12em] text-muted-foreground">
                <Code2 className="h-4 w-4" /> Code Sandbox
              </div>
              <Badge variant="outline">idle</Badge>
            </div>
            <WorkspaceLanding
              sessionId={sessionId}
              ensureSession={ensureSession}
              onWorkspaceReady={(wsId, name) => {
                setActiveWorkspaceId(wsId);
                refreshTree(wsId).then(() => {
                  setProjectName(name);
                  setProjectSelected(true);
                  setShowEditor(false);
                });
              }}
              onOpenFolder={openFolder}
            />
          </div>
        </Allotment.Pane>
        {chatPanel && (
          <Allotment.Pane preferredSize={400} minSize={300}>
            {chatPanel}
          </Allotment.Pane>
        )}
      </Allotment>
    );
  }

  return (
    <>
      {headerNode && createPortal(
        <>
          <WorkspaceHeader
            workspaceId={activeWorkspaceId!}
            projectName={projectName}
            onRefresh={() => refreshTree(activeWorkspaceId!)}
          />
          <div className="h-4 w-px bg-border/50 mx-2"></div>
          <Button variant={showPreview ? "secondary" : "ghost"} size="icon-sm" className="h-7 w-7 mr-2" onClick={handleTogglePreview} title={showPreview ? "Close Preview" : "Live Preview"}>
            <Globe className="h-4 w-4" />
          </Button>
          <Button variant={showChat ? "secondary" : "ghost"} size="icon-sm" className="h-7 w-7 mr-2" onClick={handleToggleChat} title={showChat ? "Hide Chat" : "Show Chat"}>
            <MessageSquare className="h-4 w-4" />
          </Button>
        </>,
        headerNode
      )}
      <Allotment defaultSizes={[250, 750, 400]}>
        {/* File Explorer & Timeline Pane */}
        <Allotment.Pane preferredSize={250} minSize={200} maxSize={400}>
          <div className="flex h-full flex-col border-r border-border bg-sidebar/80 relative">
            <input
              ref={fileInputRef}
              type="file"
              multiple
              className="hidden"
              onChange={handleFolderUpload}
              {...{ webkitdirectory: "" }}
            />

            <Tabs value={activeTab} onValueChange={setActiveTab} className="flex h-full flex-col w-full">
              <div className="px-3 pt-3 flex items-center justify-between border-b border-border/50 pb-2">
                <TabsList className="grid grid-cols-2 w-full max-w-[260px] h-8">
                  <TabsTrigger value="sandbox" className="text-[10px]">Files</TabsTrigger>
                  <TabsTrigger value="agent" className="text-[10px]">Agent</TabsTrigger>
                </TabsList>
                
                {!showEditor && (
                  <Button variant="ghost" size="icon-sm" onClick={() => setShowEditor(true)} title="Show Editor">
                    <PanelLeftOpen className="h-4 w-4 text-muted-foreground hover:text-foreground" />
                  </Button>
                )}
              </div>
              
              <TabsContent value="sandbox" className="flex-1 min-h-0 mt-0 data-[state=inactive]:hidden p-0 flex flex-col overflow-y-auto">
                <div className="bg-muted border-b border-border px-3 py-1.5 text-[10px] text-muted-foreground font-medium">
                  Workspace is an isolated copy.
                </div>
                <FileExplorer 
                  files={files} 
                  onFileSelect={loadFile} 
                  activePath={activeFile?.path} 
                  projectName={projectName}
                  onCreate={handleCreate}
                  onRename={handleRename}
                  onDelete={handleDelete}
                />
              </TabsContent>
              
              
              
              <TabsContent value="agent" className="flex-1 min-h-0 mt-0 data-[state=inactive]:hidden p-0 border-none overflow-y-auto">
                <AgentStatePanel />
              </TabsContent>
            </Tabs>
          </div>
        </Allotment.Pane>

        {/* Editor Pane */}
        <Allotment.Pane visible={showEditor}>
          <div className="flex min-w-0 flex-1 flex-col h-full border-r border-border bg-card">
            <div className="flex h-11 shrink-0 items-center justify-between border-b border-border bg-muted/30 px-3">
              <div className="flex min-w-0 items-center gap-2">
                <Button variant="ghost" size="icon-sm" className="-ml-1 text-muted-foreground hover:text-foreground" onClick={() => setShowEditor(false)} title="Hide Editor">
                  <PanelRightClose className="h-4 w-4" />
                </Button>
                <FileCode2 className="h-4 w-4 text-primary ml-1" />
                <span className="truncate text-xs font-medium text-muted-foreground">
                  {showPatches ? "Patch Review" : (activeFile?.path || "No file selected")}
                </span>
                {isDirty && <Badge variant="secondary" className="ml-2 h-5 rounded-sm px-1.5 text-[10px]">Unsaved</Badge>}
                {isLoadingFile && <Loader2 className="h-3.5 w-3.5 animate-spin text-muted-foreground" />}
              </div>
              <div className="flex items-center gap-1">
                <Button variant={showChat ? "secondary" : "ghost"} size="icon-sm" className="h-7 w-7 mr-2" onClick={handleToggleChat} title={showChat ? "Hide Chat" : "Show Chat"}>
                  <MessageSquare className="h-3.5 w-3.5" />
                </Button>
                <Button variant={showPatches ? "default" : "outline"} size="sm" className="h-7 text-xs mr-2" onClick={() => setShowPatches(!showPatches)}>
                  {showPatches ? "Close Patches" : "Review Patches"}
                  {pendingPatchCount > 0 && <Badge className="ml-1 h-4 min-w-4 px-1 text-[10px]">{pendingPatchCount}</Badge>}
                </Button>
                <Button variant="ghost" size="icon-sm" onClick={handleSave} title="Save file (Ctrl+S)" disabled={!isDirty || !activeFile}>
                  <Save className="h-3.5 w-3.5" />
                </Button>
                <Button variant="ghost" size="icon-sm" onClick={handleCopy} title="Copy code" disabled={!activeFile && !showPatches}>
                  {copied ? <Check className="h-3.5 w-3.5 text-emerald-400" /> : <Copy className="h-3.5 w-3.5" />}
                </Button>
              </div>
            </div>

            <div className="min-h-0 flex-1">
              <Allotment vertical={true}>
                <Allotment.Pane minSize={100}>
                  {showPatches && activeWorkspaceId ? (
                    <DiffReviewPanel workspaceId={activeWorkspaceId} onResolved={() => refreshPatchCount(activeWorkspaceId)} />
                  ) : activeFile ? (
                    <CodeMirrorEditor
                      language={activeLanguage}
                      code={code}
                      onChange={(value) => setCode(value || "")}
                      readOnly={false}
                    />
                  ) : (
                    <div className="flex h-full items-center justify-center text-sm text-muted-foreground">
                      Select a file to view its code
                    </div>
                  )}
                </Allotment.Pane>
                <Allotment.Pane preferredSize={250} minSize={100} snap>
                  <div className="h-full w-full bg-[#1e1e1e] border-t border-border overflow-y-auto flex flex-col">
                    <div className="flex items-center px-3 py-1.5 bg-muted/40 border-b border-border/50 text-xs font-semibold text-muted-foreground">
                      <TerminalIcon className="h-3.5 w-3.5 mr-1.5" />
                      Terminal
                    </div>
                    <div className="flex-1 min-h-0 overflow-y-auto">
                      {timelinePanel}
                    </div>
                  </div>
                </Allotment.Pane>
              </Allotment>
            </div>
          </div>
        </Allotment.Pane>

        {/* WebContainer Preview Pane */}
        <Allotment.Pane visible={showPreview}>
          <WebPreview 
            files={previewFiles} 
            visible={showPreview} 
            onClose={() => setShowPreview(false)} 
          />
        </Allotment.Pane>

        {/* Chat Pane */}
        {chatPanel && (
          <Allotment.Pane preferredSize={400} minSize={300} visible={showChat}>
            {chatPanel}
          </Allotment.Pane>
        )}
      </Allotment>

      {/* Create Dialog */}
      <Modal
        open={!!createDialog}
        onClose={() => setCreateDialog(null)}
        ariaLabel="Create file or folder"
      >
        <h3 className="text-lg font-semibold mb-4">
          Create new {createDialog?.type}
        </h3>
        <div className="space-y-4">
          <Input
            value={createName}
            onChange={(e) => setCreateName(e.target.value)}
            placeholder={`Enter ${createDialog?.type} name`}
            onKeyDown={(e) => e.key === "Enter" && executeCreate()}
            autoFocus
          />
          <div className="flex justify-end gap-2">
            <Button variant="ghost" onClick={() => setCreateDialog(null)}>
              Cancel
            </Button>
            <Button onClick={executeCreate} disabled={!createName.trim()}>
              Create
            </Button>
          </div>
        </div>
      </Modal>

      {/* Rename Dialog */}
      <Modal
        open={!!renameDialog}
        onClose={() => setRenameDialog(null)}
        ariaLabel="Rename file or folder"
      >
        <h3 className="text-lg font-semibold mb-4">Rename</h3>
        <div className="space-y-4">
          <Input
            value={renameName}
            onChange={(e) => setRenameName(e.target.value)}
            placeholder="New name"
            onKeyDown={(e) => e.key === "Enter" && executeRename()}
            autoFocus
          />
          <div className="flex justify-end gap-2">
            <Button variant="ghost" onClick={() => setRenameDialog(null)}>
              Cancel
            </Button>
            <Button onClick={executeRename} disabled={!renameName.trim() || renameName === renameDialog?.split("/").pop()}>
              Rename
            </Button>
          </div>
        </div>
      </Modal>

      {/* Delete Dialog */}
      <Modal
        open={!!deleteDialog}
        onClose={() => setDeleteDialog(null)}
        ariaLabel="Delete file"
      >
        <h3 className="text-lg font-semibold mb-2">Delete</h3>
        <p className="text-sm text-muted-foreground mb-6">
          Are you sure you want to delete &ldquo;
          {deleteDialog?.split("/").pop()}&rdquo;? This action cannot be undone.
        </p>
        <div className="flex justify-end gap-2">
          <Button variant="ghost" onClick={() => setDeleteDialog(null)}>
            Cancel
          </Button>
          <Button variant="destructive" onClick={executeDelete}>
            Delete
          </Button>
        </div>
      </Modal>
    </>
  );
}
