import { useMemo, useState } from "react";
import { ChevronDown, ChevronRight, Edit2, File as FileIcon, FilePlus, Folder, FolderOpen, FolderPlus, Link2, Search, Trash2 } from "lucide-react";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { useWorkbench } from "@/contexts/WorkbenchContext";

export type FileNode = {
  name: string;
  type: "file" | "folder";
  path: string;
  children?: FileNode[];
  content?: string;
  file?: File;
  fileHandle?: unknown;
};

interface FileExplorerProps {
  files: FileNode[];
  onFileSelect: (file: FileNode) => void;
  activePath?: string;
  projectName?: string;
  onCreate?: (parentPath: string, type: "file" | "folder") => void;
  onRename?: (path: string) => void;
  onDelete?: (path: string) => void;
}

const filterTree = (nodes: FileNode[], query: string): FileNode[] => {
  const normalized = query.trim().toLowerCase();
  if (!normalized) return nodes;
  return nodes.flatMap((node) => {
    const children = node.children ? filterTree(node.children, normalized) : [];
    return node.name.toLowerCase().includes(normalized) || node.path.toLowerCase().includes(normalized) || children.length
      ? [{ ...node, children }]
      : [];
  });
};

function FileTreeNode({ node, depth = 0, onSelect, activePath, contextPaths, filtering, onCreate, onRename, onDelete }: {
  node: FileNode;
  depth?: number;
  onSelect: (file: FileNode) => void;
  activePath?: string;
  contextPaths: string[];
  filtering: boolean;
  onCreate?: (parentPath: string, type: "file" | "folder") => void;
  onRename?: (path: string) => void;
  onDelete?: (path: string) => void;
}) {
  const [isOpen, setIsOpen] = useState(depth < 1);
  const isFolder = node.type === "folder";
  const expanded = filtering || isOpen;
  const isActive = node.path === activePath;
  const isContext = contextPaths.includes(node.path);
  const activate = () => isFolder ? setIsOpen((open) => !open) : onSelect(node);

  return (
    <div className="group relative" role="none">
      <button
        type="button"
        role="treeitem"
        aria-level={depth + 1}
        aria-expanded={isFolder ? expanded : undefined}
        aria-selected={isActive}
        className={`flex min-h-10 w-full items-center gap-1.5 pr-24 text-left text-sm transition-colors hover:bg-muted hover:text-foreground ${isActive ? "bg-primary/10 text-foreground" : "text-muted-foreground"}`}
        style={{ paddingLeft: `${depth * 12 + 8}px` }}
        onClick={activate}
        onKeyDown={(event) => {
          if (!isFolder) return;
          if (event.key === "ArrowRight" && !expanded) { event.preventDefault(); setIsOpen(true); }
          if (event.key === "ArrowLeft" && expanded) { event.preventDefault(); setIsOpen(false); }
        }}
        title={node.path}
        draggable
        onDragStart={(event) => {
          event.dataTransfer.setData("application/x-compass-path", JSON.stringify({ path: node.path, name: node.name, type: node.type }));
          event.dataTransfer.effectAllowed = "copy";
        }}
      >
        {isFolder ? (expanded ? <ChevronDown className="h-3.5 w-3.5 shrink-0 opacity-70" /> : <ChevronRight className="h-3.5 w-3.5 shrink-0 opacity-70" />) : <span className="h-3.5 w-3.5 shrink-0" />}
        {isFolder ? (expanded ? <FolderOpen className="h-4 w-4 shrink-0 text-info" /> : <Folder className="h-4 w-4 shrink-0 text-info" />) : <FileIcon className="h-4 w-4 shrink-0 opacity-80" />}
        <span className="min-w-0 flex-1 truncate">{node.name}</span>
        {isContext && <Link2 className="h-3.5 w-3.5 shrink-0 text-primary" aria-label="Included in context" />}
      </button>
      {(onCreate || onRename || onDelete) && (
        <div className="absolute right-1 top-1/2 hidden -translate-y-1/2 items-center gap-0.5 rounded bg-sidebar/95 p-0.5 shadow-sm group-hover:flex group-focus-within:flex">
          {isFolder && onCreate && <><Button type="button" variant="ghost" size="icon-xs" onClick={() => onCreate(node.path, "file")} aria-label={`New file in ${node.path}`} title="New file"><FilePlus className="h-3.5 w-3.5 text-info" /></Button><Button type="button" variant="ghost" size="icon-xs" onClick={() => onCreate(node.path, "folder")} aria-label={`New folder in ${node.path}`} title="New folder"><FolderPlus className="h-3.5 w-3.5 text-info" /></Button></>}
          {onRename && <Button type="button" variant="ghost" size="icon-xs" onClick={() => onRename(node.path)} aria-label={`Rename ${node.path}`} title="Rename"><Edit2 className="h-3.5 w-3.5 text-info" /></Button>}
          {onDelete && <Button type="button" variant="ghost" size="icon-xs" onClick={() => onDelete(node.path)} aria-label={`Delete ${node.path}`} title="Delete"><Trash2 className="h-3.5 w-3.5 text-destructive" /></Button>}
        </div>
      )}
      {isFolder && expanded && node.children && <div role="group">{node.children.map((child) => <FileTreeNode key={child.path} node={child} depth={depth + 1} onSelect={onSelect} activePath={activePath} contextPaths={contextPaths} filtering={filtering} onCreate={onCreate} onRename={onRename} onDelete={onDelete} />)}</div>}
    </div>
  );
}

export default function FileExplorer(props: FileExplorerProps) {
  const { files, onFileSelect, activePath, projectName = "Workspace" } = props;
  const { state } = useWorkbench();
  const [query, setQuery] = useState("");
  const visibleFiles = useMemo(() => filterTree(files, query), [files, query]);

  return (
    <div className="flex h-full flex-col bg-sidebar/80">
      <div className="border-b border-border p-3">
        <div className="flex items-center justify-between gap-2">
          <div className="min-w-0"><h3 className="truncate text-sm font-semibold text-foreground">{projectName}</h3><p className="text-xs text-muted-foreground">Files</p></div>
          {props.onCreate && <div className="flex items-center gap-1 text-muted-foreground"><Button type="button" variant="ghost" size="icon-sm" aria-label="New file" title="New file" onClick={() => props.onCreate!("", "file")}><FilePlus className="h-4 w-4" /></Button><Button type="button" variant="ghost" size="icon-sm" aria-label="New folder" title="New folder" onClick={() => props.onCreate!("", "folder")}><FolderPlus className="h-4 w-4" /></Button></div>}
        </div>
        <div className="relative mt-2"><Search className="pointer-events-none absolute left-2.5 top-2 h-3.5 w-3.5 text-muted-foreground" /><Input value={query} onChange={(event) => setQuery(event.target.value)} className="pl-8" placeholder="Filter files" aria-label="Filter project files" /></div>
      </div>
      <ScrollArea className="min-h-0 flex-1">
        {visibleFiles.length ? <div className="py-2" role="tree" aria-label={`${projectName} files`}>{visibleFiles.map((node) => <FileTreeNode key={node.path} node={node} onSelect={onFileSelect} activePath={activePath} contextPaths={state.selectedContextFiles} filtering={Boolean(query.trim())} onCreate={props.onCreate} onRename={props.onRename} onDelete={props.onDelete} />)}</div> : <div className="px-4 py-8 text-center text-sm text-muted-foreground">{query.trim() ? `No files match “${query}”.` : "This project has no files yet."}</div>}
      </ScrollArea>
    </div>
  );
}