import { Activity, Bot, GitBranch, Radio, WifiOff } from "lucide-react";
import { useRunEvents } from "@/contexts/RunContext";
import { useWorkbench } from "@/contexts/WorkbenchContext";

export default function StatusBar() {
  const { connection } = useRunEvents();
  const { state, reviewPatches } = useWorkbench();
  return (
    <footer className="flex h-6 w-full shrink-0 items-center justify-between border-t border-border bg-card px-3 text-xs text-muted-foreground">
      <div className="flex min-w-0 items-center gap-4">
        <span className="flex items-center gap-1.5">
          {connection === "offline" ? <WifiOff className="h-3 w-3 text-destructive" /> : <Radio className={`h-3 w-3 ${connection === "streaming" ? "text-success" : ""}`} />}
          {connection}
        </span>
        <button type="button" onClick={reviewPatches} className="flex items-center gap-1.5 hover:text-foreground">
          <Activity className="h-3 w-3" /> {state.pendingPatchCount} changed
        </button>
        <span className="hidden min-w-0 items-center gap-1.5 sm:flex">
          <GitBranch className="h-3 w-3" /><span className="truncate">{state.projectName}</span>
        </span>
      </div>
      <div className="flex items-center gap-4">
        <span className="hidden items-center gap-1.5 sm:flex"><Bot className="h-3 w-3" /> Default model</span>
        <span className="capitalize">{state.mode}</span>
      </div>
    </footer>
  );
}
