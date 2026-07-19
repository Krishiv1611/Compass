import { useEffect, useState } from "react";
import ReactDiffViewer from "react-diff-viewer-continued";
import { CheckCircle, Download, Loader2, XCircle, RotateCcw, History } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { toast } from "react-toastify";
import { useTheme } from "@/components/ThemeProvider";
import { workspaceApi } from "@/api";

interface PatchReviewProps {
  workspaceId: string;
  onResolved?: () => void;
}

export default function DiffReviewPanel({ workspaceId, onResolved }: PatchReviewProps) {
  const [pendingPatches, setPendingPatches] = useState<any[]>([]);
  const [appliedPatches, setAppliedPatches] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [activeTab, setActiveTab] = useState("pending");
  const { theme } = useTheme();

  const fetchPatches = async () => {
    try {
      const response = await workspaceApi.getPatches(workspaceId);
      setPendingPatches(response.filter((p: any) => p.status === "pending"));
      setAppliedPatches(response.filter((p: any) => p.status === "applied").sort((a: any, b: any) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime()));
    } catch (error) {
      console.error("Failed to fetch patches", error);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchPatches();
    const refresh = () => fetchPatches();
    window.addEventListener("agent-done", refresh);
    window.addEventListener("patches-changed", refresh);
    return () => {
      window.removeEventListener("agent-done", refresh);
      window.removeEventListener("patches-changed", refresh);
    };
  }, [workspaceId]);

  const notifyResolved = () => {
    onResolved?.();
    window.dispatchEvent(new Event("patches-changed"));
  };

  const handleApply = async (patchId: string) => {
    try {
      await workspaceApi.applyPatch(workspaceId, patchId);
      toast.success("Patch applied");
      fetchPatches();
      notifyResolved();
      window.dispatchEvent(new Event("refresh-workspace-tree"));
    } catch (error: any) {
      toast.error(error?.response?.data?.detail || "Failed to apply patch");
    }
  };

  const handleReject = async (patchId: string) => {
    try {
      await workspaceApi.rejectPatch(workspaceId, patchId);
      toast.success("Patch rejected");
      fetchPatches();
      notifyResolved();
    } catch (error: any) {
      toast.error(error?.response?.data?.detail || "Failed to reject patch");
    }
  };

  const handleUndo = async (patchId: string) => {
    try {
      await workspaceApi.undoPatch(workspaceId, patchId);
      toast.success("Patch reverted successfully");
      fetchPatches();
      notifyResolved();
      window.dispatchEvent(new Event("refresh-workspace-tree"));
    } catch (error: any) {
      toast.error(error?.response?.data?.detail || "Failed to undo patch");
    }
  };

  const handleAcceptAll = async () => {
    try {
      await workspaceApi.acceptAllPatches(workspaceId);
      toast.success("All patches accepted");
      fetchPatches();
      notifyResolved();
      window.dispatchEvent(new Event("refresh-workspace-tree"));
    } catch (error: any) {
      toast.error(error?.response?.data?.detail || "Failed to accept all patches");
    }
  };

  const handleRejectAll = async () => {
    try {
      await workspaceApi.rejectAllPatches(workspaceId);
      toast.success("All patches rejected");
      fetchPatches();
      notifyResolved();
    } catch (error: any) {
      toast.error(error?.response?.data?.detail || "Failed to reject all patches");
    }
  };

  if (loading && pendingPatches.length === 0 && appliedPatches.length === 0) {
    return (
      <div className="flex h-full items-center justify-center text-muted-foreground">
        <Loader2 className="mr-2 h-5 w-5 animate-spin" /> Loading patches...
      </div>
    );
  }

  const renderPatch = (patch: any, isApplied: boolean = false) => (
    <div key={patch.id} className="flex flex-col gap-4 rounded-lg border border-border bg-card p-4">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Badge variant="outline" className={isApplied ? "border-green-500/30 text-green-500" : "border-amber-500/30 text-amber-500"}>
            {isApplied ? "Applied" : "Pending"}
          </Badge>
          <span className="font-mono text-xs text-muted-foreground">{patch.id.slice(0, 8)}</span>
        </div>
        <div className="flex items-center gap-2">
          {isApplied ? (
            <Button size="sm" variant="outline" onClick={() => handleUndo(patch.id)} className="text-red-500 hover:bg-red-500/10 hover:text-red-600">
              <RotateCcw className="mr-1 h-4 w-4" /> Undo
            </Button>
          ) : (
            <>
              <Button size="sm" variant="outline" onClick={() => handleReject(patch.id)} className="text-red-500 hover:bg-red-500/10 hover:text-red-600">
                <XCircle className="mr-1 h-4 w-4" /> Reject
              </Button>
              <Button size="sm" onClick={() => handleApply(patch.id)} className="bg-green-600 text-white hover:bg-green-700">
                <CheckCircle className="mr-1 h-4 w-4" /> Apply
              </Button>
            </>
          )}
        </div>
      </div>

      <div className="flex flex-col gap-4">
        {patch.changes.map((change: any, idx: number) => {
          const originalContent = change.before !== undefined ? change.before : "";
          const modifiedContent = change.after !== undefined ? change.after : change.content || "";
          return (
            <div key={idx} className="flex flex-col gap-2">
              <div className="flex items-center gap-2">
                <span className="font-mono text-xs font-bold uppercase text-muted-foreground">{change.type}</span>
                <span className="font-mono text-xs text-foreground">{change.path}</span>
              </div>
              <div className="overflow-hidden rounded border border-border bg-card">
                <ReactDiffViewer
                  oldValue={originalContent}
                  newValue={modifiedContent}
                  splitView={true}
                  useDarkTheme={theme === "dark"}
                  leftTitle="Original"
                  rightTitle="Modified"
                />
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );

  return (
    <div className="flex h-full flex-col overflow-hidden bg-background">
      <div className="px-4 py-2 border-b border-border bg-muted/20">
        <Tabs value={activeTab} onValueChange={setActiveTab}>
          <TabsList className="grid w-[200px] grid-cols-2">
            <TabsTrigger value="pending">Pending ({pendingPatches.length})</TabsTrigger>
            <TabsTrigger value="history">History</TabsTrigger>
          </TabsList>
        </Tabs>
      </div>

      <div className="flex-1 overflow-y-auto p-4">
        {activeTab === "pending" && (
          <>
            {pendingPatches.length === 0 ? (
              <div className="flex h-full flex-col items-center justify-center gap-3 text-center text-sm text-muted-foreground">
                <span>No pending patches.</span>
                <Button size="sm" variant="outline" onClick={() => window.open(workspaceApi.getDownloadUrl(workspaceId))}>
                  <Download className="mr-1 h-4 w-4" /> Download ZIP
                </Button>
              </div>
            ) : (
              <div className="flex flex-col gap-4">
                <div className="flex items-center justify-between mb-2">
                  <span className="text-sm font-medium text-muted-foreground">
                    Review {pendingPatches.length} patch{pendingPatches.length !== 1 ? "es" : ""}
                  </span>
                  <div className="flex gap-2">
                    <Button size="sm" variant="outline" onClick={handleRejectAll} className="text-red-500 hover:bg-red-500/10 hover:text-red-600">
                      <XCircle className="mr-1 h-4 w-4" /> Reject All
                    </Button>
                    <Button size="sm" onClick={handleAcceptAll} className="bg-green-600 text-white hover:bg-green-700">
                      <CheckCircle className="mr-1 h-4 w-4" /> Accept All
                    </Button>
                  </div>
                </div>
                {pendingPatches.map(p => renderPatch(p, false))}
              </div>
            )}
          </>
        )}

        {activeTab === "history" && (
          <>
            {appliedPatches.length === 0 ? (
              <div className="flex h-full flex-col items-center justify-center text-center text-sm text-muted-foreground">
                <History className="h-8 w-8 mb-2 opacity-50" />
                <span>No patch history.</span>
              </div>
            ) : (
              <div className="flex flex-col gap-4">
                {appliedPatches.map(p => renderPatch(p, true))}
              </div>
            )}
          </>
        )}
      </div>
    </div>
  );
}
