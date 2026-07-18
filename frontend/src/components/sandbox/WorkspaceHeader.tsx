import { useEffect, useState } from "react";
import {
  FolderDown,
  HardDrive,
  FileText,
  Loader2,
  RefreshCcw,
  Info,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { workspaceApi } from "@/api";

interface WorkspaceHeaderProps {
  workspaceId: string;
  projectName: string;
  onRefresh?: () => void;
}

function formatBytes(bytes: number): string {
  if (bytes === 0) return "0 B";
  const k = 1024;
  const sizes = ["B", "KB", "MB", "GB"];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return `${parseFloat((bytes / Math.pow(k, i)).toFixed(1))} ${sizes[i]}`;
}

export default function WorkspaceHeader({
  workspaceId,
  projectName,
  onRefresh,
}: WorkspaceHeaderProps) {
  const [meta, setMeta] = useState<{
    file_count: number;
    size_bytes: number;
    status: string;
  } | null>(null);
  const [uploading, setUploading] = useState(false);

  const fetchMeta = async () => {
    try {
      const workspaces = await workspaceApi.listWorkspaces();
      const ws = workspaces.find((w: any) => w.id === workspaceId);
      if (ws) setMeta(ws);
    } catch {
      // ignore
    }
  };

  useEffect(() => {
    fetchMeta();
    // Poll when uploading
    let interval: ReturnType<typeof setInterval> | null = null;
    if (uploading) {
      interval = setInterval(fetchMeta, 2000);
    }
    return () => {
      if (interval) clearInterval(interval);
    };
  }, [workspaceId, uploading]);

  useEffect(() => {
    if (meta?.status === "uploading") {
      setUploading(true);
    } else {
      setUploading(false);
    }
  }, [meta?.status]);

  const statusColor =
    meta?.status === "ready"
      ? "text-green-500 border-green-500/30 bg-green-500/10"
      : meta?.status === "uploading"
      ? "text-amber-500 border-amber-500/30 bg-amber-500/10"
      : "text-muted-foreground";

  return (
    <div className="flex items-center justify-between border-b border-border bg-muted/30 px-3 py-2">
      <div className="flex items-center gap-2 min-w-0">
        <HardDrive className="h-3.5 w-3.5 shrink-0 text-primary" />
        <span className="truncate text-xs font-medium text-foreground">
          {projectName}
        </span>
        {meta && (
          <>
            <Badge
              variant="outline"
              className={`h-5 rounded-sm px-1.5 text-[10px] ${statusColor}`}
            >
              {meta.status === "uploading" && (
                <Loader2 className="h-2.5 w-2.5 animate-spin mr-0.5" />
              )}
              {meta.status}
            </Badge>
            <span className="hidden text-[10px] text-muted-foreground sm:flex items-center gap-1">
              <FileText className="h-3 w-3" />
              {meta.file_count} files
              <Info className="h-3 w-3 ml-1" />
              {formatBytes(meta.size_bytes)}
            </span>
          </>
        )}
      </div>

      <div className="flex items-center gap-1 shrink-0">
        {onRefresh && (
          <Button
            variant="ghost"
            size="icon-sm"
            onClick={onRefresh}
            title="Refresh file tree"
            aria-label="Refresh file tree"
            className="focus-visible:ring-2 focus-visible:ring-primary/40"
          >
            <RefreshCcw className="h-3.5 w-3.5" />
          </Button>
        )}
        <Button
          variant="ghost"
          size="icon-sm"
          onClick={() => window.open(workspaceApi.getDownloadUrl(workspaceId))}
          title="Download workspace as ZIP"
          aria-label="Download workspace as ZIP"
          className="focus-visible:ring-2 focus-visible:ring-primary/40"
        >
          <FolderDown className="h-3.5 w-3.5" />
        </Button>
      </div>
    </div>
  );
}
