import { useEffect, useMemo, useRef, useState } from "react";
import { useOutletContext, useSearchParams } from "react-router-dom";
import { Activity, Bot, FileCode2, GitPullRequest, Loader2, MessageSquare, Sparkles, UserCircle, Wrench, Terminal, RefreshCcw } from "lucide-react";
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
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { chatApi, sessionsApi, uploadsApi, workspaceApi } from "@/api";
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
  const [mobilePanel, setMobilePanel] = useState<"files" | "diffs" | "logs" | null>(null);


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
  }, [messages, isLoading]);

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
      const session = await sessionsApi.getSession(currentSessionId);
      setMessages(session.messages || []);
      window.dispatchEvent(new Event("sessions-refresh"));
    } catch {
      window.dispatchEvent(new Event("sessions-refresh"));
    }
  };

  const sendWithWebSocket = (currentSessionId: string, message: string, mode: "normal" | "plan") =>
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
          setMessages((prev) => [...prev, { id: assistantId, role: "assistant", content: "", pending: true }]);
          socket.send(JSON.stringify({ type: "message", content: message, mode }));
        };

        socket.onmessage = (event) => {
          const payload = JSON.parse(event.data);
          if (payload.type === "ping") {
            socket.send(JSON.stringify({ type: "pong" }));
            return;
          }

          if (payload.seq !== undefined) {
            if (payload.seq > expectedSeq) {
              console.warn(`Gap detected! Expected ${expectedSeq}, got ${payload.seq}`);
              // Fallback to REST API fetch
              refreshSessionAfterResponse(currentSessionId);
            }
            expectedSeq = payload.seq + 1;
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

  const sendWithHttpFallback = async (currentSessionId: string, message: string, mode: "normal" | "plan") => {
    setStreamStatus("Thinking");
    const response = await chatApi.sendMessage(currentSessionId, message, mode);
    setMessages(response.messages || []);
  };

  const handleSend = async (message: string, files: File[], mode: "normal" | "plan") => {
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

  return (
    <div className="flex h-full w-full min-h-0 flex-col lg:flex-row">
      <div className="flex min-w-0 flex-1 flex-col bg-background">
        <div className="flex-1 min-h-0">
          <ScrollArea className="h-full px-4 py-5 md:px-8">
            <div className="mx-auto flex max-w-3xl flex-col gap-5">
            {visibleMessages.length === 0 ? (
              <div className="flex h-[52vh] flex-col items-center justify-center text-center">
                <div className="mb-4 flex size-12 items-center justify-center rounded-lg border border-border bg-card text-primary">
                  <Sparkles className="h-6 w-6" />
                </div>
                <h1 className="text-xl font-semibold tracking-tight">What are we building?</h1>
                <p className="mt-2 max-w-md text-sm leading-6 text-muted-foreground">
                  Ask for code changes, upload project docs, open a folder, or switch to plan mode for deeper agent work.
                </p>
              </div>
            ) : (
              <AnimatePresence initial={false}>
                {visibleMessages.map((msg, idx) => {
                  const isUser = msg.role === "user";
                  const isTool = msg.role === "tool";
                  
                  return (
                    <motion.div 
                      key={msg.id || idx} 
                      initial={{ opacity: 0, y: 15 }}
                      animate={{ opacity: 1, y: 0 }}
                      transition={{ duration: 0.3, ease: "easeOut" }}
                      className={`optimize-list flex gap-3 ${isUser ? "justify-end" : "justify-start"}`}
                    >
                      {!isUser && (
                        <div className={`mt-1 flex size-7 shrink-0 items-center justify-center rounded-lg ${isTool ? "bg-amber-500/12 text-amber-300" : "bg-primary/12 text-primary"}`}>
                          {isTool ? <Wrench className="h-4 w-4" /> : <Bot className="h-4 w-4" />}
                        </div>
                      )}
                      <div className={`max-w-[82%] ${isUser ? "order-first" : ""}`}>
                        {!isUser && (
                          <div className="mb-1 flex items-center gap-2 text-[11px] font-semibold uppercase tracking-[0.12em] text-muted-foreground">
                            {isTool ? "Tool" : "Compass"}
                            {msg.model && <Badge variant="outline">{msg.model}</Badge>}
                          </div>
                        )}
                        <Card className={`rounded-lg px-4 py-3 ${isUser ? "bg-primary text-primary-foreground" : isTool ? "bg-amber-500/8 text-foreground" : "bg-card"}`}>
                          {!isUser && !isTool && msg.plan && (
                            <PlanChecklist
                              plan={msg.plan}
                              completedSteps={msg.completedPlanSteps}
                            />
                          )}
                          {msg.pending && !msg.content ? (
                            <MessageSkeleton />
                          ) : (
                            isTool ? (
                              <details className="group">
                                <summary className="cursor-pointer text-xs font-semibold text-amber-500/80 hover:text-amber-500 flex items-center">
                                  <span className="group-open:hidden">Show output</span>
                                  <span className="hidden group-open:inline">Hide output</span>
                                </summary>
                                <div className="mt-2 text-xs font-mono bg-background/50 p-2 rounded max-h-64 overflow-y-auto whitespace-pre-wrap">
                                  {msg.content}
                                </div>
                              </details>
                            ) : (
                              <MarkdownMessage content={msg.content || ""} isStreaming={msg.pending} />
                            )
                          )}
                        </Card>
                      </div>
                      {isUser && (
                        <div className="flex flex-col gap-1 items-center">
                          <div className="mt-1 flex size-7 shrink-0 items-center justify-center rounded-lg bg-muted text-muted-foreground">
                            <UserCircle className="h-4 w-4" />
                          </div>
                          {idx === visibleMessages.length - 1 && !isLoading && (
                            <button
                              className="flex size-7 shrink-0 items-center justify-center rounded-lg text-muted-foreground transition-colors hover:bg-muted hover:text-foreground"
                              title="Retry message"
                              onClick={() => handleSend(msg.content || "", [], "normal")}
                            >
                              <RefreshCcw className="h-3 w-3" />
                            </button>
                          )}
                        </div>
                      )}
                    </motion.div>
                  );
                })}
              </AnimatePresence>
            )}
            
            {pendingApproval && (
              <motion.div initial={{ opacity: 0, y: 15 }} animate={{ opacity: 1, y: 0 }} className="flex gap-3 justify-start">
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
                      <Button size="sm" onClick={() => handleApprovalAction("yes")} variant="default">Approve Once</Button>
                      <Button size="sm" onClick={() => handleApprovalAction("always")} variant="outline" className="text-green-500 border-green-500/20 hover:bg-green-500/10">Always Allow in Thread</Button>
                      <Button size="sm" onClick={() => handleApprovalAction("skip")} variant="secondary">Skip Step</Button>
                      <Button size="sm" onClick={() => handleApprovalAction("no")} variant="destructive">Deny</Button>
                    </div>
                  </Card>
                </div>
              </motion.div>
            )}

            <div ref={bottomRef} />
          </div>
        </ScrollArea>
        </div>

        <div className="border-t border-border bg-background/95 shrink-0">
          <div className="mx-auto flex max-w-3xl items-center justify-between px-4 pt-3 text-xs text-muted-foreground md:px-0">
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
              <Button variant="ghost" size="sm" onClick={() => setShowSandbox(!showSandbox)} className="text-muted-foreground hover:text-foreground">
                <Terminal className="h-4 w-4 mr-1" />
                {showSandbox ? "Hide Sandbox" : "Show Sandbox"}
              </Button>
            </div>
          </div>
          {pendingPatchCount > 0 && (
            <div className="mx-auto mb-2 flex max-w-3xl items-center justify-between gap-3 rounded-lg border border-amber-500/30 bg-amber-500/10 px-4 py-2 text-sm text-foreground">
              <div className="flex min-w-0 items-center gap-2">
                <GitPullRequest className="h-4 w-4 shrink-0 text-amber-500" />
                <span>{pendingPatchCount} pending patch{pendingPatchCount === 1 ? "" : "es"} ready for review</span>
              </div>
              <Button size="sm" variant="outline" onClick={() => window.dispatchEvent(new Event("review-patches-request"))}>
                Review
              </Button>
            </div>
          )}
          <ChatInput onSend={handleSend} isLoading={isLoading} />
        </div>
      </div>

      {showSandbox && (
        <aside className="hidden w-[520px] shrink-0 flex-col bg-card/70 lg:flex border-l border-border h-full min-h-0">
          <Tabs defaultValue="sandbox" className="flex h-full flex-col w-full">
            <div className="px-3 pt-3">
              <TabsList className="w-full grid grid-cols-2">
                <TabsTrigger value="sandbox">Sandbox</TabsTrigger>
                <TabsTrigger value="timeline">Timeline</TabsTrigger>
              </TabsList>
            </div>
            <TabsContent value="sandbox" className="flex-1 min-h-0 mt-0 data-[state=inactive]:hidden p-3 pt-2">
              <CodeSandbox language="typescript" sessionId={sessionId} ensureSession={ensureSession} />
            </TabsContent>
            <TabsContent value="timeline" className="flex-1 min-h-0 mt-0 data-[state=inactive]:hidden p-0">
              <RunTimeline sessionId={sessionId} />
            </TabsContent>
          </Tabs>
        </aside>
      )}

      <div className="fixed inset-x-0 bottom-0 z-40 grid grid-cols-4 border-t border-border bg-background/95 pb-[env(safe-area-inset-bottom)] lg:hidden">
        <button className="flex min-h-11 flex-col items-center justify-center text-[11px] text-primary" onClick={() => setMobilePanel(null)}>
          <MessageSquare className="h-4 w-4" /> Chat
        </button>
        <button className="flex min-h-11 flex-col items-center justify-center text-[11px] text-muted-foreground" onClick={() => setMobilePanel("files")}>
          <FileCode2 className="h-4 w-4" /> Files
        </button>
        <button className="relative flex min-h-11 flex-col items-center justify-center text-[11px] text-muted-foreground" onClick={() => setMobilePanel("diffs")}>
          <GitPullRequest className="h-4 w-4" /> Diffs
          {pendingPatchCount > 0 && <span className="absolute right-5 top-1 rounded-full bg-primary px-1 text-[10px] text-primary-foreground">{pendingPatchCount}</span>}
        </button>
        <button className="relative flex min-h-11 flex-col items-center justify-center text-[11px] text-muted-foreground" onClick={() => setMobilePanel("logs")}>
          <Activity className="h-4 w-4" /> Logs
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













