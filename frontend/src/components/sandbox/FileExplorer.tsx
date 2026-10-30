import { useEffect, useMemo, useRef, useState } from "react";
import {
  ChevronDown,
  ChevronRight,
  Edit2,
  FilePlus,
  FolderPlus,
  Link2,
  Search,
  Trash2,
} from "lucide-react";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { useWorkbench } from "@/contexts/WorkbenchContext";
import { getFileIcon } from "@/lib/fileIcons";
import { patchesApi } from "@/api";

export type FileNode = {
  name: string;
  type: "file" | "folder";
  path: string;
  children?: FileNode[];
  content?: string;
  file?: File;
  fileHandle?: unknown;
  gitStatus?: "M" | "U" | "D" | "A" | string;
};

export interface FileExplorerProps {
  files: FileNode[];
  onFileSelect: (file: FileNode) => void;
  activePath?: string;
  projectName?: string;
  gitStatus?: Record<string, string>;
  onCreate?: (parentPath: string, type: "file" | "folder") => void;
  onRename?: (path: string) => void;
  onDelete?: (path: string) => void;
  onToggleContext?: (path: string) => void;
}

type VisibleTreeNode = { node: FileNode; depth: number; parentPath?: string };

const filterTree = (nodes: FileNode[], query: string): FileNode[] => {
  const normalized = query.trim().toLowerCase();
  if (!normalized) return nodes;
  return nodes.flatMap((node) => {
    const children = node.children ? filterTree(node.children, normalized) : [];
    return node.name.toLowerCase().includes(normalized) ||
      node.path.toLowerCase().includes(normalized) ||
      children.length
      ? [{ ...node, children }]
      : [];
  });
};

function flattenTree(
  nodes: FileNode[],
  expandedPaths: Set<string>,
  filtering: boolean,
  depth = 0,
  parentPath?: string
): VisibleTreeNode[] {
  return nodes.flatMap((node) => {
    const row = { node, depth, parentPath };
    const children =
      node.type === "folder" && node.children && (filtering || expandedPaths.has(node.path))
        ? flattenTree(node.children, expandedPaths, filtering, depth + 1, node.path)
        : [];
    return [row, ...children];
  });
}

function resolveGitBadge(
  node: FileNode,
  propsGitStatus?: Record<string, string>,
  patchStatusMap?: Map<string, string>
): { badge: string; label: string; className: string } | null {
  const cleanPath = node.path.replace(/^\/+/, "");
  const rawStatus =
    node.gitStatus ||
    propsGitStatus?.[node.path] ||
    propsGitStatus?.[cleanPath] ||
    patchStatusMap?.get(cleanPath) ||
    patchStatusMap?.get(node.path);

  if (!rawStatus) return null;

  const status = rawStatus.toUpperCase();
  if (status === "M" || status === "MODIFIED" || status === "EDIT") {
    return {
      badge: "M",
      label: "Modified",
      className: "text-amber-400 group-hover:text-amber-300",
    };
  }
  if (status === "U" || status === "UNTRACKED" || status === "A" || status === "CREATE" || status === "ADDED") {
    return {
      badge: "U",
      label: "Untracked",
      className: "text-emerald-400 group-hover:text-emerald-300",
    };
  }
  if (status === "D" || status === "DELETED" || status === "DELETE") {
    return {
      badge: "D",
      label: "Deleted",
      className: "text-rose-400 group-hover:text-rose-300",
    };
  }
  return null;
}

export default function FileExplorer(props: FileExplorerProps) {
  const { files, onFileSelect, activePath, projectName = "Workspace", gitStatus: propsGitStatus } = props;
  const workbench = useWorkbench();
  const { state } = workbench;
  const [query, setQuery] = useState("");
  const [expandedPaths, setExpandedPaths] = useState(
    () => new Set(files.filter((file) => file.type === "folder").map((file) => file.path))
  );
  const [focusedPath, setFocusedPath] = useState<string | null>(null);
  const [patchStatusMap, setPatchStatusMap] = useState<Map<string, string>>(new Map());
  const treeItemRefs = useRef(new Map<string, HTMLButtonElement>());
  const visibleFiles = useMemo(() => filterTree(files, query), [files, query]);
  const filtering = Boolean(query.trim());
  const visibleRows = useMemo(
    () => flattenTree(visibleFiles, expandedPaths, filtering),
    [visibleFiles, expandedPaths, filtering]
  );

  // Sync git status from patches when activeWorkspaceId is present
  useEffect(() => {
    if (!state?.activeWorkspaceId) {
      setPatchStatusMap(new Map());
      return;
    }
    let cancelled = false;
    patchesApi
      .getPatches(state.activeWorkspaceId)
      .then((patches) => {
        if (cancelled || !Array.isArray(patches)) return;
        const map = new Map<string, string>();
        for (const patch of patches) {
          for (const change of patch.changes || []) {
            const clean = change.path.replace(/^\/+/, "");
            if (change.type === "delete") {
              map.set(clean, "D");
            } else if (change.type === "create") {
              map.set(clean, "U");
            } else {
              map.set(clean, "M");
            }
          }
        }
        setPatchStatusMap(map);
      })
      .catch(() => {
        // Workspace may not have patches initialized yet
      });
    return () => {
      cancelled = true;
    };
  }, [state?.activeWorkspaceId, state?.patchesVersion]);

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

  const toggleContext = (node: FileNode) => {
    if (props.onToggleContext) {
      props.onToggleContext(node.path);
      return;
    }
    const currentContext = state?.selectedContextFiles || [];
    const isContext = currentContext.includes(node.path);
    if (isContext) {
      if (workbench?.removeContextFile) {
        workbench.removeContextFile(node.path);
      } else {
        workbench?.dispatch?.({
          type: "setContextFiles",
          files: currentContext.filter((p) => p !== node.path),
        });
      }
    } else {
      if (workbench?.setContextFiles) {
        workbench.setContextFiles([...currentContext, node.path]);
      } else {
        workbench?.dispatch?.({
          type: "setContextFiles",
          files: [...currentContext, node.path],
        });
      }
    }
  };

  const handleTreeKeyDown = (
    event: React.KeyboardEvent<HTMLButtonElement>,
    row: VisibleTreeNode
  ) => {
    const index = visibleRows.findIndex((item) => item.node.path === row.node.path);
    const next = (offset: number) =>
      visibleRows[(index + offset + visibleRows.length) % visibleRows.length];
    const expanded = expandedPaths.has(row.node.path) || filtering;

    if (event.key === "ArrowDown") {
      event.preventDefault();
      focusPath(next(1).node.path);
    } else if (event.key === "ArrowUp") {
      event.preventDefault();
      focusPath(next(-1).node.path);
    } else if (event.key === "Home") {
      event.preventDefault();
      focusPath(visibleRows[0].node.path);
    } else if (event.key === "End") {
      event.preventDefault();
      focusPath(visibleRows[visibleRows.length - 1].node.path);
    } else if (event.key === "ArrowRight" && row.node.type === "folder") {
      event.preventDefault();
      if (!expanded) toggleFolder(row.node.path);
      else {
        const firstChild = visibleRows[index + 1];
        if (firstChild?.depth === row.depth + 1) focusPath(firstChild.node.path);
      }
    } else if (event.key === "ArrowLeft") {
      if (row.node.type === "folder" && expanded && !filtering) {
        event.preventDefault();
        toggleFolder(row.node.path);
      } else if (row.parentPath) {
        event.preventDefault();
        focusPath(row.parentPath);
      }
    } else if (event.key === "Enter" || event.key === " ") {
      event.preventDefault();
      if (row.node.type === "folder") toggleFolder(row.node.path);
      else onFileSelect(row.node);
    }
  };

  return (
    <div className="flex h-full flex-col bg-sidebar/80 select-none">
      <div className="border-b border-border/80 p-2.5">
        <div className="flex items-center justify-between gap-2">
          <div className="min-w-0">
            <h3 className="truncate text-xs font-semibold uppercase tracking-wider text-muted-foreground/80">
              {projectName}
            </h3>
            <p className="text-[11px] text-muted-foreground">Explorer</p>
          </div>
          {props.onCreate && (
            <div className="flex items-center gap-0.5 text-muted-foreground">
              <Button
                type="button"
                variant="ghost"
                size="icon-xs"
                aria-label="New file"
                title="New file"
                onClick={() => props.onCreate!("", "file")}
              >
                <FilePlus className="h-3.5 w-3.5" />
              </Button>
              <Button
                type="button"
                variant="ghost"
                size="icon-xs"
                aria-label="New folder"
                title="New folder"
                onClick={() => props.onCreate!("", "folder")}
              >
                <FolderPlus className="h-3.5 w-3.5" />
              </Button>
            </div>
          )}
        </div>
        <div className="relative mt-2">
          <Search className="pointer-events-none absolute left-2 top-2 h-3 w-3 text-muted-foreground" />
          <Input
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            className="h-7 pl-7 text-xs bg-background/50"
            placeholder="Filter files"
            aria-label="Filter project files"
          />
        </div>
      </div>
      <ScrollArea className="min-h-0 flex-1">
        {visibleRows.length ? (
          <div className="py-1 font-mono text-xs" role="tree" aria-label={`${projectName} files`}>
            {visibleRows.map((row, index) => {
              const { node, depth } = row;
              const isFolder = node.type === "folder";
              const expanded = filtering || expandedPaths.has(node.path);
              const isActive = node.path === activePath;
              const isContext = Boolean(state?.selectedContextFiles?.includes(node.path));
              const gitBadge = resolveGitBadge(node, propsGitStatus, patchStatusMap);

              return (
                <div
                  key={node.path}
                  className="group relative flex h-7 select-none items-center"
                  role="none"
                >
                  {/* Hairline vertical indent guidelines */}
                  {Array.from({ length: depth }).map((_, i) => (
                    <span
                      key={i}
                      data-testid="indent-guide"
                      aria-hidden="true"
                      className="pointer-events-none absolute bottom-0 top-0 w-px bg-border/25"
                      style={{ left: `${i * 12 + 13}px` }}
                    />
                  ))}

                  <button
                    ref={(element) => {
                      if (element) treeItemRefs.current.set(node.path, element);
                      else treeItemRefs.current.delete(node.path);
                    }}
                    type="button"
                    role="treeitem"
                    aria-label={node.name}
                    tabIndex={
                      focusedPath === null
                        ? index === 0
                          ? 0
                          : -1
                        : focusedPath === node.path
                        ? 0
                        : -1
                    }
                    aria-level={depth + 1}
                    aria-expanded={isFolder ? expanded : undefined}
                    aria-selected={isActive}
                    className={`flex h-7 w-full items-center gap-1.5 pr-20 text-left text-xs transition-colors hover:bg-muted/60 hover:text-foreground focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring ${
                      isActive
                        ? "bg-primary/15 text-foreground font-medium"
                        : "text-muted-foreground"
                    }`}
                    style={{ paddingLeft: `${depth * 12 + 8}px` }}
                    onFocus={() => setFocusedPath(node.path)}
                    onClick={() => (isFolder ? toggleFolder(node.path) : onFileSelect(node))}
                    onKeyDown={(event) => handleTreeKeyDown(event, row)}
                    title={node.path}
                    draggable
                    onDragStart={(event) => {
                      event.dataTransfer.setData(
                        "application/x-compass-path",
                        JSON.stringify({ path: node.path, name: node.name, type: node.type })
                      );
                      event.dataTransfer.effectAllowed = "copy";
                    }}
                  >
                    {isFolder ? (
                      expanded ? (
                        <ChevronDown className="h-3 w-3 shrink-0 opacity-70" />
                      ) : (
                        <ChevronRight className="h-3 w-3 shrink-0 opacity-70" />
                      )
                    ) : (
                      <span className="h-3 w-3 shrink-0" aria-hidden="true" />
                    )}

                    {getFileIcon(node.name, isFolder, expanded)}

                    <span className="min-w-0 flex-1 truncate text-xs">{node.name}</span>

                    {isContext && (
                      <Link2
                        className="h-3 w-3 shrink-0 text-primary"
                        aria-label="Included in context"
                      />
                    )}

                    {gitBadge && (
                      <span
                        data-testid={`git-status-${node.path}`}
                        title={gitBadge.label}
                        aria-label={gitBadge.label}
                        className={`ml-auto mr-1 inline-flex items-center justify-center font-mono text-[10px] font-bold ${gitBadge.className}`}
                      >
                        {gitBadge.badge}
                      </span>
                    )}
                  </button>

                  {/* Fast inline hover actions */}
                  <div className="absolute right-1 top-1/2 hidden -translate-y-1/2 items-center gap-0.5 rounded border border-border/40 bg-sidebar/95 px-0.5 py-0.5 shadow-sm group-hover:flex group-focus-within:flex z-10">
                    {!isFolder && (
                      <Button
                        type="button"
                        variant="ghost"
                        size="icon-xs"
                        onClick={(event) => {
                          event.stopPropagation();
                          toggleContext(node);
                        }}
                        aria-label={
                          isContext
                            ? `Remove ${node.name} from context`
                            : `Add ${node.name} to context`
                        }
                        title={isContext ? "Remove from AI context" : "Add to AI context"}
                      >
                        <Link2
                          className={`h-3 w-3 ${
                            isContext
                              ? "text-primary"
                              : "text-muted-foreground hover:text-foreground"
                          }`}
                        />
                      </Button>
                    )}

                    {isFolder && props.onCreate && (
                      <>
                        <Button
                          type="button"
                          variant="ghost"
                          size="icon-xs"
                          onClick={(event) => {
                            event.stopPropagation();
                            props.onCreate!(node.path, "file");
                          }}
                          aria-label={`New file in ${node.path}`}
                          title="New file"
                        >
                          <FilePlus className="h-3 w-3 text-muted-foreground hover:text-foreground" />
                        </Button>
                        <Button
                          type="button"
                          variant="ghost"
                          size="icon-xs"
                          onClick={(event) => {
                            event.stopPropagation();
                            props.onCreate!(node.path, "folder");
                          }}
                          aria-label={`New folder in ${node.path}`}
                          title="New folder"
                        >
                          <FolderPlus className="h-3 w-3 text-muted-foreground hover:text-foreground" />
                        </Button>
                      </>
                    )}

                    {props.onRename && (
                      <Button
                        type="button"
                        variant="ghost"
                        size="icon-xs"
                        onClick={(event) => {
                          event.stopPropagation();
                          props.onRename!(node.path);
                        }}
                        aria-label={`Rename ${node.path}`}
                        title="Rename"
                      >
                        <Edit2 className="h-3 w-3 text-muted-foreground hover:text-foreground" />
                      </Button>
                    )}

                    {props.onDelete && (
                      <Button
                        type="button"
                        variant="ghost"
                        size="icon-xs"
                        onClick={(event) => {
                          event.stopPropagation();
                          props.onDelete!(node.path);
                        }}
                        aria-label={`Delete ${node.path}`}
                        title="Delete"
                      >
                        <Trash2 className="h-3 w-3 text-destructive/80 hover:text-destructive" />
                      </Button>
                    )}
                  </div>
                </div>
              );
            })}
          </div>
        ) : (
          <div className="px-4 py-8 text-center text-xs text-muted-foreground">
            {query.trim() ? (
              `No files match “${query}”.`
            ) : (
              <>
                <p>This project has no files yet.</p>
                {props.onCreate && (
                  <Button
                    className="mt-3 text-xs"
                    size="sm"
                    onClick={() => props.onCreate!("", "file")}
                  >
                    Create first file
                  </Button>
                )}
              </>
            )}
          </div>
        )}
      </ScrollArea>
    </div>
  );
}
