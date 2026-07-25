import { Bot, Check, X, PencilLine, AlertTriangle } from "lucide-react";
import { Button } from "@/components/ui/button";
import { useState } from "react";
import ReactMarkdown from "react-markdown";

interface PlanReviewCardProps {
  plan: string;
  onAction: (action: "execute_plan" | "revise_plan" | "cancel", feedback?: string) => void;
}

export default function PlanReviewCard({ plan, onAction }: PlanReviewCardProps) {
  const [isRevising, setIsRevising] = useState(false);
  const [feedback, setFeedback] = useState("");

  return (
    <div className="mb-5 flex justify-start gap-3">
      <div className="mt-1 flex size-7 shrink-0 items-center justify-center rounded-sm border border-accent/20 bg-accent/10 text-accent">
        <Bot className="h-4 w-4" />
      </div>
      <div className="max-w-[85%] w-full">
        <div className="mb-1 flex items-center gap-2 text-xs font-semibold text-accent">
          <AlertTriangle className="h-3 w-3" />
          Plan Review Required
        </div>
        <div className="rounded-md border border-border bg-card p-4">
          <div className="prose prose-sm mb-4 max-w-none text-muted-foreground dark:prose-invert [&>h1]:text-foreground [&>h2]:text-foreground [&>h3]:text-foreground">
            <ReactMarkdown>{plan}</ReactMarkdown>
          </div>
          
          {isRevising ? (
            <div className="mt-4 flex flex-col gap-2">
              <textarea
                value={feedback}
                onChange={(e) => setFeedback(e.target.value)}
                placeholder="What should be changed? Provide feedback for the agent..."
                className="h-24 w-full resize-none rounded-md border border-border bg-background p-3 text-sm focus:outline-none focus:ring-1 focus:ring-accent"
                autoFocus
              />
              <div className="flex justify-end gap-2 mt-2">
                <Button size="sm" variant="ghost" onClick={() => setIsRevising(false)}>
                  Cancel
                </Button>
                <Button size="sm" className="bg-accent text-accent-foreground hover:bg-accent/90" onClick={() => onAction("revise_plan", feedback)} disabled={!feedback.trim()}>
                  Submit Revision
                </Button>
              </div>
            </div>
          ) : (
            <div className="flex gap-2 mt-4 pt-4 border-t border-border flex-wrap">
              <Button size="sm" className="bg-accent text-accent-foreground hover:bg-accent/90" onClick={() => onAction("execute_plan")}>
                <Check className="h-4 w-4 mr-2" /> Execute Plan
              </Button>
              <Button size="sm" variant="outline" className="border-border" onClick={() => setIsRevising(true)}>
                <PencilLine className="h-4 w-4 mr-2" /> Revise
              </Button>
              <Button size="sm" variant="ghost" className="rounded-none text-muted-foreground hover:text-destructive" onClick={() => onAction("cancel")}>
                <X className="h-4 w-4 mr-2" /> Cancel
              </Button>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
