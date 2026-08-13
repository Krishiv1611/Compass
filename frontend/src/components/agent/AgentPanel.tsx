import { useRef } from "react";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Loader2, GitPullRequest } from "lucide-react";
import { Button } from "@/components/ui/button";
import MessageList from "@/components/chat/MessageList";
import ChatInput from "@/components/chat/ChatInput";
import type { TranscriptMessage } from "@/components/chat/MessageList";
import type { ChatMode } from "@/types/chat";
import type { InterruptKind, ResumePayload } from "@/types/protocol";

interface AgentPanelProps {
  messages: TranscriptMessage[];
  isLoading: boolean;
  streamStatus: string;
  activeSocket: WebSocket | null;
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
  pendingPatchCount: number;
  activeWorkspaceId: string | null;
  handleSend: (content: string, files: File[], mode: ChatMode, contextFiles: string[]) => Promise<void>;
  handleResume(payload: ResumePayload): void;
  handleCancel: () => void;
  reviewPatches: () => void;
  onContextChange: (files: string[]) => void;
}

export default function AgentPanel({
  messages,
  isLoading,
  streamStatus,
  activeSocket,
  pendingApproval,
  pendingPatchCount,
  activeWorkspaceId,
  handleSend,
  handleResume,
  handleCancel,
  reviewPatches,
  onContextChange
}: AgentPanelProps) {
  const bottomRef = useRef<HTMLDivElement>(null);

  return (
    <div className="relative flex h-full min-w-0 flex-col bg-background">
      <div className="flex-1 min-h-0">
        <ScrollArea className="h-full px-4 py-5 md:px-6">
          <div className="mx-auto flex w-full max-w-3xl flex-col gap-5">
            <MessageList 
              messages={messages} 
              isLoading={isLoading} 
              onRetry={(content) => handleSend(content, [], "edit", [])}
              pendingApproval={pendingApproval} 
              onResume={handleResume}
            />
            <div ref={bottomRef} />
          </div>
        </ScrollArea>
      </div>

      <div className="border-t border-border bg-background/95 shrink-0 pb-[env(safe-area-inset-bottom)]">
        <div className="mx-auto flex w-full items-center justify-between px-4 pt-3 text-xs text-muted-foreground">
          <div className="flex items-center gap-2">
            {isLoading && (
              <>
                <Loader2 className="h-3.5 w-3.5 animate-spin text-primary" />
                <span>{streamStatus}</span>
                {activeSocket && (
                  <Button variant="ghost" size="sm" onClick={handleCancel} className="ml-2 h-7 text-xs text-muted-foreground hover:bg-destructive/10 hover:text-destructive">
                    <span className="bg-destructive w-1.5 h-1.5 rounded-sm mr-1"></span> Stop
                  </Button>
                )}
              </>
            )}
          </div>
        </div>
        
        {pendingPatchCount > 0 && (
          <div className="mx-4 mb-2 mt-2 flex items-center justify-between gap-3 rounded-md border border-warning/30 bg-warning/10 px-4 py-2 text-sm text-foreground">
            <div className="flex min-w-0 items-center gap-2">
              <GitPullRequest className="h-4 w-4 shrink-0 text-warning" />
              <span>{pendingPatchCount} pending patch{pendingPatchCount === 1 ? "" : "es"}</span>
            </div>
            <Button size="sm" variant="outline" onClick={reviewPatches}>
              Review
            </Button>
          </div>
        )}
        
        <ChatInput
          onSend={handleSend}
          isLoading={isLoading}
          workspaceId={activeWorkspaceId}
          onContextChange={onContextChange}
        />
      </div>
    </div>
  );
}
