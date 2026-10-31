import { memo, useContext, useState } from "react";
import {
  CheckCircle2,
  Loader2,
  RefreshCcw,
  RotateCcw,
  Sparkles,
  User,
} from "lucide-react";
import { toast } from "react-toastify";
import type { TranscriptMessage } from "./MessageList";
import MarkdownMessage from "./MarkdownMessage";
import PlanChecklist from "./PlanChecklist";
import StreamingText from "./StreamingText";
import { WorkbenchContext } from "@/contexts/WorkbenchContext";
import { checkpointsApi } from "@/api/checkpoints";
import { cn } from "@/lib/utils";

export interface MessageRowProps {
  message: TranscriptMessage;
  onRetry?: (content: string) => void;
  isLast?: boolean;
  isLoading?: boolean;
}

function MessageRow({ message, onRetry, isLast, isLoading }: MessageRowProps) {
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

  if (message.role === "user") {
    return (
      <div className="group relative rounded-xl border border-border/80 bg-[#0D1117]/80 p-3.5 shadow-sm transition-all hover:border-border">
        <div className="flex items-center justify-between text-xs">
          <div className="flex items-center gap-2">
            <span className="inline-flex items-center gap-1.5 rounded-full bg-sky-500/10 border border-sky-500/20 px-2.5 py-0.5 font-mono text-[11px] font-medium text-sky-400">
              <User className="h-3 w-3" />
              <span>User Prompt</span>
            </span>
          </div>
          {onRetry && isLast && !isLoading && (
            <button
              type="button"
              className="opacity-0 group-hover:opacity-100 flex items-center gap-1 text-[11px] text-muted-foreground hover:text-foreground transition-opacity"
              title="Retry message"
              onClick={() => onRetry(message.content || "")}
            >
              <RefreshCcw className="h-3 w-3" />
              <span>Retry</span>
            </button>
          )}
        </div>
        <div className="whitespace-pre-wrap text-sm font-medium leading-relaxed text-foreground mt-2.5 selection:bg-sky-500/30">
          {content}
        </div>
      </div>
    );
  }

  return (
    <div className="rounded-xl border border-border/70 bg-card/40 p-4 shadow-sm backdrop-blur-sm space-y-3">
      <div className="flex items-center justify-between text-xs">
        <div className="flex items-center gap-2">
          <span className="inline-flex items-center gap-1.5 rounded-full bg-sky-500/10 border border-sky-500/20 px-2.5 py-0.5 font-mono text-[11px] font-medium text-sky-400">
            <span
              className={cn(
                "h-1.5 w-1.5 rounded-full",
                message.pending ? "bg-amber-400 animate-pulse" : "bg-emerald-400",
              )}
            />
            <Sparkles className="h-3 w-3 text-sky-400" />
            <span>{message.model || "Compass Brain"}</span>
          </span>
        </div>

        <div className="flex items-center gap-2">
          {message.pending ? (
            <span className="inline-flex items-center gap-1 rounded bg-amber-500/10 border border-amber-500/20 px-1.5 py-0.5 font-mono text-[10px] text-amber-400">
              <Loader2 className="h-2.5 w-2.5 animate-spin" />
              <span>Generating</span>
            </span>
          ) : (
            <span className="inline-flex items-center gap-1 rounded bg-muted/40 border border-border/40 px-1.5 py-0.5 font-mono text-[10px] text-muted-foreground">
              <CheckCircle2 className="h-2.5 w-2.5 text-emerald-400" />
              <span>Turn Ready</span>
            </span>
          )}

          {!message.pending && state?.activeWorkspaceId && (
            <button
              type="button"
              disabled={reverting}
              onClick={() => void handleRevert()}
              className="inline-flex items-center gap-1.5 rounded-md border border-border/60 bg-muted/30 px-2 py-0.5 text-[11px] text-muted-foreground transition-all hover:bg-muted hover:text-foreground hover:border-border"
              title="Revert workspace to the checkpoint before this turn"
            >
              <RotateCcw className={`h-3 w-3 ${reverting ? "animate-spin text-sky-400" : ""}`} />
              <span>{reverting ? "Restoring snapshot…" : "Revert turn"}</span>
            </button>
          )}
        </div>
      </div>

      {message.plan && (
        <div className="pt-1">
          <PlanChecklist plan={message.plan} completedSteps={message.completedPlanSteps} />
        </div>
      )}

      {content && (
        <div className="pt-0.5">
          {message.pending ? (
            <StreamingText content={content} />
          ) : (
            <div className="text-sm leading-relaxed text-foreground">
              <MarkdownMessage content={content} />
            </div>
          )}
        </div>
      )}
    </div>
  );
}

export default memo(MessageRow, (prev, next) => {
  if (prev.message !== next.message) {
    if (
      prev.message.id !== next.message.id ||
      prev.message.content !== next.message.content ||
      prev.message.pending !== next.message.pending ||
      prev.message.plan !== next.message.plan ||
      prev.message.model !== next.message.model
    ) {
      return false;
    }
  }
  if (prev.message.role === "user") {
    return (
      prev.isLast === next.isLast &&
      prev.isLoading === next.isLoading &&
      prev.onRetry === next.onRetry
    );
  }
  return true;
});
