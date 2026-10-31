import { useState } from "react";
import {
  Check,
  CheckCircle2,
  ChevronDown,
  ChevronRight,
  Copy,
  FileCode2,
  Loader2,
  Search,
  Terminal,
  Wrench,
  XCircle,
} from "lucide-react";
import { motion, AnimatePresence } from "framer-motion";
import { cn } from "@/lib/utils";

export interface ToolCallCardProps {
  toolName: string;
  args: unknown;
  result?: unknown;
  status: "pending" | "running" | "completed" | "error";
  error?: string;
  durationMs?: number;
  className?: string;
}

function getToolMeta(toolName: string) {
  const lower = toolName.toLowerCase();
  if (
    lower.includes("shell") ||
    lower.includes("cmd") ||
    lower.includes("exec") ||
    lower.includes("terminal") ||
    lower.includes("bash") ||
    lower.includes("command")
  ) {
    return {
      type: "shell" as const,
      Icon: Terminal,
      colorClass: "text-amber-400 bg-amber-500/10 border-amber-500/20",
    };
  }
  if (
    lower.includes("file") ||
    lower.includes("code") ||
    lower.includes("write") ||
    lower.includes("read") ||
    lower.includes("edit") ||
    lower.includes("patch")
  ) {
    return {
      type: "file" as const,
      Icon: FileCode2,
      colorClass: "text-sky-400 bg-sky-500/10 border-sky-500/20",
    };
  }
  if (
    lower.includes("search") ||
    lower.includes("grep") ||
    lower.includes("find") ||
    lower.includes("lookup")
  ) {
    return {
      type: "search" as const,
      Icon: Search,
      colorClass: "text-purple-400 bg-purple-500/10 border-purple-500/20",
    };
  }
  return {
    type: "generic" as const,
    Icon: Wrench,
    colorClass: "text-slate-400 bg-slate-500/10 border-slate-500/20",
  };
}

function getPreview(
  toolName: string,
  args: unknown,
  type: "shell" | "file" | "search" | "generic",
): string | null {
  let parsed = args;
  if (typeof args === "string") {
    try {
      parsed = JSON.parse(args);
    } catch {
      // not JSON string
    }
  }

  if (parsed && typeof parsed === "object") {
    const record = parsed as Record<string, unknown>;
    if (type === "shell") {
      const cmd =
        record.command ||
        record.cmd ||
        record.command_line ||
        record.CommandLine ||
        record.script;
      if (typeof cmd === "string" && cmd.trim()) {
        const trimmed = cmd.trim();
        return trimmed.startsWith("$") ? trimmed : `$ ${trimmed}`;
      }
    }

    if (type === "file") {
      const p =
        record.path ||
        record.Path ||
        record.filepath ||
        record.filePath ||
        record.file_path ||
        record.file ||
        record.target_file;
      if (typeof p === "string" && p.trim()) {
        return p.trim();
      }
    }

    if (type === "search") {
      const q =
        record.query ||
        record.query_text ||
        record.pattern ||
        record.search_term ||
        record.regex ||
        record.term;
      if (typeof q === "string" && q.trim()) {
        return `"${q.trim()}"`;
      }
    }

    // Generic fallback for any other prominent argument
    const candidate = record.path || record.name || record.url || record.key || record.query;
    if (typeof candidate === "string" && candidate.trim()) {
      return candidate.trim();
    }
  } else if (typeof parsed === "string" && parsed.trim()) {
    if (type === "shell") {
      const trimmed = parsed.trim();
      return trimmed.startsWith("$") ? trimmed : `$ ${trimmed}`;
    }
    return parsed.trim();
  }

  return null;
}

function getExitCode(result: unknown, error?: string): number | null {
  if (result && typeof result === "object") {
    const resObj = result as Record<string, unknown>;
    if (typeof resObj.exit_code === "number") return resObj.exit_code;
    if (typeof resObj.exitCode === "number") return resObj.exitCode;
    if (typeof resObj.code === "number") return resObj.code;
  }
  const textToCheck = `${typeof result === "string" ? result : ""} ${error || ""}`;
  const match = textToCheck.match(/exit(?:_|\s+)?code[:\s]+(\d+)/i);
  if (match) {
    return parseInt(match[1], 10);
  }
  return null;
}

const safeText = (value: unknown): string => {
  if (value === undefined || value === null) return "";
  if (typeof value === "string") return value;
  try {
    return JSON.stringify(value, null, 2);
  } catch {
    return String(value);
  }
};

const getCopyableText = (result: unknown, args: unknown, error?: string): string => {
  if (result !== undefined && result !== null) {
    if (typeof result === "string") return result;
    try {
      const resObj = result as Record<string, unknown>;
      if (typeof resObj.stdout === "string" && resObj.stdout) {
        return resObj.stdout + (resObj.stderr ? `\n${resObj.stderr}` : "");
      }
      return JSON.stringify(result, null, 2);
    } catch {
      return String(result);
    }
  }
  if (error) return error;
  if (typeof args === "string") return args;
  try {
    return JSON.stringify(args, null, 2);
  } catch {
    return String(args);
  }
};

function DiffViewer({ content }: { content: string }) {
  const lines = content.split("\n");
  const isDiff = lines.some(
    (l) =>
      l.startsWith("--- ") ||
      l.startsWith("+++ ") ||
      l.startsWith("@@ ") ||
      (l.startsWith("+") && !l.startsWith("+++")) ||
      (l.startsWith("-") && !l.startsWith("---")),
  );

  if (!isDiff) {
    return (
      <pre className="max-h-60 overflow-auto whitespace-pre-wrap font-mono text-[11px] leading-relaxed text-[#c9d1d9]">
        {content}
      </pre>
    );
  }

  return (
    <div className="max-h-60 overflow-auto font-mono text-[11px] leading-relaxed">
      {lines.map((line, idx) => {
        let lineStyle = "text-[#c9d1d9]";
        if (line.startsWith("+") && !line.startsWith("+++")) {
          lineStyle = "bg-emerald-500/15 text-emerald-300 px-1 rounded-sm";
        } else if (line.startsWith("-") && !line.startsWith("---")) {
          lineStyle = "bg-rose-500/15 text-rose-300 px-1 rounded-sm";
        } else if (line.startsWith("@@")) {
          lineStyle = "text-sky-400 font-semibold";
        } else if (line.startsWith("---") || line.startsWith("+++")) {
          lineStyle = "text-muted-foreground font-semibold";
        }
        return (
          <div key={idx} className={lineStyle}>
            {line || " "}
          </div>
        );
      })}
    </div>
  );
}

export default function ToolCallCard({
  toolName,
  args,
  result,
  status,
  error,
  durationMs,
  className,
}: ToolCallCardProps) {
  const [isOpen, setIsOpen] = useState(false);
  const [copied, setCopied] = useState(false);

  const meta = getToolMeta(toolName);
  const Icon = meta.Icon;
  const preview = getPreview(toolName, args, meta.type);
  const exitCode = getExitCode(result, error);

  const handleCopy = async (e: React.MouseEvent) => {
    e.stopPropagation();
    const text = getCopyableText(result, args, error);
    try {
      if (navigator?.clipboard?.writeText) {
        await navigator.clipboard.writeText(text);
      }
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      // clipboard access error
    }
  };

  const formattedArgs = safeText(args);
  const formattedResult = safeText(result);

  return (
    <section
      className={cn(
        "my-2 overflow-hidden rounded-lg border border-border/80 bg-card/60 transition-colors shadow-sm",
        status === "error" && "border-destructive/40 bg-destructive/5",
        status === "running" && "border-amber-500/30 bg-amber-500/5",
        className,
      )}
    >
      <button
        type="button"
        onClick={() => setIsOpen((prev) => !prev)}
        className="flex w-full items-center justify-between px-3 py-2 text-left text-xs transition-colors hover:bg-muted/40 focus:outline-none"
        aria-expanded={isOpen}
      >
        <span className="flex min-w-0 items-center gap-2 mr-2">
          <span
            className={cn(
              "flex h-5 w-5 shrink-0 items-center justify-center rounded border",
              meta.colorClass,
            )}
          >
            <Icon className="h-3 w-3 shrink-0" />
          </span>
          <span className="font-mono font-medium text-foreground truncate">{toolName}</span>
          {preview && (
            <span className="font-mono text-muted-foreground truncate text-[11px] max-w-xs sm:max-w-md">
              {preview}
            </span>
          )}
        </span>

        <span className="flex items-center gap-2 shrink-0">
          {status === "running" && (
            <span className="inline-flex items-center gap-1 rounded bg-amber-500/10 px-1.5 py-0.5 font-mono text-[10px] font-medium text-amber-400 border border-amber-500/20">
              <Loader2 className="h-3 w-3 animate-spin text-amber-400" />
              <span>Running</span>
            </span>
          )}

          {status === "error" && (
            <span className="inline-flex items-center gap-1 rounded bg-rose-500/10 px-1.5 py-0.5 font-mono text-[10px] font-medium text-rose-400 border border-rose-500/20">
              <XCircle className="h-3 w-3 text-rose-400" />
              <span>{exitCode !== null ? `exit ${exitCode}` : "error"}</span>
            </span>
          )}

          {status === "completed" && (
            <span className="inline-flex items-center gap-1 rounded bg-emerald-500/10 px-1.5 py-0.5 font-mono text-[10px] font-medium text-emerald-400 border border-emerald-500/20">
              <CheckCircle2 className="h-3 w-3 text-emerald-400" />
              <span>{meta.type === "shell" ? `exit ${exitCode ?? 0}` : "completed"}</span>
            </span>
          )}

          {status === "pending" && (
            <span className="inline-flex items-center gap-1 rounded bg-muted/40 px-1.5 py-0.5 font-mono text-[10px] text-muted-foreground border border-border/40">
              Pending
            </span>
          )}

          {durationMs != null && (
            <span className="inline-flex items-center rounded bg-muted/40 border border-border/40 px-1.5 py-0.5 font-mono text-[10px] text-muted-foreground">
              {Math.round(durationMs)}ms
            </span>
          )}

          {isOpen ? (
            <ChevronDown className="h-3.5 w-3.5 text-muted-foreground" />
          ) : (
            <ChevronRight className="h-3.5 w-3.5 text-muted-foreground" />
          )}
        </span>
      </button>

      <AnimatePresence initial={false}>
        {isOpen && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: "auto", opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: 0.18, ease: "easeOut" }}
            className="overflow-hidden border-t border-border/60 bg-[#0D1117]/80"
          >
            <div className="flex items-center justify-between border-b border-border/40 px-3 py-1.5 text-[11px] text-muted-foreground">
              <span className="font-mono text-[10px] uppercase tracking-wider text-muted-foreground">
                Execution Details
              </span>
              <button
                type="button"
                onClick={handleCopy}
                className="inline-flex items-center gap-1.5 rounded border border-border/40 bg-muted/30 px-2 py-0.5 text-[11px] font-medium text-muted-foreground transition-all hover:bg-muted/70 hover:text-foreground active:scale-95"
                title="Copy output to clipboard"
              >
                {copied ? (
                  <>
                    <Check className="h-3 w-3 text-emerald-400" />
                    <span className="text-emerald-400">Copied</span>
                  </>
                ) : (
                  <>
                    <Copy className="h-3 w-3" />
                    <span>Copy Output</span>
                  </>
                )}
              </button>
            </div>

            <div className="space-y-3 p-3 text-xs">
              <div>
                <p className="mb-1 font-mono text-[11px] font-medium text-muted-foreground">
                  Arguments
                </p>
                <div className="rounded-md border border-border/50 bg-[#090D13] p-2.5">
                  <pre className="max-h-40 overflow-auto whitespace-pre-wrap font-mono text-[11px] leading-relaxed text-[#c9d1d9]">
                    {formattedArgs || "{}"}
                  </pre>
                </div>
              </div>

              {(result !== undefined || status === "completed") && (
                <div>
                  <p className="mb-1 font-mono text-[11px] font-medium text-muted-foreground">
                    Output
                  </p>
                  <div className="rounded-md border border-border/50 bg-[#090D13] p-2.5">
                    <DiffViewer content={formattedResult || "Success"} />
                  </div>
                </div>
              )}

              {error && (
                <div className="rounded-md border border-destructive/30 bg-destructive/10 p-2.5 text-[11px] text-destructive">
                  <p className="font-mono font-medium">Error Details</p>
                  <p className="mt-0.5 whitespace-pre-wrap font-mono">{error}</p>
                </div>
              )}
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </section>
  );
}
