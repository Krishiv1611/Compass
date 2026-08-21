import { useMemo, useRef, useState } from "react";
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

type VisibleTreeNode = { node: FileNode; depth: number; parentPath?: string };

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

function flattenTree(nodes: FileNode[], expandedPaths: Set<string>, filtering: boolean, depth = 0, parentPath?: string): VisibleTreeNode[] {
  return nodes.flatMap((node) => {
    const row = { node, depth, parentPath };
    const children = node.type === "folder" && node.children && (filtering || expandedPaths.has(node.path))
      ? flattenTree(node.children, expandedPaths, filtering, depth + 1, node.path)
      : [];
    return [row, ...children];
  });
}

export default function FileExplorer(props: FileExplorerProps) {
  const { files, onFileSelect, activePath, projectName = "Workspace" } = props;
  const { state } = useWorkbench();
  const [query, setQuery] = useState("");
  const [expandedPaths, setExpandedPaths] = useState(() => new Set(files.filter((file) => file.type === "folder").map((file) => file.path)));
  const [focusedPath, setFocusedPath] = useState<string | null>(null);
  const treeItemRefs = useRef(new Map<string, HTMLButtonElement>());
  const visibleFiles = useMemo(() => filterTree(files, query), [files, query]);
  const filtering = Boolean(query.trim());
  const visibleRows = useMemo(() => flattenTree(visibleFiles, expandedPaths, filtering), [visibleFiles, expandedPaths, filtering]);

  const focusPath = (path: string) => {
    setFocusedPath(path);
    treeItemRefs.current.get(path)?.focus();
  };

  const toggleFolder = (path: string) => {
    setExpandedPaths((current) => {
      const next = new Set(current);
      if (next.has(path)) next.delete(path);
      else next.add(path);
      return next;
    });
  };

  const handleTreeKeyDown = (event: React.KeyboardEvent<HTMLButtonElement>, row: VisibleTreeNode) => {
    const index = visibleRows.findIndex((item) => item.node.path === row.node.path);
    const next = (offset: number) => visibleRows[(index + offset + visibleRows.length) % visibleRows.length];
    const expanded = expandedPaths.has(row.node.path) || filtering;

    if (event.key === "ArrowDown") { event.preventDefault(); focusPath(next(1).node.path); }
    else if (event.key === "ArrowUp") { event.preventDefault(); focusPath(next(-1).node.path); }
    else if (event.key === "Home") { event.preventDefault(); focusPath(visibleRows[0].node.path); }
    else if (event.key === "End") { event.preventDefault(); focusPath(visibleRows[visibleRows.length - 1].node.path); }
    else if (event.key === "ArrowRight" && row.node.type === "folder") {
      event.preventDefault();
      if (!expanded) toggleFolder(row.node.path);
      else {
        const firstChild = visibleRows[index + 1];
        if (firstChild?.depth === row.depth + 1) focusPath(firstChild.node.path);
      }
    }
    else if (event.key === "ArrowLeft") {
      if (row.node.type === "folder" && expanded && !filtering) { event.preventDefault(); toggleFolder(row.node.path); }
      else if (row.parentPath) { event.preventDefault(); focusPath(row.parentPath); }
    } else if (event.key === "Enter" || event.key === " ") {
      event.preventDefault();
      if (row.node.type === "folder") toggleFolder(row.node.path);
      else onFileSelect(row.node);
    }
  };

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
        {visibleRows.length ? <div className="py-2" role="tree" aria-label={`${projectName} files`}>{visibleRows.map((row, index) => {
          const { node, depth } = row;
          const isFolder = node.type === "folder";
          const expanded = filtering || expandedPaths.has(node.path);
          const isActive = node.path === activePath;
          const isContext = state.selectedContextFiles.includes(node.path);
          return <div key={node.path} className="group relative" role="none">
            <button
              ref={(element) => { if (element) treeItemRefs.current.set(node.path, element); else treeItemRefs.current.delete(node.path); }}
              type="button"
              role="treeitem"
              tabIndex={focusedPath === null ? (index === 0 ? 0 : -1) : (focusedPath === node.path ? 0 : -1)}
              aria-level={depth + 1}
              aria-expanded={isFolder ? expanded : undefined}
              aria-selected={isActive}
              className={`flex min-h-10 w-full items-center gap-1.5 pr-24 text-left text-sm transition-colors hover:bg-muted hover:text-foreground focus-visible:ring-2 focus-visible:ring-ring ${isActive ? "bg-primary/10 text-foreground" : "text-muted-foreground"}`}
              style={{ paddingLeft: `${depth * 12 + 8}px` }}
              onFocus={() => setFocusedPath(node.path)}
              onClick={() => isFolder ? toggleFolder(node.path) : onFileSelect(node)}
              onKeyDown={(event) => handleTreeKeyDown(event, row)}
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
            {(props.onCreate || props.onRename || props.onDelete) && <div className="absolute right-1 top-1/2 hidden -translate-y-1/2 items-center gap-0.5 rounded bg-sidebar/95 p-0.5 shadow-sm group-hover:flex group-focus-within:flex">
              {isFolder && props.onCreate && <><Button type="button" variant="ghost" size="icon-xs" onClick={() => props.onCreate!(node.path, "file")} aria-label={`New file in ${node.path}`} title="New file"><FilePlus className="h-3.5 w-3.5 text-info" /></Button><Button type="button" variant="ghost" size="icon-xs" onClick={() => props.onCreate!(node.path, "folder")} aria-label={`New folder in ${node.path}`} title="New folder"><FolderPlus className="h-3.5 w-3.5 text-info" /></Button></>}
              {props.onRename && <Button type="button" variant="ghost" size="icon-xs" onClick={() => props.onRename!(node.path)} aria-label={`Rename ${node.path}`} title="Rename"><Edit2 className="h-3.5 w-3.5 text-info" /></Button>}
              {props.onDelete && <Button type="button" variant="ghost" size="icon-xs" onClick={() => props.onDelete!(node.path)} aria-label={`Delete ${node.path}`} title="Delete"><Trash2 className="h-3.5 w-3.5 text-destructive" /></Button>}
            </div>}
          </div>;
        })}</div> : <div className="px-4 py-8 text-center text-sm text-muted-foreground">{query.trim() ? `No files match “${query}”.` : <><p>This project has no files yet.</p>{props.onCreate && <Button className="mt-3" size="sm" onClick={() => props.onCreate!("", "file")}>Create first file</Button>}</>}</div>}
      </ScrollArea>
    </div>
  );
}
