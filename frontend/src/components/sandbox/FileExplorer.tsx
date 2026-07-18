import { useState } from "react";
import { ChevronDown, ChevronRight, File as FileIcon, Folder, FolderOpen, FilePlus, FolderPlus, Edit2, Trash2 } from "lucide-react";
import { ScrollArea } from "@/components/ui/scroll-area";

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

const FileTreeNode = ({
  node,
  depth = 0,
  onSelect,
  activePath,
  onCreate,
  onRename,
  onDelete,
}: {
  node: FileNode;
  depth?: number;
  onSelect: (file: FileNode) => void;
  activePath?: string;
  onCreate?: (parentPath: string, type: "file" | "folder") => void;
  onRename?: (path: string) => void;
  onDelete?: (path: string) => void;
}) => {
  const [isOpen, setIsOpen] = useState(depth < 1);
  const isFolder = node.type === "folder";
  const isActive = node.path === activePath;

  const handleClick = () => {
    if (isFolder) {
      setIsOpen((open) => !open);
    } else {
      onSelect(node);
    }
  };

  return (
    <div>
      <button
        className={`group flex min-h-10 w-full items-center gap-1.5 px-2 text-left text-sm transition-colors hover:bg-muted hover:text-foreground ${
          isActive ? "bg-primary/10 text-foreground" : "text-muted-foreground"
        }`}
        style={{ paddingLeft: `${depth * 12 + 8}px` }}
        onClick={handleClick}
        title={node.path}
      >
        {isFolder ? (
          isOpen ? <ChevronDown className="h-3.5 w-3.5 shrink-0 opacity-70" /> : <ChevronRight className="h-3.5 w-3.5 shrink-0 opacity-70" />
        ) : (
          <span className="h-3.5 w-3.5 shrink-0" />
        )}
        {isFolder ? (
          isOpen ? <FolderOpen className="h-4 w-4 shrink-0 text-sky-400" /> : <Folder className="h-4 w-4 shrink-0 text-sky-400" />
        ) : (
          <FileIcon className="h-4 w-4 shrink-0 opacity-80" />
        )}
        <span className="truncate flex-1">{node.name}</span>
        <div className="hidden items-center gap-1 opacity-60 group-hover:flex hover:opacity-100">
          {isFolder && onCreate && (
            <>
              <FilePlus className="h-3.5 w-3.5 hover:text-sky-400" onClick={(e) => { e.stopPropagation(); onCreate(node.path, "file"); }} />
              <FolderPlus className="h-3.5 w-3.5 hover:text-sky-400" onClick={(e) => { e.stopPropagation(); onCreate(node.path, "folder"); }} />
            </>
          )}
          {onRename && <Edit2 className="h-3.5 w-3.5 hover:text-sky-400" onClick={(e) => { e.stopPropagation(); onRename(node.path); }} />}
          {onDelete && <Trash2 className="h-3.5 w-3.5 hover:text-destructive" onClick={(e) => { e.stopPropagation(); onDelete(node.path); }} />}
        </div>
      </button>

      {isFolder && isOpen && node.children && (
        <div className="flex flex-col">
          {node.children.map((child) => (
            <FileTreeNode key={child.path} node={child} depth={depth + 1} onSelect={onSelect} activePath={activePath} onCreate={onCreate} onRename={onRename} onDelete={onDelete} />
          ))}
        </div>
      )}
    </div>
  );
};

export default function FileExplorer(props: FileExplorerProps) {
  const { files, onFileSelect, activePath, projectName = "Workspace" } = props;
  return (
    <div className="flex h-full flex-col bg-sidebar/80">
      <div className="flex items-center justify-between border-b border-border px-3 py-2">
        <div>
          <h3 className="truncate text-xs font-semibold text-foreground">{projectName}</h3>
          <p className="mt-0.5 text-[11px] uppercase tracking-[0.12em] text-muted-foreground">Files</p>
        </div>
        <div className="flex items-center gap-1 text-muted-foreground">
          {props.onCreate && (
            <>
              <button title="New File" onClick={() => props.onCreate!("", "file")}>
                <FilePlus className="h-4 w-4 hover:text-sky-400" />
              </button>
              <button title="New Folder" onClick={() => props.onCreate!("", "folder")}>
                <FolderPlus className="h-4 w-4 hover:text-sky-400" />
              </button>
            </>
          )}
        </div>
      </div>
      <ScrollArea className="flex-1">
        <div className="py-2">
          {files.map((node) => (
            <FileTreeNode key={node.path} node={node} onSelect={onFileSelect} activePath={activePath} onCreate={props.onCreate} onRename={props.onRename} onDelete={props.onDelete} />
          ))}
        </div>
      </ScrollArea>
    </div>
  );
}

