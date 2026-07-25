import { Bot, CircleDot, GitBranch, GitCommitHorizontal, Radio, WifiOff } from "lucide-react";
import { useWorkbench } from "@/contexts/WorkbenchContext";

interface WorkbenchStatusBarProps {
  model: string;
  revision?: string | null;
  branch?: string | null;
  pendingChanges: number;
  tokens: number;
  connection: "ready" | "streaming" | "offline";
}

const shortModel = (model: string) => model.split("/").pop() || model;

export default function WorkbenchStatusBar({
  model,
  revision,
  branch,
  pendingChanges,
  tokens,
  connection,
}: WorkbenchStatusBarProps) {
  const { reviewPatches } = useWorkbench();
  return (
    <div className="hidden h-6 shrink-0 items-center justify-between border-t border-border bg-sidebar px-3 font-mono text-xs text-muted-foreground lg:flex">
      <div className="flex min-w-0 items-center gap-4">
        <span className="flex min-w-0 items-center gap-1.5" title={model}>
          <Bot className="h-3 w-3" />
          <span className="max-w-44 truncate">{shortModel(model)}</span>
        </span>
        <span className="flex items-center gap-1.5">
          <GitBranch className="h-3 w-3" />
          {branch || "local"}
        </span>
        <span className="flex items-center gap-1.5" title={revision || "No indexed revision"}>
          <GitCommitHorizontal className="h-3 w-3" />
          {revision?.slice(0, 8) || "unindexed"}
        </span>
      </div>
      <div className="flex items-center gap-4">
        <button
          type="button"
          onClick={() => reviewPatches()}
          className="flex items-center gap-1.5 hover:text-foreground"
          title="Review project changes"
        >
          <CircleDot className={`h-3 w-3 ${pendingChanges ? "text-warning" : ""}`} />
          {pendingChanges} change{pendingChanges === 1 ? "" : "s"}
        </button>
        <span>{tokens.toLocaleString()} tokens</span>
        <span className={`flex items-center gap-1.5 ${connection === "streaming" ? "text-success" : connection === "offline" ? "text-destructive" : ""}`}>
          {connection === "offline" ? <WifiOff className="h-3 w-3" /> : <Radio className={`h-3 w-3 ${connection === "streaming" ? "animate-pulse" : ""}`} />}
          {connection}
        </span>
      </div>
    </div>
  );
}
