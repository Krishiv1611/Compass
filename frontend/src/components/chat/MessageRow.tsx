import { memo } from "react";
import type { TranscriptMessage } from "./MessageList";
import MarkdownMessage from "./MarkdownMessage";
import PlanChecklist from "./PlanChecklist";
import StreamingText from "./StreamingText";

function MessageRow({ message }: { message: TranscriptMessage }) {
  const content = message.content?.replace(/<thought>[\s\S]*?<\/thought>/g, "") ?? "";
  return (
    <div className="border-l-[3px] border-transparent py-1 pl-4">
      {message.plan && <div className="mb-4"><PlanChecklist plan={message.plan} completedSteps={message.completedPlanSteps} /></div>}
      {content && (message.pending
        ? <StreamingText content={content} />
        : <div className="text-sm leading-relaxed text-foreground"><MarkdownMessage content={content} /></div>)}
    </div>
  );
}

export default memo(MessageRow);
