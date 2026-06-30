import { useState } from "react";
import { ChevronDown, ChevronRight, File as FileIcon, Folder, FolderOpen } from "lucide-react";
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
}

const FileTreeNode = ({
  node,
  depth = 0,
  onSelect,
  activePath,
}: {
  node: FileNode;
  depth?: number;
  onSelect: (file: FileNode) => void;
  activePath?: string;
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
        className={`flex h-7 w-full items-center gap-1.5 px-2 text-left text-sm transition-colors hover:bg-muted hover:text-foreground ${
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
        <span className="truncate">{node.name}</span>
      </button>

      {isFolder && isOpen && node.children && (
        <div className="flex flex-col">
          {node.children.map((child) => (
            <FileTreeNode key={child.path} node={child} depth={depth + 1} onSelect={onSelect} activePath={activePath} />
          ))}
        </div>
      )}
    </div>
  );
};

export default function FileExplorer({ files, onFileSelect, activePath, projectName = "Workspace" }: FileExplorerProps) {
  return (
    <div className="flex h-full flex-col bg-sidebar/80">
      <div className="border-b border-border px-3 py-2">
        <h3 className="truncate text-xs font-semibold text-foreground">{projectName}</h3>
        <p className="mt-0.5 text-[11px] uppercase tracking-[0.12em] text-muted-foreground">Files</p>
      </div>
      <ScrollArea className="flex-1">
        <div className="py-2">
          {files.map((node) => (
            <FileTreeNode key={node.path} node={node} onSelect={onFileSelect} activePath={activePath} />
          ))}
        </div>
      </ScrollArea>
    </div>
  );
}
