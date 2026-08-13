import { useState } from "react";
import { Button } from "@/components/ui/button";
import type { ResumeAction, ResumePayload } from "@/types/protocol";

export interface ToolApprovalInterrupt {
  content?: string;
  data?: {
    tool_calls?: Array<{
      id?: string;
      name?: string;
      args?: unknown;
      arguments?: unknown;
    }>;
  };
}

interface ToolApprovalCardProps {
  interrupt: ToolApprovalInterrupt;
  onResume(payload: ResumePayload): void;
}

const ACTIONS: Array<{ action: ResumeAction; label: string; variant: "default" | "outline" | "secondary" | "destructive" }> = [
  { action: "approve", label: "Approve once", variant: "default" },
  { action: "always", label: "Always allow for this thread", variant: "outline" },
  { action: "skip", label: "Skip", variant: "secondary" },
  { action: "deny", label: "Deny", variant: "destructive" },
];

export default function ToolApprovalCard({ interrupt, onResume }: ToolApprovalCardProps) {
  const [submitted, setSubmitted] = useState(false);

  const resume = (action: ResumeAction) => {
    if (submitted) return;
    setSubmitted(true);
    onResume({ action });
  };

  return (
    <div>
      <div className="mb-2 flex items-center gap-2 text-xs font-semibold text-warning">
        Approval required
      </div>
      <div className="border border-warning/20 bg-warning/10 p-4">
        <p className="mb-3 text-sm font-medium text-foreground">
          {interrupt.content || "The agent wants to perform a potentially risky action."}
        </p>
        {interrupt.data?.tool_calls?.map((toolCall, index) => (
          <div key={toolCall.id || `${toolCall.name}-${index}`} className="mb-2 overflow-x-auto rounded bg-background/50 p-2 font-mono text-xs">
            <span className="font-bold text-warning">{toolCall.name || "tool"}</span>
            ({JSON.stringify(toolCall.args ?? toolCall.arguments ?? {})})
          </div>
        ))}
        <div className="mt-4 flex flex-wrap gap-2">
          {ACTIONS.map(({ action, label, variant }) => (
            <Button key={action} size="sm" variant={variant} disabled={submitted} onClick={() => resume(action)}>
              {label}
            </Button>
          ))}
        </div>
      </div>
    </div>
  );
}
