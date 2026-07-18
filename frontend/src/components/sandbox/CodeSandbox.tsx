import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import Editor from "@monaco-editor/react";
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
  TerminalSquare,
  Save,
} from "lucide-react";
import { toast } from "react-toastify";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import FileExplorer, { type FileNode } from "./FileExplorer";
import { useTheme } from "@/components/ThemeProvider";
import { workspaceApi } from "@/api";
import Modal from "@/components/ui/modal";
import DiffReviewPanel from "./DiffReviewPanel";
import WorkspaceLanding from "./WorkspaceLanding";
import WorkspaceHeader from "./WorkspaceHeader";



interface CodeSandboxProps {
  initialCode?: string;
  language?: string;
  sessionId: string | null;
  ensureSession: (title?: string) => Promise<string>;
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


export default function CodeSandbox({ initialCode = "", language = "typescript", sessionId, ensureSession }: CodeSandboxProps) {
  const [activeWorkspaceId, setActiveWorkspaceId] = useState<string | null>(null);
  const [projectSelected, setProjectSelected] = useState(false);
  const [projectName, setProjectName] = useState("No folder open");
  const [files, setFiles] = useState<FileNode[]>([]);
  const [activeFile, setActiveFile] = useState<FileNode | null>(null);
  const [code, setCode] = useState(initialCode);
  const [originalCode, setOriginalCode] = useState(initialCode);
  const [copied, setCopied] = useState(false);
  const [output, setOutput] = useState("Open a folder to inspect real project files.");
  const [showPatches, setShowPatches] = useState(false);
  const [pendingPatchCount, setPendingPatchCount] = useState(0);

  // Dialog states
  const [createDialog, setCreateDialog] = useState<{parentPath: string, type: "file"|"folder"} | null>(null);
  const [createName, setCreateName] = useState("");
  
  const [renameDialog, setRenameDialog] = useState<string | null>(null);
  const [renameName, setRenameName] = useState("");
  
  const [deleteDialog, setDeleteDialog] = useState<string | null>(null);

  const [isLoadingFile, setIsLoadingFile] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const { theme } = useTheme();

  const monacoTheme = theme === "light" ? "vs-light" : "vs-dark";
  const activeLanguage = useMemo(
    () => languageFromName(activeFile?.name || "", language),
    [activeFile?.name, language]
  );
  const isDirty = code !== originalCode;

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
      setOutput(`Loaded ${file.path}\nLanguage: ${languageFromName(file.name, language)}\nSize: ${text.length.toLocaleString()} characters`);
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
      setOutput("Folder opened, but no readable files were found in the first scan.");
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
    setOutput(activeFile ? `Reset ${activeFile.path} to last loaded content.` : "Nothing to reset.");
  };

  const handleSave = useCallback(async () => {
    if (!activeFile || !activeWorkspaceId) return;
    if (!isDirty) return;
    
    try {
      await workspaceApi.updateFile(activeWorkspaceId, activeFile.path, code);
      setOriginalCode(code);
      toast.success("Saved");
      setOutput(`Saved ${activeFile.path}`);
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
    setOutput([
      `File: ${activeFile.path}`,
      `Language: ${activeLanguage}`,
      `Lines: ${code.split("\n").length}`,
      `Characters: ${code.length.toLocaleString()}`,
      code !== originalCode ? "State: edited in sandbox" : "State: unchanged",
    ].join("\n"));
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
    const openReview = () => setShowPatches(true);
    window.addEventListener("review-patches-request", openReview);
    return () => window.removeEventListener("review-patches-request", openReview);
  }, []);

  if (!projectSelected) {
    return (
      <div className="flex h-full flex-col overflow-hidden rounded-lg border border-border bg-panel">
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
            });
          }}
          onOpenFolder={openFolder}
        />
      </div>
    );
  }

  return (
    <div className="flex h-full overflow-hidden rounded-lg border border-border bg-panel">
      <input
        ref={fileInputRef}
        type="file"
        multiple
        className="hidden"
        onChange={handleFolderUpload}
        {...{ webkitdirectory: "" }}
      />

      <div className="hidden w-56 shrink-0 border-r border-border bg-sidebar/80 md:flex md:flex-col">
        <WorkspaceHeader
          workspaceId={activeWorkspaceId!}
          projectName={projectName}
          onRefresh={() => refreshTree(activeWorkspaceId!)}
        />
        <div className="bg-primary/10 border-b border-primary/20 px-3 py-1.5 text-[10px] text-primary/80 font-medium">
          Workspace is an isolated copy. Use <FolderDown className="inline h-3 w-3 mx-0.5" /> to download.
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
      </div>

      <div className="flex min-w-0 flex-1 flex-col">
        <div className="flex h-11 shrink-0 items-center justify-between border-b border-border bg-header px-3">
          <div className="flex min-w-0 items-center gap-2">
            <FileCode2 className="h-4 w-4 text-primary" />
            <span className="truncate text-xs font-medium text-muted-foreground">
              {showPatches ? "Patch Review" : (activeFile?.path || projectName)}
            </span>
            {isDirty && <Badge variant="secondary" className="ml-2 h-5 rounded-sm px-1.5 text-[10px]">Unsaved</Badge>}
            {isLoadingFile && <Loader2 className="h-3.5 w-3.5 animate-spin text-muted-foreground" />}
          </div>
          <div className="flex items-center gap-1">
            <Button variant={showPatches ? "default" : "outline"} size="sm" className="h-7 text-xs mr-2" onClick={() => setShowPatches(!showPatches)}>
              {showPatches ? "Close Patches" : "Review Patches"}
              {pendingPatchCount > 0 && <Badge className="ml-1 h-4 min-w-4 px-1 text-[10px]">{pendingPatchCount}</Badge>}
            </Button>
            {activeWorkspaceId && (
              <Button variant="ghost" size="icon-sm" onClick={() => window.open(workspaceApi.getDownloadUrl(activeWorkspaceId))} title="Download Project">
                <FolderDown className="h-3.5 w-3.5" />
              </Button>
            )}
            <Button variant="ghost" size="icon-sm" onClick={openFolder} title="Open folder">
              <FolderOpen className="h-3.5 w-3.5" />
            </Button>
            <Button variant="ghost" size="icon-sm" onClick={handleSave} title="Save file (Ctrl+S)" disabled={!isDirty || !activeFile}>
              <Save className="h-3.5 w-3.5" />
            </Button>
            <Button variant="ghost" size="icon-sm" onClick={handleReset} title="Reset sandbox code">
              <RotateCcw className="h-3.5 w-3.5" />
            </Button>
            <Button variant="ghost" size="icon-sm" onClick={handleCopy} title="Copy code">
              {copied ? <Check className="h-3.5 w-3.5 text-emerald-400" /> : <Copy className="h-3.5 w-3.5" />}
            </Button>
            <Button variant="secondary" size="sm" className="h-7" onClick={inspectFile} disabled={!activeFile}>
              <Info className="mr-1.5 h-3.5 w-3.5" /> Inspect
            </Button>
          </div>
        </div>

        <div className="min-h-0 flex-1">
          {showPatches && activeWorkspaceId ? (
            <DiffReviewPanel workspaceId={activeWorkspaceId} onResolved={() => refreshPatchCount(activeWorkspaceId)} />
          ) : (
            <Editor
              height="100%"
              language={activeLanguage}
              theme={monacoTheme}
              value={code}
              onChange={(value) => setCode(value || "")}
              options={{
                minimap: { enabled: false },
                fontSize: 13,
                fontFamily: "'JetBrains Mono', 'SFMono-Regular', Consolas, monospace",
                lineHeight: 21,
                padding: { top: 14 },
                scrollBeyondLastLine: false,
                smoothScrolling: true,
                renderLineHighlight: "line",
                wordWrap: "on",
                readOnly: !activeFile,
              }}
            />
          )}
        </div>

        <div className="h-32 shrink-0 border-t border-border bg-background/70">
          <div className="flex h-8 items-center border-b border-border px-3 text-[11px] font-semibold uppercase tracking-[0.12em] text-muted-foreground">
            <TerminalSquare className="mr-2 h-3.5 w-3.5" /> Sandbox Output
          </div>
          <pre className="h-[calc(100%-2rem)] overflow-auto p-3 font-mono text-xs leading-5 text-muted-foreground">{output}</pre>
        </div>
      </div>

      {/* Create Dialog */}
      <Modal
        open={!!createDialog}
        onClose={() => setCreateDialog(null)}
        ariaLabel={`Create ${createDialog?.type ?? "item"}`}
      >
        <h3 className="text-lg font-semibold mb-4">
          Create {createDialog?.type === "folder" ? "Folder" : "File"}
        </h3>
        <form onSubmit={executeCreate} className="flex flex-col gap-4">
          <input
            autoFocus
            type="text"
            value={createName}
            onChange={(e) => setCreateName(e.target.value)}
            placeholder="Name"
            className="flex h-9 w-full rounded-md border border-input bg-transparent px-3 py-1 text-sm shadow-sm transition-colors placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary/40"
          />
          <div className="flex justify-end gap-2">
            <Button type="button" variant="ghost" onClick={() => setCreateDialog(null)}>
              Cancel
            </Button>
            <Button type="submit">Create</Button>
          </div>
        </form>
      </Modal>

      {/* Rename Dialog */}
      <Modal
        open={!!renameDialog}
        onClose={() => setRenameDialog(null)}
        ariaLabel="Rename file"
      >
        <h3 className="text-lg font-semibold mb-4">Rename</h3>
        <form onSubmit={executeRename} className="flex flex-col gap-4">
          <input
            autoFocus
            type="text"
            value={renameName}
            onChange={(e) => setRenameName(e.target.value)}
            className="flex h-9 w-full rounded-md border border-input bg-transparent px-3 py-1 text-sm shadow-sm transition-colors placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary/40"
          />
          <div className="flex justify-end gap-2">
            <Button type="button" variant="ghost" onClick={() => setRenameDialog(null)}>
              Cancel
            </Button>
            <Button type="submit">Rename</Button>
          </div>
        </form>
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
    </div>
  );
}



