import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import Editor from "@monaco-editor/react";
import {
  Check,
  Code2,
  Copy,
  FileCode2,
  FolderOpen,
  Info,
  Loader2,
  RotateCcw,
  TerminalSquare,
} from "lucide-react";
import { toast } from "react-toastify";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import FileExplorer, { type FileNode } from "./FileExplorer";
import { useTheme } from "@/components/ThemeProvider";

type FileHandleLike = {
  kind: "file";
  name: string;
  getFile: () => Promise<File>;
};

type DirectoryHandleLike = {
  kind: "directory";
  name: string;
  entries: () => AsyncIterableIterator<[string, FileHandleLike | DirectoryHandleLike]>;
};

type WindowWithPicker = Window & {
  showDirectoryPicker?: () => Promise<DirectoryHandleLike>;
};

interface CodeSandboxProps {
  initialCode?: string;
  language?: string;
}

const ignoredNames = new Set(["node_modules", ".git", ".venv", "__pycache__", "dist", "build", ".next"]);

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

const sortNodes = (nodes: FileNode[]) =>
  nodes.sort((a, b) => {
    if (a.type !== b.type) return a.type === "folder" ? -1 : 1;
    return a.name.localeCompare(b.name);
  });

async function readDirectory(handle: DirectoryHandleLike, parentPath = "", depth = 0): Promise<FileNode[]> {
  if (depth > 5) return [];
  const nodes: FileNode[] = [];
  for await (const [name, entry] of handle.entries()) {
    if (ignoredNames.has(name) || name.startsWith(".")) continue;
    const path = `${parentPath}/${name}`;
    if (entry.kind === "directory") {
      nodes.push({
        name,
        type: "folder",
        path,
        children: await readDirectory(entry, path, depth + 1),
      });
    } else {
      nodes.push({ name, type: "file", path, fileHandle: entry as any });
    }
  }
  return sortNodes(nodes);
}

function filesToTree(files: FileList): FileNode[] {
  const root: FileNode[] = [];
  Array.from(files).forEach((file) => {
    const relativePath = (file as File & { webkitRelativePath?: string }).webkitRelativePath || file.name;
    const parts = relativePath.split("/").filter(Boolean);
    let cursor = root;
    parts.forEach((part, index) => {
      const path = `/${parts.slice(0, index + 1).join("/")}`;
      const isFile = index === parts.length - 1;
      let node = cursor.find((item) => item.name === part && item.path === path);
      if (!node) {
        node = isFile
          ? { name: part, type: "file", path, file }
          : { name: part, type: "folder", path, children: [] };
        cursor.push(node);
      }
      if (!isFile) cursor = node.children || [];
    });
  });

  const sortTree = (nodes: FileNode[]) => {
    sortNodes(nodes);
    nodes.forEach((node) => sortTree(node.children || []));
    return nodes;
  };

  return sortTree(root);
}

export default function CodeSandbox({ initialCode = "", language = "typescript" }: CodeSandboxProps) {
  const [projectSelected, setProjectSelected] = useState(false);
  const [projectName, setProjectName] = useState("No folder open");
  const [files, setFiles] = useState<FileNode[]>([]);
  const [activeFile, setActiveFile] = useState<FileNode | null>(null);
  const [code, setCode] = useState(initialCode);
  const [originalCode, setOriginalCode] = useState(initialCode);
  const [copied, setCopied] = useState(false);
  const [output, setOutput] = useState("Open a folder to inspect real project files.");
  const [isLoadingFile, setIsLoadingFile] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const { theme } = useTheme();

  const monacoTheme = theme === "light" ? "vs-light" : "vs-dark";
  const activeLanguage = useMemo(
    () => languageFromName(activeFile?.name || "", language),
    [activeFile?.name, language]
  );

  const loadFile = useCallback(async (file: FileNode) => {
    if (file.type !== "file") return;
    setIsLoadingFile(true);
    try {
      let text = file.content;
      if (text === undefined && file.fileHandle) {
        const handleFile = await (file.fileHandle as FileHandleLike).getFile();
        text = await handleFile.text();
      } else if (text === undefined && file.file) {
        text = await file.file.text();
      }
      const safeText = text ?? "";
      setActiveFile(file);
      setCode(safeText);
      setOriginalCode(safeText);
      setOutput(`Loaded ${file.path}\nLanguage: ${languageFromName(file.name, language)}\nSize: ${safeText.length.toLocaleString()} characters`);
    } catch (error: any) {
      toast.error(error?.message || "Could not read file");
    } finally {
      setIsLoadingFile(false);
    }
  }, [language]);

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

  const openFolder = useCallback(async () => {
    const picker = (window as WindowWithPicker).showDirectoryPicker;
    if (picker) {
      try {
        const directory = await picker();
        const nodes = await readDirectory(directory);
        applyProject(nodes, directory.name);
        toast.success(`Opened ${directory.name}`);
      } catch (error: any) {
        if (error?.name !== "AbortError") toast.error(error?.message || "Could not open folder");
      }
      return;
    }
    fileInputRef.current?.click();
  }, [applyProject]);

  useEffect(() => {
    const requestOpenFolder = () => {
      openFolder();
    };
    window.addEventListener("open-folder-request", requestOpenFolder);
    return () => window.removeEventListener("open-folder-request", requestOpenFolder);
  }, [openFolder]);

  const handleFallbackFolder = (event: React.ChangeEvent<HTMLInputElement>) => {
    if (!event.target.files?.length) return;
    const nodes = filesToTree(event.target.files);
    const first = Array.from(event.target.files)[0] as File & { webkitRelativePath?: string };
    const folderName = first.webkitRelativePath?.split("/")[0] || "Selected folder";
    applyProject(nodes, folderName);
    toast.success(`Opened ${folderName}`);
    event.target.value = "";
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

  if (!projectSelected) {
    return (
      <div className="flex h-full flex-col overflow-hidden rounded-lg border border-border bg-panel">
        <input
          ref={fileInputRef}
          type="file"
          multiple
          className="hidden"
          onChange={handleFallbackFolder}
          {...{ webkitdirectory: "" }}
        />
        <div className="flex h-11 items-center justify-between border-b border-border px-3">
          <div className="flex items-center gap-2 text-xs font-semibold uppercase tracking-[0.12em] text-muted-foreground">
            <Code2 className="h-4 w-4" /> Code Sandbox
          </div>
          <Badge variant="outline">idle</Badge>
        </div>
        <div className="flex flex-1 flex-col items-center justify-center p-8 text-center">
          <div className="mb-4 flex size-12 items-center justify-center rounded-lg border border-border bg-background text-primary">
            <FolderOpen className="h-6 w-6" />
          </div>
          <h3 className="text-base font-semibold">Open a project folder</h3>
          <p className="mt-2 max-w-sm text-sm leading-6 text-muted-foreground">
            Browse real local files and inspect code in the sandbox. No mock project is loaded.
          </p>
          <Button className="mt-5" onClick={openFolder}>
            <FolderOpen className="h-4 w-4" /> Open Folder
          </Button>
        </div>
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
        onChange={handleFallbackFolder}
        {...{ webkitdirectory: "" }}
      />

      <div className="hidden w-56 shrink-0 border-r border-border bg-sidebar/80 md:block">
        <FileExplorer files={files} onFileSelect={loadFile} activePath={activeFile?.path} projectName={projectName} />
      </div>

      <div className="flex min-w-0 flex-1 flex-col">
        <div className="flex h-11 shrink-0 items-center justify-between border-b border-border bg-header px-3">
          <div className="flex min-w-0 items-center gap-2">
            <FileCode2 className="h-4 w-4 text-primary" />
            <span className="truncate text-xs font-medium text-muted-foreground">
              {activeFile?.path || projectName}
            </span>
            {isLoadingFile && <Loader2 className="h-3.5 w-3.5 animate-spin text-muted-foreground" />}
          </div>
          <div className="flex items-center gap-1">
            <Button variant="ghost" size="icon-sm" onClick={openFolder} title="Open folder">
              <FolderOpen className="h-3.5 w-3.5" />
            </Button>
            <Button variant="ghost" size="icon-sm" onClick={handleReset} title="Reset sandbox code">
              <RotateCcw className="h-3.5 w-3.5" />
            </Button>
            <Button variant="ghost" size="icon-sm" onClick={handleCopy} title="Copy code">
              {copied ? <Check className="h-3.5 w-3.5 text-emerald-400" /> : <Copy className="h-3.5 w-3.5" />}
            </Button>
            <Button variant="secondary" size="sm" className="h-7" onClick={inspectFile} disabled={!activeFile}>
              <Info className="h-3.5 w-3.5" /> Inspect
            </Button>
          </div>
        </div>

        <div className="min-h-0 flex-1">
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
        </div>

        <div className="h-32 shrink-0 border-t border-border bg-background/70">
          <div className="flex h-8 items-center border-b border-border px-3 text-[11px] font-semibold uppercase tracking-[0.12em] text-muted-foreground">
            <TerminalSquare className="mr-2 h-3.5 w-3.5" /> Sandbox Output
          </div>
          <pre className="h-[calc(100%-2rem)] overflow-auto p-3 font-mono text-xs leading-5 text-muted-foreground">{output}</pre>
        </div>
      </div>
    </div>
  );
}
