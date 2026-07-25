import { Compass, RefreshCcw } from "lucide-react";
import { Button } from "@/components/ui/button";
import MarkdownMessage from "./MarkdownMessage";
import PlanChecklist from "./PlanChecklist";
import ToolCallCard from "./ToolCallCard";
import PlanReviewCard from "./PlanReviewCard";

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
      plan?: string;
      tool_calls?: Array<{ id?: string; name?: string; args?: unknown; arguments?: unknown }>;
    };
  } | null;
  onApprove: (action: string, feedback?: string) => void;
}

export default function MessageList({ messages, isLoading, onRetry, pendingApproval, onApprove }: MessageListProps) {
  if (messages.length === 0) {
    return (
      <div className="flex h-[70vh] flex-col items-center justify-center text-center">
        <div className="mb-6 flex size-16 items-center justify-center border border-accent/30 bg-accent/10 text-accent rounded-md">
          <Compass className="h-8 w-8" />
        </div>
        <h1 className="mb-3 text-2xl font-semibold text-foreground">How can I help you today?</h1>
        <p className="max-w-md text-sm leading-6 text-muted-foreground">
          I am Compass, your AI coding assistant.
        </p>
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

        return (
          <div key={msg.id || idx} className="pl-4 py-1 border-l-[3px] border-transparent">
            {msg.plan && (
              <div className="mb-4">
                <PlanChecklist
                  plan={msg.plan}
                  completedSteps={msg.completedPlanSteps}
                />
              </div>
            )}

            {msg.content && (
              <div className="text-sm leading-relaxed text-foreground">
                <MarkdownMessage
                  content={msg.content.replace(/<thought>[\s\S]*?<\/thought>/g, '')}
                  isStreaming={msg.pending}
                />
              </div>
            )}
          </div>
        );
      })}

      {pendingApproval && (
        <div className="mt-4 pl-4 py-1 border-l-[3px] border-warning/50">
          {pendingApproval.data?.reason === "plan_approval_required" ? (
            <PlanReviewCard
              plan={pendingApproval.data.plan || "No plan details were returned."}
              onAction={(action, feedback) => {
                if (action === "execute_plan") {
                  onApprove("execute_plan");
                } else if (action === "revise_plan") {
                  onApprove("revise_plan", feedback);
                } else {
                  onApprove("cancel");
                }
              }}
            />
          ) : (
            <div>
              <div className="mb-2 flex items-center gap-2 text-xs font-semibold text-warning">
                Approval Required
              </div>
              <div className="border border-warning/20 bg-warning/10 p-4">
                <p className="mb-3 text-sm font-medium text-foreground">
                  {pendingApproval.content || "The agent wants to perform a potentially risky action."}
                </p>
                {pendingApproval.data?.tool_calls?.map((tc) => (
                  <div key={tc.id} className="text-xs font-mono bg-background/50 p-2 rounded mb-2 overflow-x-auto">
                    <span className="font-bold text-warning">{tc.name}</span>({JSON.stringify(tc.args)})
                  </div>
                ))}
                <div className="flex gap-2 mt-4 flex-wrap">
                  <Button size="sm" onClick={() => onApprove("yes")} variant="default">Approve Once</Button>
                  <Button size="sm" onClick={() => onApprove("always")} variant="outline" className="text-success border-success/20 hover:bg-success/10">Always Allow in Thread</Button>
                  <Button size="sm" onClick={() => onApprove("skip")} variant="secondary">Skip Step</Button>
                  <Button size="sm" onClick={() => onApprove("no")} variant="destructive">Deny</Button>
                </div>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
