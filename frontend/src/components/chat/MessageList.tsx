import { Bot, UserCircle, RefreshCcw } from "lucide-react";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { motion, AnimatePresence } from "framer-motion";
import MarkdownMessage from "./MarkdownMessage";
import PlanChecklist from "./PlanChecklist";
import ToolCallCard from "./ToolCallCard";
import ThinkingBlock from "./ThinkingBlock";


type Message = {
  id?: string;
  role: "user" | "assistant" | "tool" | string;
  content?: string | null;
  tool_calls?: any;
  model?: string | null;
  created_at?: string;
  pending?: boolean;
  plan?: string;
  completedPlanSteps?: number[];
  tool_name?: string;
  tool_args?: any;
  status?: "pending" | "running" | "completed" | "error";
  error?: string;
};

interface MessageListProps {
  messages: Message[];
  isLoading: boolean;
  onRetry: (msg: string) => void;
  pendingApproval: any | null;
  onApprove: (action: string) => void;
}

export default function MessageList({ messages, isLoading, onRetry, pendingApproval, onApprove }: MessageListProps) {
  if (messages.length === 0) {
    return (
      <div className="flex h-[70vh] flex-col items-center justify-center text-center">
        <div className="mb-12 glow-orb"></div>
        <h1 className="text-3xl font-light tracking-tight text-white mb-3">Ready to Create Something New?</h1>
        <p className="max-w-md text-sm leading-6 text-muted-foreground">
          Ask Compass to inspect, edit, build, or explain...
        </p>
      </div>
    );
  }

  return (
    <AnimatePresence initial={false}>
      {messages.map((msg, idx) => {
        const isUser = msg.role === "user";
        const isTool = msg.role === "tool";
        
        return (
          <motion.div 
            key={msg.id || idx} 
            initial={{ opacity: 0, y: 15 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.3, ease: "easeOut" }}
            className={`optimize-list flex gap-3 ${isUser ? "justify-end" : "justify-start"} mb-5`}
          >
            {!isUser && !isTool && (
              <div className={`mt-1 flex size-7 shrink-0 items-center justify-center rounded-lg bg-primary/12 text-primary`}>
                <Bot className="h-4 w-4" />
              </div>
            )}
            <div className={`max-w-[82%] ${isUser ? "order-first" : ""} ${isTool ? "w-full" : ""}`}>
              {!isUser && !isTool && (
                <div className="mb-1 flex items-center gap-2 text-[11px] font-semibold uppercase tracking-[0.12em] text-muted-foreground">
                  Compass {msg.model && <Badge variant="outline">{msg.model}</Badge>}
                </div>
              )}
              
              {isTool ? (
                (() => {
                  let parsedArgs = msg.tool_args || {};
                  let toolName = msg.tool_name || "tool_call";
                  let result = msg.content;
                  
                  // Try to parse the content if it looks like a JSON dump of a tool call
                  if (!msg.tool_name && msg.content) {
                    try {
                      // Some backends return the tool result as JSON
                      const parsed = JSON.parse(msg.content);
                      if (parsed.name && parsed.arguments) {
                        toolName = parsed.name;
                        parsedArgs = parsed.arguments;
                        result = parsed.result || null;
                      }
                    } catch (e) {
                      // Not JSON, just use default
                    }
                  }

                  return (
                    <ToolCallCard 
                      toolName={toolName} 
                      args={parsedArgs} 
                      result={result} 
                      status={msg.status || "completed"} 
                      error={msg.error}
                    />
                  );
                })()
              ) : (
                <div className={`rounded-xl px-4 py-3 ${isUser ? "bg-muted text-foreground" : "text-foreground"}`}>
                  {!isUser && msg.plan && (
                    <PlanChecklist
                      plan={msg.plan}
                      completedSteps={msg.completedPlanSteps}
                    />
                  )}
                  
                  {/* Thinking block for backend thought traces, or just a loader if pending */}
                  {!isUser && msg.pending && !msg.content ? (
                    <ThinkingBlock isProcessing={true} />
                  ) : !isUser && (msg.content?.includes("<thought>") || false) ? (
                    <ThinkingBlock 
                      content={msg.content?.match(/<thought>([\s\S]*?)<\/thought>/)?.[1]} 
                    />
                  ) : null}
                  
                  {/* Actual message content */}
                  {msg.content && (
                    <MarkdownMessage 
                      content={msg.content.replace(/<thought>[\s\S]*?<\/thought>/g, '')} 
                      isStreaming={msg.pending} 
                    />
                  )}
                </div>
              )}
            </div>
            
            {isUser && (
              <div className="flex flex-col gap-1 items-center">
                <div className="mt-1 flex size-7 shrink-0 items-center justify-center rounded-lg bg-muted text-muted-foreground">
                  <UserCircle className="h-4 w-4" />
                </div>
                {idx === messages.length - 1 && !isLoading && (
                  <button
                    className="flex size-7 shrink-0 items-center justify-center rounded-lg text-muted-foreground transition-colors hover:bg-muted hover:text-foreground"
                    title="Retry message"
                    onClick={() => onRetry(msg.content || "")}
                  >
                    <RefreshCcw className="h-3 w-3" />
                  </button>
                )}
              </div>
            )}
          </motion.div>
        );
      })}

      {pendingApproval && (
        <motion.div initial={{ opacity: 0, y: 15 }} animate={{ opacity: 1, y: 0 }} className="flex gap-3 justify-start mb-5">
          <div className="mt-1 flex size-7 shrink-0 items-center justify-center rounded-lg bg-red-500/12 text-red-500">
            <Bot className="h-4 w-4" />
          </div>
          <div className="max-w-[82%]">
            <div className="mb-1 flex items-center gap-2 text-[11px] font-semibold uppercase tracking-[0.12em] text-red-500">
              Approval Required
            </div>
            <Card className="rounded-lg p-4 bg-red-500/10 border-red-500/20">
              <p className="text-sm font-medium mb-3 text-foreground">
                {pendingApproval.content || "The agent wants to perform a potentially risky action."}
              </p>
              {pendingApproval.data?.tool_calls?.map((tc: any) => (
                <div key={tc.id} className="text-xs font-mono bg-background/50 p-2 rounded mb-2 overflow-x-auto">
                  <span className="font-bold text-red-400">{tc.name}</span>({JSON.stringify(tc.args)})
                </div>
              ))}
              <div className="flex gap-2 mt-4 flex-wrap">
                <Button size="sm" onClick={() => onApprove("yes")} variant="default">Approve Once</Button>
                <Button size="sm" onClick={() => onApprove("always")} variant="outline" className="text-green-500 border-green-500/20 hover:bg-green-500/10">Always Allow in Thread</Button>
                <Button size="sm" onClick={() => onApprove("skip")} variant="secondary">Skip Step</Button>
                <Button size="sm" onClick={() => onApprove("no")} variant="destructive">Deny</Button>
              </div>
            </Card>
          </div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}
