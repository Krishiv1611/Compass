import { useState } from "react";
import { Button } from "@/components/ui/button";
import type { ResumePayload } from "@/types/protocol";

interface ClarificationCardProps {
  prompt: string;
  onResume(payload: ResumePayload): void;
}

export default function ClarificationCard({ prompt, onResume }: ClarificationCardProps) {
  const [answer, setAnswer] = useState("");
  const [submitted, setSubmitted] = useState(false);

  const submit = () => {
    const feedback = answer.trim();
    if (!feedback || submitted) return;
    setSubmitted(true);
    onResume({ action: "answer", feedback });
  };

  return (
    <div className="rounded-md border border-accent/30 bg-accent/10 p-4">
      <div className="mb-2 text-xs font-semibold text-accent">Clarification required</div>
      <p className="mb-3 text-sm text-foreground">{prompt}</p>
      <textarea
        value={answer}
        onChange={event => setAnswer(event.target.value)}
        disabled={submitted}
        className="h-24 w-full resize-none rounded-md border border-border bg-background p-3 text-sm focus:outline-none focus:ring-1 focus:ring-accent"
        placeholder="Type your answer"
      />
      <div className="mt-2 flex justify-end">
        <Button size="sm" disabled={submitted || !answer.trim()} onClick={submit}>Answer</Button>
      </div>
    </div>
  );
}
