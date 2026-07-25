import { useState } from "react";
import { CheckCircle2, ChevronDown, ChevronRight, FileCode2, Loader2, Search, Terminal, Wrench, XCircle } from "lucide-react";
import { cn } from "@/lib/utils";

interface ToolCallCardProps {
  toolName: string;
  args: unknown;
  result?: unknown;
  status: "pending" | "running" | "completed" | "error";
  error?: string;
}

const safeText = (value: unknown) => {
  if (typeof value === "string") return value;
  try { return JSON.stringify(value, null, 2); } catch { return "Unavailable"; }
};

export default function ToolCallCard({ toolName, args, result, status, error }: ToolCallCardProps) {
  const [isOpen, setIsOpen] = useState(false);
  const Icon = toolName.includes("file") || toolName.includes("code") ? FileCode2 : toolName.includes("search") || toolName.includes("grep") ? Search : toolName.includes("shell") || toolName.includes("cmd") ? Terminal : Wrench;
  const statusIcon = status === "running" ? <Loader2 className="h-3.5 w-3.5 animate-spin text-warning" /> : status === "completed" ? <CheckCircle2 className="h-3.5 w-3.5 text-success" /> : status === "error" ? <XCircle className="h-3.5 w-3.5 text-destructive" /> : <span className="h-3 w-3 rounded-full border border-muted-foreground" />;
  return (
    <section className={cn("my-2 overflow-hidden border-y border-border", status === "error" && "border-destructive/40")}>
      <button type="button" onClick={() => setIsOpen((value) => !value)} className="flex w-full items-center justify-between px-2 py-2 text-left text-xs hover:bg-muted/50" aria-expanded={isOpen}>
        <span className="flex min-w-0 items-center gap-2"><Icon className="h-4 w-4 shrink-0 text-primary" /><span className="truncate font-mono">{toolName}</span></span>
        <span className="flex items-center gap-2">{statusIcon}{isOpen ? <ChevronDown className="h-3.5 w-3.5" /> : <ChevronRight className="h-3.5 w-3.5" />}</span>
      </button>
      {isOpen && <div className="border-t border-border px-2 py-3 text-xs"><p className="mb-1 font-medium text-muted-foreground">Arguments</p><pre className="mb-3 max-h-40 overflow-auto border-l-2 border-border pl-2 font-mono text-xs">{safeText(args) || "{}"}</pre>{(result !== undefined || status === "completed") && <><p className="mb-1 font-medium text-muted-foreground">Result</p><pre className="max-h-40 overflow-auto border-l-2 border-border pl-2 font-mono text-xs">{safeText(result) || "Success"}</pre></>}{error && <p className="mt-3 text-xs text-destructive">{error}</p>}</div>}
    </section>
  );
}
