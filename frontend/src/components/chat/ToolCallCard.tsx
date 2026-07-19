import { useState } from "react";
import { ChevronDown, ChevronRight, CheckCircle2, Wrench, Terminal, FileCode2, Search, Loader2, XCircle } from "lucide-react";
import { cn } from "@/lib/utils";
import { motion, AnimatePresence } from "framer-motion";

interface ToolCallCardProps {
  toolName: string;
  args: any;
  result?: any;
  status: "pending" | "running" | "completed" | "error";
  error?: string;
}

export default function ToolCallCard({ toolName, args, result, status, error }: ToolCallCardProps) {
  const [isOpen, setIsOpen] = useState(false);

  // Map tool names to nice icons
  const getIcon = () => {
    if (toolName.includes("file") || toolName.includes("code")) return <FileCode2 className="h-4 w-4" />;
    if (toolName.includes("search") || toolName.includes("grep")) return <Search className="h-4 w-4" />;
    if (toolName.includes("shell") || toolName.includes("cmd") || toolName.includes("bash")) return <Terminal className="h-4 w-4" />;
    return <Wrench className="h-4 w-4" />;
  };

  const getStatusIcon = () => {
    if (status === "running") return <Loader2 className="h-3.5 w-3.5 animate-spin text-amber-500" />;
    if (status === "completed") return <CheckCircle2 className="h-3.5 w-3.5 text-green-500" />;
    if (status === "error") return <XCircle className="h-3.5 w-3.5 text-red-500" />;
    return <div className="h-3.5 w-3.5 rounded-full border-2 border-muted-foreground/30 border-t-amber-500/50 animate-spin" />;
  };

  const formattedArgs = typeof args === 'string' ? args : JSON.stringify(args, null, 2);
  const formattedResult = typeof result === 'string' ? result : JSON.stringify(result, null, 2);

  return (
    <div className={cn(
      "my-2 flex flex-col gap-0 overflow-hidden rounded-md border",
      status === "error" ? "border-red-500/30" : "border-border/50"
    )}>
      <button
        onClick={() => setIsOpen(!isOpen)}
        className="flex w-full items-center justify-between bg-muted/10 px-3 py-2 text-xs hover:bg-muted/30 transition-colors"
      >
        <div className="flex items-center gap-2">
          <div className={cn(
            "flex h-6 w-6 items-center justify-center rounded-sm",
            status === "error" ? "bg-red-500/10 text-red-500" : "bg-primary/10 text-primary"
          )}>
            {getIcon()}
          </div>
          <span className="font-mono text-[11px] font-medium">{toolName}</span>
        </div>
        <div className="flex items-center gap-2">
          {getStatusIcon()}
          {isOpen ? <ChevronDown className="h-3.5 w-3.5 text-muted-foreground" /> : <ChevronRight className="h-3.5 w-3.5 text-muted-foreground" />}
        </div>
      </button>

      <AnimatePresence>
        {isOpen && (
          <motion.div
            initial={{ height: 0 }}
            animate={{ height: "auto" }}
            exit={{ height: 0 }}
            className="overflow-hidden bg-muted/5 border-t border-border/50"
          >
            <div className="p-3 text-xs">
              <div className="mb-1 font-semibold text-muted-foreground">Arguments</div>
              <pre className="mb-3 overflow-x-auto rounded bg-background p-2 font-mono text-[10px] text-foreground">
                {formattedArgs || "{}"}
              </pre>

              {(result || status === 'completed') && (
                <>
                  <div className="mb-1 font-semibold text-muted-foreground">Result</div>
                  <pre className="max-h-40 overflow-x-auto overflow-y-auto rounded bg-background p-2 font-mono text-[10px] text-foreground">
                    {formattedResult || "Success"}
                  </pre>
                </>
              )}

              {error && (
                <>
                  <div className="mb-1 font-semibold text-red-400">Error</div>
                  <pre className="max-h-40 overflow-x-auto overflow-y-auto rounded bg-red-950/30 p-2 font-mono text-[10px] text-red-400 border border-red-500/20">
                    {error}
                  </pre>
                </>
              )}
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
