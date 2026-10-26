import { Compass, RefreshCcw } from "lucide-react";
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
        <div className="mb-4 flex size-14 items-center justify-center border border-sky-500/30 bg-sky-500/10 text-sky-400 rounded-lg shadow-sm">
          <Compass className="h-7 w-7" />
        </div>
        <h1 className="mb-2 text-2xl font-bold tracking-tight text-foreground">How can I help you today?</h1>
        <p className="max-w-md text-sm text-muted-foreground mb-6">
          I am Compass, your AI coding assistant. Ask questions, generate UI components, or edit full-stack code.
        </p>

        <div className="grid w-full max-w-md grid-cols-1 sm:grid-cols-2 gap-2 text-left">
          <button
            type="button"
            onClick={() => onRetry("Build a modern hero section with call-to-action buttons and responsive layout")}
            className="rounded-md border border-border bg-card/60 p-2.5 text-xs text-muted-foreground transition-colors hover:border-sky-500/50 hover:bg-card hover:text-foreground"
          >
            <span className="block font-medium text-foreground">✨ Hero Section</span>
            <span>Create responsive hero with CTA</span>
          </button>
          <button
            type="button"
            onClick={() => onRetry("Add a dark mode theme toggle with persistent state in localStorage")}
            className="rounded-md border border-border bg-card/60 p-2.5 text-xs text-muted-foreground transition-colors hover:border-sky-500/50 hover:bg-card hover:text-foreground"
          >
            <span className="block font-medium text-foreground">🌙 Dark Mode Toggle</span>
            <span>Stateful theme switcher</span>
          </button>
          <button
            type="button"
            onClick={() => onRetry("Inspect element styling and polish typography and spacing")}
            className="rounded-md border border-border bg-card/60 p-2.5 text-xs text-muted-foreground transition-colors hover:border-sky-500/50 hover:bg-card hover:text-foreground"
          >
            <span className="block font-medium text-foreground">🎯 Polish Styling</span>
            <span>Refine layout and typography</span>
          </button>
          <button
            type="button"
            onClick={() => onRetry("Run tests, identify any errors or broken code, and propose a fix")}
            className="rounded-md border border-border bg-card/60 p-2.5 text-xs text-muted-foreground transition-colors hover:border-sky-500/50 hover:bg-card hover:text-foreground"
          >
            <span className="block font-medium text-foreground">🧪 Test & Self-Heal</span>
            <span>Execute tests & fix bugs</span>
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-6">
      {messages.map((msg, idx) => {
        const isUser = msg.role === "user";
        const isTool = msg.role === "tool";

        if (isUser) {
          return (
            <div key={msg.id || idx} className="group relative border-l-[3px] border-border pl-4 py-1 mt-2">
              <div className="mb-2 flex items-center justify-between text-xs font-semibold text-muted-foreground">
                <span>Task</span>
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
            </div>
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
            <div key={msg.id || idx} className="pl-4 py-1 border-l-[3px] border-transparent">
              <ToolCallCard
                toolName={toolName}
                args={parsedArgs}
                result={result}
                status={msg.status || "completed"}
                error={msg.error}
              />
            </div>
          );
        }

        return <MessageRow key={msg.id || idx} message={msg} />;
      })}

      {pendingApproval && (
        <div className="mt-4 pl-4 py-1 border-l-[3px] border-warning/50">
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
        </div>
      )}
    </div>
  );
}
