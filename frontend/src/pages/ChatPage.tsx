import { useEffect, useMemo, useRef, useState } from "react";
import { useOutletContext, useSearchParams } from "react-router-dom";
import { Bot, Loader2, Sparkles, UserCircle, Wrench, Terminal } from "lucide-react";
import { toast } from "react-toastify";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Badge } from "@/components/ui/badge";
import CodeSandbox from "@/components/sandbox/CodeSandbox";
import ChatInput from "@/components/chat/ChatInput";
import LoginModal from "@/components/auth/LoginModal";
import { chatApi, sessionsApi, uploadsApi } from "@/api";

type Message = {
  id?: string;
  role: "user" | "assistant" | "tool" | string;
  content?: string | null;
  tool_calls?: any;
  model?: string | null;
  created_at?: string;
  pending?: boolean;
};

type OutletContext = {
  user: any | null;
  refreshUser: () => Promise<void>;
};

const titleFromMessage = (message: string) => {
  const cleaned = message.replace(/[`*_#>()]/g, " ").replace(/[\[\]]/g, " ").replace(/\s+/g, " ").trim();
  if (!cleaned) return "New Chat";
  const words = cleaned.split(" ").slice(0, 6).join(" ");
  return words.length > 54 ? `${words.slice(0, 51)}...` : words;
};

export default function ChatPage() {
  const { refreshUser } = useOutletContext<OutletContext>();
  const [showLogin, setShowLogin] = useState(false);
  const [showSandbox, setShowSandbox] = useState(true);
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [messages, setMessages] = useState<Message[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [streamStatus, setStreamStatus] = useState("Ready");
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
          toast.error(error?.response?.data?.detail || "Failed to load session");
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
    };
    window.addEventListener("new-chat", handleNewChat);
    return () => window.removeEventListener("new-chat", handleNewChat);
  }, [setSearchParams]);

  const visibleMessages = useMemo(
    () => messages.filter((message) => message.content || message.tool_calls),
    [messages]
  );

  const ensureSession = async (message: string) => {
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
      toast.warning(`${failed} attachment${failed > 1 ? "s" : ""} could not be indexed`);
    } else {
      toast.success(`${files.length} attachment${files.length > 1 ? "s" : ""} indexed`);
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
      const socket = chatApi.createWebSocket(currentSessionId);
      let opened = false;
      let completed = false;
      const assistantId = `assistant-${Date.now()}`;

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
        const data = JSON.parse(event.data);
        if (data.type === "ping") {
          socket.send(JSON.stringify({ type: "pong" }));
          return;
        }
        if (data.type === "token") {
          setMessages((prev) =>
            prev.map((item) =>
              item.id === assistantId ? { ...item, content: `${item.content || ""}${data.content || ""}` } : item
            )
          );
        }
        if (data.type === "tool_call") {
          setMessages((prev) => [
            ...prev,
            { id: `tool-call-${Date.now()}`, role: "tool", content: `Calling ${data.tool_call?.name || "tool"}` },
          ]);
          setStreamStatus(`Using ${data.tool_call?.name || "tool"}`);
        }
        if (data.type === "tool_result") {
          setMessages((prev) => [
            ...prev,
            { id: `tool-result-${Date.now()}`, role: "tool", content: data.content || "Tool completed" },
          ]);
        }
        if (data.type === "done") {
          completed = true;
          socket.close();
          setMessages((prev) => prev.map((item) => (item.id === assistantId ? { ...item, pending: false } : item)));
          resolve(true);
        }
        if (data.type === "error") {
          completed = true;
          socket.close();
          reject(new Error(data.content || "Streaming failed"));
        }
      };

      socket.onerror = () => {
        window.clearTimeout(failTimer);
        if (!completed) reject(new Error(opened ? "Streaming interrupted" : "Streaming unavailable"));
      };

      socket.onclose = () => {
        window.clearTimeout(failTimer);
        if (!opened && !completed) reject(new Error("Streaming unavailable"));
      };
    });

  const sendWithHttpFallback = async (currentSessionId: string, message: string, mode: "normal" | "plan") => {
    setStreamStatus("Thinking");
    const response = await chatApi.sendMessage(currentSessionId, message, mode);
    setMessages(response.messages || []);
  };

  const handleSend = async (message: string, files: File[], mode: "normal" | "plan") => {
    const token = localStorage.getItem("compass_access_token");
    if (!token) {
      setShowLogin(true);
      return;
    }

    const cleanMessage = message.trim() || "Use the attached files.";
    const userMessage: Message = { id: `user-${Date.now()}`, role: "user", content: cleanMessage };

    try {
      setIsLoading(true);
      const currentSessionId = await ensureSession(cleanMessage);
      await uploadFiles(currentSessionId, files);
      setMessages((prev) => [...prev, userMessage]);

      try {
        await sendWithWebSocket(currentSessionId, cleanMessage, mode);
      } catch (streamError: any) {
        if (streamError?.message === "Streaming unavailable" || streamError?.message === "Streaming connection timed out") {
          toast.info("Streaming unavailable, using standard response");
          await sendWithHttpFallback(currentSessionId, cleanMessage, mode);
        } else {
          throw streamError;
        }
      }

      await refreshSessionAfterResponse(currentSessionId);
      setStreamStatus("Ready");
    } catch (error: any) {
      toast.error(error?.response?.data?.detail || error?.message || "Failed to send message");
      setStreamStatus("Ready");
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="flex h-full w-full min-h-0 flex-col lg:flex-row">
      <div className="flex min-w-0 flex-1 flex-col bg-background">
        <ScrollArea className="min-h-0 flex-1 px-4 py-5 md:px-8">
            <div className="mx-auto flex max-w-3xl flex-col gap-5">
            {visibleMessages.length === 0 ? (
              <div className="flex min-h-[52vh] flex-col items-center justify-center text-center">
                <div className="mb-4 flex size-12 items-center justify-center rounded-lg border border-border bg-card text-primary">
                  <Sparkles className="h-6 w-6" />
                </div>
                <h1 className="text-xl font-semibold tracking-tight">What are we building?</h1>
                <p className="mt-2 max-w-md text-sm leading-6 text-muted-foreground">
                  Ask for code changes, upload project docs, open a folder, or switch to plan mode for deeper agent work.
                </p>
              </div>
            ) : (
              visibleMessages.map((msg, idx) => {
                const isUser = msg.role === "user";
                const isTool = msg.role === "tool";
                return (
                  <div key={msg.id || idx} className={`flex gap-3 ${isUser ? "justify-end" : "justify-start"}`}>
                    {!isUser && (
                      <div className={`mt-1 flex size-7 shrink-0 items-center justify-center rounded-lg ${isTool ? "bg-amber-500/12 text-amber-300" : "bg-primary/12 text-primary"}`}>
                        {isTool ? <Wrench className="h-4 w-4" /> : <Bot className="h-4 w-4" />}
                      </div>
                    )}
                    <div className={`max-w-[82%] ${isUser ? "order-first" : ""}`}>
                      {!isUser && (
                        <div className="mb-1 flex items-center gap-2 text-[11px] font-semibold uppercase tracking-[0.12em] text-muted-foreground">
                          {isTool ? "Tool" : "Compass"}
                          {msg.pending && <Loader2 className="h-3 w-3 animate-spin" />}
                          {msg.model && <Badge variant="outline">{msg.model}</Badge>}
                        </div>
                      )}
                      <Card className={`rounded-lg px-4 py-3 ${isUser ? "bg-primary text-primary-foreground" : isTool ? "bg-amber-500/8 text-foreground" : "bg-card"}`}>
                        <p className="whitespace-pre-wrap text-sm leading-6">{msg.content}</p>
                      </Card>
                    </div>
                    {isUser && (
                      <div className="mt-1 flex size-7 shrink-0 items-center justify-center rounded-lg bg-muted text-muted-foreground">
                        <UserCircle className="h-4 w-4" />
                      </div>
                    )}
                  </div>
                );
              })
            )}
            <div ref={bottomRef} />
          </div>
        </ScrollArea>

        <div className="border-t border-border bg-background/95 shrink-0">
          <div className="mx-auto flex max-w-3xl items-center justify-between px-4 pt-3 text-xs text-muted-foreground md:px-0">
            <div className="flex items-center gap-2">
              {isLoading && (
                <>
                  <Loader2 className="h-3.5 w-3.5 animate-spin text-primary" />
                  <span>{streamStatus}</span>
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
          <ChatInput onSend={handleSend} isLoading={isLoading} />
        </div>
      </div>

      {showSandbox && (
        <aside className="hidden w-[520px] shrink-0 flex-col bg-card/70 p-3 lg:flex border-l border-border">
          <CodeSandbox language="typescript" />
        </aside>
      )}

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




