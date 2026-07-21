import { useEffect, useMemo, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { useOutletContext, useSearchParams } from "react-router-dom";
import { Activity, Bot, FileCode2, GitPullRequest, Loader2, MessageSquare, Sparkles, UserCircle, Wrench, Terminal, RefreshCcw, LayoutGrid } from "lucide-react";
import { toast } from "react-toastify";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Badge } from "@/components/ui/badge";
import CodeSandbox from "@/components/sandbox/CodeSandbox";
import ChatInput from "@/components/chat/ChatInput";
import LoginModal from "@/components/auth/LoginModal";
import MessageSkeleton from "@/components/chat/MessageSkeleton";
import RunTimeline from "@/components/chat/RunTimeline";
import PlanChecklist from "@/components/chat/PlanChecklist";
import MessageList from "@/components/chat/MessageList";
import { Allotment } from "allotment";
import "allotment/dist/style.css";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { chatApi, sessionsApi, uploadsApi, workspaceApi, runsApi } from "@/api";
import { motion, AnimatePresence } from "framer-motion";
import MarkdownMessage from "@/components/chat/MarkdownMessage";
import { useRunEvents } from "@/contexts/RunContext";

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
};

type OutletContext = {
  user: any | null;
  refreshUser: () => Promise<void>;
};

const titleFromMessage = (message: string) => {
  const cleaned = message.replace(/[`*_#>()]/g, " ").replace(/[[\]]/g, " ").replace(/\s+/g, " ").trim();
  if (!cleaned) return "New Chat";
  const words = cleaned.split(" ").slice(0, 6).join(" ");
  return words.length > 54 ? `${words.slice(0, 51)}...` : words;
};

export default function ChatPage() {
  const { refreshUser } = useOutletContext<OutletContext>();
  const { addEvent, clearRun, finishRun, isRunActive, startRun } = useRunEvents();
  const [showLogin, setShowLogin] = useState(false);
  const [showSandbox, setShowSandbox] = useState(true);
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [messages, setMessages] = useState<Message[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [streamStatus, setStreamStatus] = useState("Ready");
  const [activeSocket, setActiveSocket] = useState<WebSocket | null>(null);
  const [activeRunId, setActiveRunId] = useState<string | null>(null);
  const [pendingApproval, setPendingApproval] = useState<any | null>(null);
  const [pendingPatchCount, setPendingPatchCount] = useState(0);
  const lastSeqRef = useRef<number>(0);
  const [mobilePanel, setMobilePanel] = useState<"chat" | "sandbox" | "diffs" | "files" | "logs" | null>(null);
  const [headerNode, setHeaderNode] = useState<HTMLElement | null>(null);

  useEffect(() => {
    setHeaderNode(document.getElementById("header-actions"));
  }, []);

  const refreshPendingPatches = async (currentSessionId: string) => {
    try {
      const workspaces = await workspaceApi.listWorkspaces(currentSessionId);
      const workspace = workspaces?.[0];
      if (!workspace?.id) {
        setPendingPatchCount(0);
        return;
      }
      const patches = await workspaceApi.getPatches(workspace.id);
      setPendingPatchCount(patches.filter((patch: any) => patch.status === "pending").length);
    } catch {
      setPendingPatchCount(0);
    }
  };
  const handleApprovalAction = (action: string) => {
    if (activeSocket) {
      activeSocket.send(JSON.stringify({ type: "resume", action }));
      setPendingApproval(null);
      setStreamStatus("Streaming");
    }
  };

  const handleCancel = () => {
    if (activeSocket) {
      if (sessionId && activeRunId) {
        runsApi.cancelRun(sessionId, activeRunId).catch((err) => {
          console.error("Failed to cancel backend run", err);
        });
      }
      activeSocket.close();
      setActiveSocket(null);
      setActiveRunId(null);
      setStreamStatus("Cancelled");
      setIsLoading(false);
      finishRun();
    }
  };
  const [searchParams, setSearchParams] = useSearchParams();
  const sessionParam = searchParams.get("session");
  const bottomRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [messages, isLoading, pendingApproval]);

  useEffect(() => {
    let cancelled = false;

    const loadSession = async () => {
      if (!sessionParam) {
        setSessionId(null);
        setMessages([]);
        setStreamStatus("Ready");
        return;
      }

      try {
        setStreamStatus("Loading chat");
        const session = await sessionsApi.getSession(sessionParam);
        if (cancelled) return;
        setSessionId(session.id);
        setMessages(session.messages || []);
        setStreamStatus("Ready");
      } catch (error: any) {
        if (!cancelled) {
          toast.error(error?.response?.data?.detail || "Failed to load session", { toastId: "load-session-error" });
          setSessionId(null);
          setMessages([]);
          setStreamStatus("Ready");
        }
      }
    };

    loadSession();
    return () => {
      cancelled = true;
    };
  }, [sessionParam]);

  useEffect(() => {
    const handleNewChat = () => {
      setSessionId(null);
      setMessages([]);
      setSearchParams({});
      setStreamStatus("Ready");
      setPendingApproval(null);
      setActiveSocket(null);
      setPendingPatchCount(0);
      clearRun();
    };
    window.addEventListener("new-chat", handleNewChat);
    return () => window.removeEventListener("new-chat", handleNewChat);
  }, [setSearchParams]);


  useEffect(() => {
    if (mobilePanel === "diffs") {
      window.setTimeout(() => window.dispatchEvent(new Event("review-patches-request")), 0);
    }
  }, [mobilePanel]);
  const visibleMessages = useMemo(
    () => messages.filter((message) => message.content || message.tool_calls),
    [messages]
  );

  const ensureSession = async (message: string = "New Chat") => {
    if (sessionId) return sessionId;
    const optimisticTitle = titleFromMessage(message);
    const session = await sessionsApi.createSession(optimisticTitle);
    setSessionId(session.id);
    setSearchParams({ session: session.id });
    window.dispatchEvent(new Event("sessions-refresh"));
    return session.id as string;
  };

  const uploadFiles = async (currentSessionId: string, files: File[]) => {
    if (files.length === 0) return;
    setStreamStatus("Indexing files");
    const uploads = await Promise.allSettled(files.map((file) => uploadsApi.uploadFile(currentSessionId, file)));
    const failed = uploads.filter((upload) => upload.status === "rejected").length;
    if (failed) {
      toast.warning(`${failed} attachment${failed > 1 ? "s" : ""} could not be indexed`, { toastId: "upload-warning" });
    } else {
      toast.success(`${files.length} attachment${files.length > 1 ? "s" : ""} indexed`, { toastId: "upload-success" });
    }
  };

  const refreshSessionAfterResponse = async (currentSessionId: string) => {
    try {
      // Just fire the event to update the sidebar, we already maintain messages via stream
      window.dispatchEvent(new Event("sessions-refresh"));
    } catch {
      window.dispatchEvent(new Event("sessions-refresh"));
    }
  };

  const sendWithWebSocket = (currentSessionId: string, message: string, mode: "normal" | "plan" | "fast" | "goal") =>
    new Promise<boolean>((resolve, reject) => {
      let retryCount = 0;
      const MAX_RETRIES = 3;
      const RETRY_DELAY_MS = 1500;

      const attempt = () => {
        const socket = chatApi.createWebSocket(currentSessionId);
        setActiveSocket(socket);
        let opened = false;
        let completed = false;
        const assistantId = `assistant-${Date.now()}`;
        let expectedSeq = 1;

        const failTimer = window.setTimeout(() => {
          if (!opened) {
            socket.close();
            reject(new Error("Streaming connection timed out"));
          }
        }, 4500);

        socket.onopen = () => {
          opened = true;
          window.clearTimeout(failTimer);
          setStreamStatus("Streaming");
          if (lastSeqRef.current > 0 && activeRunId) {
             socket.send(JSON.stringify({ type: "resume", run_id: activeRunId, last_seq: lastSeqRef.current, mode }));
          } else {
             setMessages((prev) => [...prev, { id: assistantId, role: "assistant", content: "", pending: true }]);
             socket.send(JSON.stringify({ type: "message", content: message, mode }));
          }
        };

        socket.onmessage = (event) => {
          const payload = JSON.parse(event.data);
          if (payload.type === "ping") {
            socket.send(JSON.stringify({ type: "pong" }));
            return;
          }

          if (payload.seq !== undefined) {
            if (payload.seq <= lastSeqRef.current) {
                // Ignore old events during replay
                return;
            }
            if (payload.seq > expectedSeq) {
              console.warn(`Gap detected! Expected ${expectedSeq}, got ${payload.seq}`);
              // Fallback to REST API fetch
              refreshSessionAfterResponse(currentSessionId);
            }
            expectedSeq = payload.seq + 1;
            lastSeqRef.current = payload.seq;
          }

          if (payload.run_id) {
            setActiveRunId(payload.run_id);
          }

          addEvent(payload);
          const msgId = payload.message_id || assistantId;

          if (payload.type === "token" || payload.type === "assistant_delta") {
            setMessages((prev) => {
              const exists = prev.some((item) => item.id === msgId);
              if (!exists) {
                return [...prev, { id: msgId, role: "assistant", content: payload.content || "", pending: true }];
              }
              return prev.map((item) =>
                item.id === msgId ? { ...item, content: `${item.content || ""}${payload.content || ""}` } : item
              );
            });
          }
          if (payload.type === "tool_call") {
            setMessages((prev) => [
              ...prev,
              { id: `tool-call-${payload.tool_call_id || Date.now()}`, role: "tool", content: `Calling ${payload.tool_call?.name || "tool"}` },
            ]);
            setStreamStatus(`Using ${payload.tool_call?.name || "tool"}`);
          }
          if (payload.type === "rpc_call") {
            // Execute the RPC call locally and send back the result
            const callId = payload.data?.call_id || payload.tool_call_id;
            const toolName = payload.data?.name || payload.tool_call?.name;
            const toolArgs = payload.data?.args || payload.tool_call?.args || {};
            try {
              // Dispatch to any registered local RPC handlers
              const rpcEvent = new CustomEvent("rpc-execute", {
                detail: { callId, toolName, toolArgs, raw: payload }
              });
              window.dispatchEvent(rpcEvent);
              // Default: echo back a not-supported result so the agent can continue
              socket.send(JSON.stringify({
                type: "tool_result",
                call_id: callId,
                result: `RPC tool '${toolName}' executed in browser context`,
              }));
            } catch (rpcErr: any) {
              socket.send(JSON.stringify({
                type: "tool_result",
                call_id: callId,
                error: String(rpcErr?.message || rpcErr),
              }));
            }
          }
          if (payload.type === "tool_result") {
            setMessages((prev) => [
              ...prev,
              { id: `tool-result-${payload.tool_call_id || Date.now()}`, role: "tool", content: payload.content || "Tool completed" },
            ]);
          }
          if (payload.type === "plan_created") {
            setMessages((prev) => {
              const exists = prev.some((item) => item.id === msgId);
              if (!exists) {
                return [
                  ...prev,
                  {
                    id: msgId,
                    role: "assistant",
                    content: "",
                    pending: true,
                    plan: payload.content || "",
                    completedPlanSteps: [],
                  },
                ];
              }
              return prev.map((item) =>
                item.id === msgId
                  ? { ...item, plan: payload.content || "", completedPlanSteps: [] }
                  : item
              );
            });
          }
          if (payload.type === "plan_step") {
            const step =
              payload.data?.step_index ??
              payload.data?.step ??
              payload.data?.current_step;
            if (step !== undefined) {
              setMessages((prev) =>
                prev.map((item) =>
                  item.id === msgId
                    ? {
                        ...item,
                        completedPlanSteps: Array.from(
                          new Set([...(item.completedPlanSteps || []), Number(step)])
                        ),
                      }
                    : item
                )
              );
            }
          }
          if (payload.type === "workspace_patch") {
            refreshPendingPatches(currentSessionId);
            window.dispatchEvent(new Event("workspace-updated"));
          }
          if (payload.type === "approval_required") {
            setPendingApproval(payload);
            setStreamStatus("Waiting for approval");
          }
          if (payload.type === "done") {
            completed = true;
            setActiveSocket(null);
            socket.close();
            setMessages((prev) => prev.map((item) => (item.id === msgId ? { ...item, pending: false } : item)));
            setIsLoading(false);
            lastSeqRef.current = 0; // Reset
            finishRun();
            window.dispatchEvent(new Event("agent-done"));
            resolve(true);
          }
          if (payload.type === "error") {
            completed = true;
            setActiveSocket(null);
            socket.close();
            setIsLoading(false);
            finishRun();
            reject(new Error(payload.content || "Streaming failed"));
          }
        };

        socket.onerror = () => {
          window.clearTimeout(failTimer);
          if (!completed) {
            if (opened) {
              // Opened but errored mid-stream â€” retry
              if (retryCount < MAX_RETRIES) {
                retryCount++;
                setStreamStatus(`Reconnecting (${retryCount}/${MAX_RETRIES})...`);
                setTimeout(attempt, RETRY_DELAY_MS);
              } else {
                reject(new Error("Streaming interrupted"));
              }
            } else {
              reject(new Error("Streaming unavailable"));
            }
          }
        };

        socket.onclose = () => {
          window.clearTimeout(failTimer);
          if (!opened && !completed) {
            if (retryCount < MAX_RETRIES) {
              retryCount++;
              setStreamStatus(`Reconnecting (${retryCount}/${MAX_RETRIES})...`);
              setTimeout(attempt, RETRY_DELAY_MS);
            } else {
              reject(new Error("Streaming unavailable"));
            }
          }
        };
      };

      attempt();
    });

  const sendWithHttpFallback = async (currentSessionId: string, message: string, mode: "normal" | "plan" | "fast" | "goal") => {
    setStreamStatus("Thinking");
    const response = await chatApi.sendMessage(currentSessionId, message, mode);
    setMessages(response.messages || []);
  };

  const handleSend = async (message: string, files: File[], mode: "normal" | "plan" | "fast" | "goal") => {
    const token = sessionStorage.getItem("compass_access_token");
    if (!token) {
      setShowLogin(true);
      return;
    }

    const cleanMessage = message.trim() || "Use the attached files.";
    const userMessage: Message = { id: `user-${Date.now()}`, role: "user", content: cleanMessage };

    try {
      setIsLoading(true);
      const currentSessionId = await ensureSession(cleanMessage);
      startRun(currentSessionId);
      await uploadFiles(currentSessionId, files);
      setMessages((prev) => [...prev, userMessage]);

      try {
        lastSeqRef.current = 0;
        await sendWithWebSocket(currentSessionId, cleanMessage, mode);
      } catch (streamError: any) {
        if (streamError?.message === "Streaming unavailable" || streamError?.message === "Streaming connection timed out") {
          toast.info("Streaming unavailable, using standard response", { toastId: "streaming-unavailable" });
          await sendWithHttpFallback(currentSessionId, cleanMessage, mode);
        } else {
          throw streamError;
        }
      }

      await refreshSessionAfterResponse(currentSessionId);
      await refreshPendingPatches(currentSessionId);
      setStreamStatus("Ready");
    } catch (error: any) {
      toast.error(error?.response?.data?.detail || error?.message || "Failed to send message", { toastId: "send-message-error" });
      setStreamStatus("Ready");
    } finally {
      setIsLoading(false);
    }
  };

  const MIN_SIDEBAR_WIDTH = 200;
  const MAX_SIDEBAR_WIDTH = 800;
  const DEFAULT_CONVERSATION_SIDEBAR_WIDTH = 400;
  const DEFAULT_MAIN_SIZE = 1000;

  const chatUI = (
    <div className="flex h-full min-w-0 flex-col bg-background relative transition-all duration-300">
      <div className="flex-1 min-h-0">
        <ScrollArea className="h-full px-4 py-5 md:px-6">
          <div className="mx-auto flex w-full flex-col gap-5">
            <MessageList 
              messages={visibleMessages} 
              isLoading={isLoading} 
              onRetry={(content) => handleSend(content, [], "normal")} 
              pendingApproval={pendingApproval} 
              onApprove={handleApprovalAction} 
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
                <span className="animate-pulse">{streamStatus}</span>
                {activeSocket && (
                  <Button variant="ghost" size="sm" onClick={handleCancel} className="h-6 text-[10px] uppercase text-muted-foreground ml-2 hover:text-red-400 hover:bg-red-500/10">
                    <span className="bg-red-500 w-1.5 h-1.5 rounded-sm mr-1"></span> Stop
                  </Button>
                )}
              </>
            )}
          </div>
          <div className="hidden items-center gap-2 sm:flex">
          </div>
        </div>
        
        {pendingPatchCount > 0 && (
          <div className="mx-4 mb-2 mt-2 flex items-center justify-between gap-3 rounded-lg border border-amber-500/30 bg-amber-500/10 px-4 py-2 text-sm text-foreground">
            <div className="flex min-w-0 items-center gap-2">
              <GitPullRequest className="h-4 w-4 shrink-0 text-amber-500" />
              <span>{pendingPatchCount} pending patch{pendingPatchCount === 1 ? "" : "es"}</span>
            </div>
            <Button size="sm" variant="outline" onClick={() => window.dispatchEvent(new Event("review-patches-request"))}>
              Review
            </Button>
          </div>
        )}
        
        <ChatInput onSend={handleSend} isLoading={isLoading} />
      </div>
    </div>
  );

  return (
    <div className="flex h-full w-full min-h-0 flex-col lg:flex-row bg-background">
      {headerNode && createPortal(
        <Button 
          variant={showSandbox ? "secondary" : "ghost"} 
          size="icon-sm" 
          className="h-7 w-7 text-muted-foreground hover:text-foreground mr-2" 
          onClick={() => setShowSandbox(!showSandbox)} 
          title={showSandbox ? "Close Sandbox" : "Open Sandbox"}
        >
          <LayoutGrid className="h-4 w-4" />
        </Button>,
        headerNode
      )}

      {showSandbox ? (
        <div className="flex-1 min-h-0 h-full w-full">
          <CodeSandbox 
            language="typescript" 
            sessionId={sessionId} 
            ensureSession={ensureSession}
            chatPanel={chatUI}
            timelinePanel={<RunTimeline sessionId={sessionId} />}
          />
        </div>
      ) : (
        <div className="flex min-w-0 flex-col bg-background relative flex-1">
          {chatUI}
        </div>
      )}

      <div className="fixed inset-x-0 bottom-0 z-40 grid grid-cols-4 border-t border-border bg-background/95 pb-[env(safe-area-inset-bottom)] lg:hidden">
        <button className="flex min-h-11 flex-col items-center justify-center text-[11px] text-primary hover:text-primary/80 transition-colors" onClick={() => setMobilePanel(null)}>
          <MessageSquare className="h-4 w-4 mb-0.5" /> Chat
        </button>
        <button className="flex min-h-11 flex-col items-center justify-center text-[11px] text-muted-foreground hover:text-foreground transition-colors" onClick={() => setMobilePanel("files")}>
          <FileCode2 className="h-4 w-4 mb-0.5" /> Files
        </button>
        <button className="relative flex min-h-11 flex-col items-center justify-center text-[11px] text-muted-foreground hover:text-foreground transition-colors" onClick={() => setMobilePanel("diffs")}>
          <GitPullRequest className="h-4 w-4 mb-0.5" /> Diffs
          {pendingPatchCount > 0 && <span className="absolute right-5 top-1 rounded-full bg-primary px-1 text-[10px] text-primary-foreground">{pendingPatchCount}</span>}
        </button>
        <button className="relative flex min-h-11 flex-col items-center justify-center text-[11px] text-muted-foreground hover:text-foreground transition-colors" onClick={() => setMobilePanel("logs")}>
          <Activity className="h-4 w-4 mb-0.5" /> Logs
          {isRunActive && <span className="absolute right-5 top-1 h-2 w-2 rounded-full bg-green-500" />}
        </button>
      </div>

      <AnimatePresence>
        {mobilePanel && (
          <motion.div
            className="fixed inset-x-0 bottom-0 z-50 flex h-[88dvh] flex-col rounded-t-lg border-t border-border bg-card shadow-2xl lg:hidden"
            initial={{ y: "100%" }}
            animate={{ y: 0 }}
            exit={{ y: "100%" }}
            transition={{ duration: 0.2 }}
          >
            <div className="flex h-11 shrink-0 items-center justify-between border-b border-border px-3">
              <span className="text-sm font-semibold capitalize">{mobilePanel}</span>
              <Button size="sm" variant="ghost" onClick={() => setMobilePanel(null)}>Close</Button>
            </div>
            <div className="min-h-0 flex-1 overflow-hidden p-2">
              {mobilePanel === "logs" ? (
                <RunTimeline sessionId={sessionId} />
              ) : (
                <CodeSandbox language="typescript" sessionId={sessionId} ensureSession={ensureSession} />
              )}
            </div>
          </motion.div>
        )}
      </AnimatePresence>
      <LoginModal
        isOpen={showLogin}
        onClose={() => setShowLogin(false)}
        onSuccess={async () => {
          await refreshUser();
          window.dispatchEvent(new Event("auth-changed"));
        }}
      />
    </div>
  );
}













