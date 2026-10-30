import { Compass, RefreshCcw, Sparkles, TestTube2, Eye, GitPullRequest } from "lucide-react";
import { motion, AnimatePresence } from "framer-motion";
import MessageRow from "./MessageRow";
import ToolCallCard from "./ToolCallCard";
import PlanReviewCard from "./PlanReviewCard";
import ToolApprovalCard from "./ToolApprovalCard";
import ClarificationCard from "./ClarificationCard";
import type { InterruptKind, ResumePayload } from "@/types/protocol";

export type TranscriptMessage = {
  id?: string;
  role: "user" | "assistant" | "tool" | string;
  content?: string | null;
  tool_calls?: unknown;
  model?: string | null;
  created_at?: string;
  pending?: boolean;
  plan?: string;
  completedPlanSteps?: number[];
  tool_name?: string;
  tool_args?: unknown;
  status?: "pending" | "running" | "completed" | "error";
  error?: string;
};

interface MessageListProps {
  messages: TranscriptMessage[];
  isLoading: boolean;
  onRetry: (msg: string) => void;
  pendingApproval: {
    content?: string;
    data?: {
      reason?: string;
      kind?: InterruptKind;
      prompt?: string;
      plan?: string;
      tool_calls?: Array<{ id?: string; name?: string; args?: unknown; arguments?: unknown }>;
    };
  } | null;
  onResume(payload: ResumePayload): void;
}

export default function MessageList({ messages, isLoading, onRetry, pendingApproval, onResume }: MessageListProps) {
  if (messages.length === 0) {
    return (
      <div className="flex h-[70vh] flex-col items-center justify-center text-center px-4">
        <div className="mb-4 flex size-12 items-center justify-center border border-sky-500/30 bg-sky-500/10 text-sky-400 rounded-xl shadow-[0_0_24px_rgba(56,189,248,0.25)]">
          <Compass className="h-6 w-6" />
        </div>
        <h1 className="mb-2 text-xl font-bold tracking-tight text-foreground sm:text-2xl">
          Compass Autonomous Studio
        </h1>
        <p className="max-w-md text-xs sm:text-sm text-muted-foreground mb-6 leading-relaxed">
          Plan, scaffold, test, and self-heal full-stack code with instant in-browser live canvas and real terminal execution.
        </p>

        <div className="grid w-full max-w-lg grid-cols-1 sm:grid-cols-2 gap-2 text-left">
          <motion.button
            type="button"
            whileHover={{ y: -2, scale: 1.01 }}
            whileTap={{ scale: 0.98 }}
            onClick={() => onRetry("Build a modern responsive dashboard layout with metrics cards and dark theme")}
            className="rounded-lg border border-border/80 bg-card/60 p-3 text-xs text-muted-foreground transition-colors hover:border-sky-500/50 hover:bg-card hover:text-foreground shadow-sm"
          >
            <div className="flex items-center gap-1.5 font-medium text-foreground mb-0.5">
              <Sparkles className="h-3.5 w-3.5 text-sky-400" />
              <span>Fullstack Scaffold</span>
            </div>
            <span className="text-[11px] text-muted-foreground">Scaffold responsive app with live canvas</span>
          </motion.button>
          <motion.button
            type="button"
            whileHover={{ y: -2, scale: 1.01 }}
            whileTap={{ scale: 0.98 }}
            onClick={() => onRetry("Run tests, identify any errors or broken code, and self-heal the issues")}
            className="rounded-lg border border-border/80 bg-card/60 p-3 text-xs text-muted-foreground transition-colors hover:border-emerald-500/50 hover:bg-card hover:text-foreground shadow-sm"
          >
            <div className="flex items-center gap-1.5 font-medium text-foreground mb-0.5">
              <TestTube2 className="h-3.5 w-3.5 text-emerald-400" />
              <span>Test & Self-Heal</span>
            </div>
            <span className="text-[11px] text-muted-foreground">Autonomous test execution & bug fixing</span>
          </motion.button>
          <motion.button
            type="button"
            whileHover={{ y: -2, scale: 1.01 }}
            whileTap={{ scale: 0.98 }}
            onClick={() => onRetry("Audit visual UI layout, inspect elements, and polish typography and padding")}
            className="rounded-lg border border-border/80 bg-card/60 p-3 text-xs text-muted-foreground transition-colors hover:border-amber-500/50 hover:bg-card hover:text-foreground shadow-sm"
          >
            <div className="flex items-center gap-1.5 font-medium text-foreground mb-0.5">
              <Eye className="h-3.5 w-3.5 text-amber-400" />
              <span>Visual Canvas QA</span>
            </div>
            <span className="text-[11px] text-muted-foreground">Inspect DOM elements & polish design</span>
          </motion.button>
          <motion.button
            type="button"
            whileHover={{ y: -2, scale: 1.01 }}
            whileTap={{ scale: 0.98 }}
            onClick={() => onRetry("Review pending workspace changes, generate a clean summary, and prepare a GitHub PR")}
            className="rounded-lg border border-border/80 bg-card/60 p-3 text-xs text-muted-foreground transition-colors hover:border-purple-500/50 hover:bg-card hover:text-foreground shadow-sm"
          >
            <div className="flex items-center gap-1.5 font-medium text-foreground mb-0.5">
              <GitPullRequest className="h-3.5 w-3.5 text-purple-400" />
              <span>Staged Git Review</span>
            </div>
            <span className="text-[11px] text-muted-foreground">Verify staged patches & export pull request</span>
          </motion.button>
        </div>
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-6">
      <AnimatePresence initial={false}>
        {messages.map((msg, idx) => {
          const isUser = msg.role === "user";
          const isTool = msg.role === "tool";

          if (isUser) {
            return (
              <motion.div
                key={msg.id || idx}
                initial={{ opacity: 0, y: 8 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.2 }}
                className="group relative border-l-[3px] border-primary/50 pl-4 py-1 mt-2"
              >
                <div className="mb-1.5 flex items-center justify-between text-xs font-semibold text-muted-foreground font-mono">
                  <span className="text-sky-400">User Prompt</span>
                  {idx === messages.length - 1 && !isLoading && (
                    <button
                      className="opacity-0 group-hover:opacity-100 flex items-center gap-1 transition-opacity text-muted-foreground hover:text-foreground"
                      title="Retry message"
                      onClick={() => onRetry(msg.content || "")}
                    >
                      <RefreshCcw className="h-3 w-3" />
                    </button>
                  )}
                </div>
                <div className="whitespace-pre-wrap text-sm font-medium leading-relaxed text-foreground">
                  {msg.content}
                </div>
              </motion.div>
            );
          }

          if (isTool) {
            let parsedArgs = msg.tool_args || {};
            let toolName = msg.tool_name || "tool_call";
            let result = msg.content;

            if (!msg.tool_name && msg.content) {
              try {
                const parsed = JSON.parse(msg.content);
                if (parsed.name && parsed.arguments) {
                  toolName = parsed.name;
                  parsedArgs = parsed.arguments;
                  result = parsed.result || null;
                }
              } catch {
                // Not JSON
              }
            }

            return (
              <motion.div
                key={msg.id || idx}
                initial={{ opacity: 0, y: 6 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.18 }}
                className="pl-4 py-1 border-l-[3px] border-transparent"
              >
                <ToolCallCard
                  toolName={toolName}
                  args={parsedArgs}
                  result={result}
                  status={msg.status || "completed"}
                  error={msg.error}
                />
              </motion.div>
            );
          }

          return (
            <motion.div
              key={msg.id || idx}
              initial={{ opacity: 0, y: 8 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.2 }}
            >
              <MessageRow key={msg.id || idx} message={msg} />
            </motion.div>
          );
        })}
      </AnimatePresence>

      {pendingApproval && (
        <motion.div
          initial={{ opacity: 0, scale: 0.98, y: 4 }}
          animate={{ opacity: 1, scale: 1, y: 0 }}
          transition={{ type: "spring", stiffness: 400, damping: 28 }}
          className="mt-4 pl-4 py-1 border-l-[3px] border-warning/50"
        >
          {pendingApproval.data?.reason === "plan_approval_required" ? (
            <PlanReviewCard
              plan={pendingApproval.data.plan || "No plan details were returned."}
              onResume={onResume}
            />
          ) : pendingApproval.data?.reason === "clarification_required" || pendingApproval.data?.kind === "clarification" ? (
            <ClarificationCard
              prompt={pendingApproval.content || pendingApproval.data?.prompt || "The agent needs clarification before proceeding."}
              onResume={onResume}
            />
          ) : (
            <ToolApprovalCard interrupt={pendingApproval} onResume={onResume} />
          )}
        </motion.div>
      )}
    </div>
  );
}
