import { memo, useContext, useState } from "react";
import { RotateCcw } from "lucide-react";
import { toast } from "react-toastify";
import type { TranscriptMessage } from "./MessageList";
import MarkdownMessage from "./MarkdownMessage";
import PlanChecklist from "./PlanChecklist";
import StreamingText from "./StreamingText";
import { WorkbenchContext } from "@/contexts/WorkbenchContext";
import { checkpointsApi } from "@/api/checkpoints";

function MessageRow({ message }: { message: TranscriptMessage }) {
  const content = message.content?.replace(/<thought>[\s\S]*?<\/thought>/g, "") ?? "";
  const workbench = useContext(WorkbenchContext);
  const state = workbench?.state;
  const refreshWorkspace = workbench?.refreshWorkspace;
  const [reverting, setReverting] = useState(false);

  const handleRevert = async () => {
    if (!state?.activeWorkspaceId) return;
    setReverting(true);
    try {
      const checkpoints = await checkpointsApi.listCheckpoints(state.activeWorkspaceId);
      if (!checkpoints || checkpoints.length === 0) {
        toast.info("No prior checkpoints available for this workspace.");
        return;
      }
      const latest = checkpoints[0];
      await checkpointsApi.restoreCheckpoint(state.activeWorkspaceId, latest.id, true);
      refreshWorkspace?.();
      toast.success(`Reverted workspace to checkpoint: ${latest.label || latest.id.slice(0, 8)}`);
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Could not restore checkpoint");
    } finally {
      setReverting(false);
    }
  };

  return (
    <div className="border-l-[3px] border-transparent py-1 pl-4">
      {message.plan && <div className="mb-4"><PlanChecklist plan={message.plan} completedSteps={message.completedPlanSteps} /></div>}
      {content && (message.pending
        ? <StreamingText content={content} />
        : <div className="text-sm leading-relaxed text-foreground"><MarkdownMessage content={content} /></div>)}
      {message.role === "assistant" && !message.pending && state?.activeWorkspaceId && (
        <div className="mt-3 flex items-center justify-between text-xs text-muted-foreground border-t border-border/40 pt-2">
          <div className="flex items-center gap-1.5">
            <span className="inline-flex items-center gap-1 rounded bg-sky-500/10 px-1.5 py-0.5 font-mono text-[10px] text-sky-400 border border-sky-500/20">
              <span className="h-1.5 w-1.5 rounded-full bg-emerald-400" />
              {message.model || "Compass Brain"}
            </span>
          </div>
          <button
            type="button"
            disabled={reverting}
            onClick={() => void handleRevert()}
            className="inline-flex items-center gap-1 rounded border border-border/60 bg-muted/30 px-2 py-0.5 text-[11px] text-muted-foreground transition-all hover:bg-muted hover:text-foreground hover:border-border"
            title="Revert project to the checkpoint before this turn"
          >
            <RotateCcw className={`h-3 w-3 ${reverting ? "animate-spin text-sky-400" : ""}`} />
            <span>{reverting ? "Restoring snapshot…" : "Revert turn"}</span>
          </button>
        </div>
      )}
    </div>
  );
}

export default memo(MessageRow);
