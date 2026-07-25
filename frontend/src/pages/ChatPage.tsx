import { useCallback, useEffect, useRef, useState } from "react";
import { useSearchParams } from "react-router-dom";
import {
  Activity,
  Command,
  FileCode2,
  FolderTree,
  GitPullRequest,
  MessageSquare,
  PanelRight,
} from "lucide-react";
import { toast } from "react-toastify";
import { chatApi, patchesApi, sessionsApi, uploadsApi, workspaceApi } from "@/api";
import { useRunEvents } from "@/contexts/RunContext";
import { useWorkbench } from "@/contexts/WorkbenchContext";
import type { ChatMode } from "@/types/chat";
import type { RunEvent } from "@/types/run";
import type { TranscriptMessage } from "@/components/chat/MessageList";
import AppLayout from "@/components/layout/AppLayout";
import AgentPanel from "@/components/agent/AgentPanel";
import CenterWorkbench from "@/components/workbench/CenterWorkbench";
import WorkbenchComposition from "@/components/workbench/WorkbenchComposition";
import WorkspaceLanding from "@/components/sandbox/WorkspaceLanding";
import CommandPalette from "@/components/workbench/CommandPalette";
import ContextDrawer from "@/components/workbench/ContextDrawer";
import RunTimeline from "@/components/chat/RunTimeline";
import GitHubPublishDialog from "@/components/github/GitHubPublishDialog";
import { Button } from "@/components/ui/button";

type ApprovalState = {
  content?: string;
  data?: {
    reason?: string;
    plan?: string;
    tool_calls?: Array<{ id?: string; name?: string; args?: unknown; arguments?: unknown }>;
  };
};

export default function ChatPage() {
  const {
    state,
    dispatch,
    setContextFiles,
    reviewPatches,
  } = useWorkbench();
  const {
    addEvent,
    finishRun,
    isRunActive,
    setOffline,
    startRun,
  } = useRunEvents();
  const [searchParams, setSearchParams] = useSearchParams();
  const sessionParam = searchParams.get("session");
  const [sessionId, setSessionId] = useState<string | null>(sessionParam);
  const [messages, setMessages] = useState<TranscriptMessage[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [streamStatus, setStreamStatus] = useState("Ready");
  const [activeSocket, setActiveSocket] = useState<WebSocket | null>(null);
  const [pendingApproval, setPendingApproval] = useState<ApprovalState | null>(null);
  const socketRef = useRef<WebSocket | null>(null);
  const assistantMessageId = useRef<string | null>(null);

  const ensureSession = useCallback(async (title = "New task") => {
    if (sessionId) return sessionId;
    const session = await sessionsApi.createSession(title);
    setSessionId(session.id);
    setSearchParams({ session: session.id });
    dispatch({ type: "sessionsChanged" });
    return session.id as string;
  }, [dispatch, sessionId, setSearchParams]);

  const refreshWorkspace = useCallback(async (currentSessionId: string) => {
    try {
      const workspaces = await workspaceApi.listWorkspaces(currentSessionId);
      const workspace = workspaces[0];
      if (!workspace) {
        dispatch({ type: "setWorkspace", workspaceId: null });
        dispatch({ type: "setPendingPatchCount", count: 0 });
        return;
      }
      dispatch({ type: "setWorkspace", workspaceId: workspace.id, projectName: workspace.name });
      const patches = await patchesApi.getPatches(workspace.id);
      const pending = patches.reduce(
        (count, patch) => count + patch.changes.filter((change) => (change.status || patch.status) === "pending").length,
        0,
      );
      dispatch({ type: "setPendingPatchCount", count: pending });
    } catch {
      dispatch({ type: "setPendingPatchCount", count: 0 });
    }
  }, [dispatch]);

  useEffect(() => {
    let cancelled = false;
    const load = async () => {
      setSessionId(sessionParam);
      if (!sessionParam) {
        setMessages([]);
        dispatch({ type: "setWorkspace", workspaceId: null });
        return;
      }
      setStreamStatus("Loading task");
      try {
        const session = await sessionsApi.getSession(sessionParam);
        if (cancelled) return;
        setMessages(session.messages || []);
        await refreshWorkspace(sessionParam);
      } catch (error) {
        if (!cancelled) toast.error(error instanceof Error ? error.message : "Could not load task");
      } finally {
        if (!cancelled) setStreamStatus("Ready");
      }
    };
    void load();
    return () => { cancelled = true; };
  }, [dispatch, refreshWorkspace, sessionParam]);

  useEffect(() => {
    return () => socketRef.current?.close();
  }, []);

  const appendAssistantText = (content: string) => {
    const id = assistantMessageId.current;
    if (!id) return;
    setMessages((items) => items.map((item) =>
      item.id === id ? { ...item, content: `${item.content || ""}${content}`, pending: true } : item
    ));
  };

  const handleSend = async (content: string, files: File[], mode: ChatMode, contextFiles: string[]) => {
    if (!content.trim() && files.length === 0) return;
    setIsLoading(true);
    setPendingApproval(null);
    setStreamStatus("Preparing task");
    try {
      const currentSessionId = await ensureSession(content.split(/\s+/).slice(0, 7).join(" ") || "New task");
      if (files.length) {
        setStreamStatus("Uploading context");
        await Promise.all(files.map((file) => uploadsApi.uploadFile(currentSessionId, file)));
      }
      const userMessage: TranscriptMessage = {
        id: `user-${Date.now()}`,
        role: "user",
        content,
        created_at: new Date().toISOString(),
      };
      const assistantId = `assistant-${Date.now()}`;
      assistantMessageId.current = assistantId;
      setMessages((items) => [...items, userMessage, {
        id: assistantId,
        role: "assistant",
        content: "",
        created_at: new Date().toISOString(),
        pending: true,
      }]);
      startRun(currentSessionId);
      const socket = chatApi.createWebSocket(currentSessionId);
      socketRef.current = socket;
      setActiveSocket(socket);
      socket.onopen = () => {
        setStreamStatus("Connected · waiting for first event");
        socket.send(JSON.stringify({
          type: "message",
          content,
          mode,
          context_files: contextFiles,
        }));
      };
      socket.onmessage = (messageEvent) => {
        let event: Record<string, unknown>;
        try {
          event = JSON.parse(messageEvent.data) as Record<string, unknown>;
        } catch {
          return;
        }
        const type = String(event.type || "status");
        if (type === "token" || type === "assistant_delta") {
          appendAssistantText(String(event.content || ""));
          setStreamStatus("Writing response");
          return;
        }
        addEvent(event as unknown as RunEvent);
        if (type === "status") setStreamStatus(String(event.content || "Working"));
        if (type === "approval_required") {
          setPendingApproval({ data: event.data as ApprovalState["data"] });
          setStreamStatus("Waiting for approval");
        }
        if (type === "workspace_patch") {
          setStreamStatus("Changes ready for review");
          void refreshWorkspace(currentSessionId);
        }
        if (type === "error") {
          toast.error(String(event.content || "The run failed"));
          setStreamStatus("Run failed");
        }
        if (type === "done" || type === "error") {
          setMessages((items) => items.map((item) => item.id === assistantId ? { ...item, pending: false } : item));
          setIsLoading(false);
          setActiveSocket(null);
          finishRun();
          dispatch({ type: "sessionsChanged" });
          void refreshWorkspace(currentSessionId);
        }
      };
      socket.onerror = () => {
        setOffline();
        setStreamStatus("Connection lost");
      };
      socket.onclose = () => {
        socketRef.current = null;
        setActiveSocket(null);
        setIsLoading(false);
        setMessages((items) => items.map((item) => item.id === assistantId ? { ...item, pending: false } : item));
      };
    } catch (error) {
      setIsLoading(false);
      finishRun();
      toast.error(error instanceof Error ? error.message : "Could not start task");
    }
  };

  const handleApprovalAction = (action: string, feedback?: string) => {
    const socket = socketRef.current;
    if (!socket || socket.readyState !== WebSocket.OPEN) return;
    socket.send(JSON.stringify({ type: "resume", action, content: feedback || "" }));
    setPendingApproval(null);
    setStreamStatus("Resuming");
  };

  const handleCancel = () => {
    const socket = socketRef.current;
    if (socket?.readyState === WebSocket.OPEN) socket.send(JSON.stringify({ type: "cancel" }));
    socket?.close();
    finishRun();
    setIsLoading(false);
    setStreamStatus("Stopped");
  };

  const centerPanel = state.activeWorkspaceId ? (
    <CenterWorkbench activeWorkspaceId={state.activeWorkspaceId} />
  ) : (
    <WorkspaceLanding
      sessionId={sessionId}
      ensureSession={ensureSession}
      onWorkspaceReady={(workspaceId, name) => dispatch({ type: "setWorkspace", workspaceId, projectName: name })}
    />
  );

  const rightPanel = (
    <div className="flex h-full min-h-0 flex-col">
      <div className={`${state.mobileDestination === "activity" ? "hidden" : "min-h-0 flex-1"} lg:block lg:min-h-0 lg:flex-1`}>
        <AgentPanel
          messages={messages}
          isLoading={isLoading}
          streamStatus={streamStatus}
          activeSocket={activeSocket}
          pendingApproval={pendingApproval}
          pendingPatchCount={state.pendingPatchCount}
          activeWorkspaceId={state.activeWorkspaceId}
          handleSend={handleSend}
          handleApprovalAction={handleApprovalAction}
          handleCancel={handleCancel}
          reviewPatches={reviewPatches}
          onContextChange={setContextFiles}
        />
      </div>
      <div className={`${state.mobileDestination === "activity" ? "flex min-h-0 flex-1 flex-col" : "hidden"} lg:block lg:flex-none`}>
        <RunTimeline sessionId={sessionId} showEmpty={state.mobileDestination === "activity"} />
      </div>
    </div>
  );

  const headerActions = (
    <>
      <Button variant="ghost" size="icon-sm" onClick={() => dispatch({ type: "setCommandPalette", open: true })} aria-label="Open command palette" title="Command palette"><Command className="h-4 w-4" /></Button>
      <Button variant="ghost" size="icon-sm" onClick={() => dispatch({ type: "setContextDrawer", open: true })} aria-label="Inspect context" title="Context"><PanelRight className="h-4 w-4" /></Button>
      <Button variant="ghost" size="sm" onClick={() => dispatch({ type: "setPublish", open: true })} disabled={!state.activeWorkspaceId}><GitPullRequest className="h-4 w-4" /> Publish</Button>
    </>
  );

  return (
    <AppLayout headerActions={headerActions}>
      <div className="relative flex min-h-0 flex-1 flex-col pb-12 lg:pb-0">
        <WorkbenchComposition
          centerPanel={centerPanel}
          rightPanel={rightPanel}
          showRightPanel={state.rightPanelOpen}
          mobileDestination={state.mobileDestination}
        />
        <nav className="fixed inset-x-0 bottom-6 z-[60] grid h-12 grid-cols-5 border-t border-border bg-background pb-[env(safe-area-inset-bottom)] lg:hidden" aria-label="Workbench destinations">
          <MobileNavButton icon={MessageSquare} label="Agent" active={state.mobileDestination === "agent"} onClick={() => dispatch({ type: "setMobileDestination", destination: "agent" })} />
          <MobileNavButton icon={FolderTree} label="Files" active={state.mobileDestination === "files"} onClick={() => dispatch({ type: "setMobileDestination", destination: "files" })} />
          <MobileNavButton icon={FileCode2} label="Editor" active={state.mobileDestination === "editor"} onClick={() => { dispatch({ type: "setCenterTab", tab: "editor" }); dispatch({ type: "setMobileDestination", destination: "editor" }); }} />
          <MobileNavButton icon={GitPullRequest} label="Changes" active={state.mobileDestination === "changes"} badge={state.pendingPatchCount} onClick={() => { dispatch({ type: "setCenterTab", tab: "changes" }); dispatch({ type: "setMobileDestination", destination: "changes" }); }} />
          <MobileNavButton icon={Activity} label="Activity" active={state.mobileDestination === "activity"} live={isRunActive} onClick={() => dispatch({ type: "setMobileDestination", destination: "activity" })} />
        </nav>
      </div>
      <CommandPalette open={state.commandPaletteOpen} onOpenChange={(open) => dispatch({ type: "setCommandPalette", open })} onContext={() => dispatch({ type: "setContextDrawer", open: true })} workspaceId={state.activeWorkspaceId} />
      <ContextDrawer open={state.contextDrawerOpen} onOpenChange={(open) => dispatch({ type: "setContextDrawer", open })} workspaceId={state.activeWorkspaceId} sessionId={sessionId} selectedFiles={state.selectedContextFiles} />
      {state.activeWorkspaceId && <GitHubPublishDialog open={state.publishOpen} onClose={() => dispatch({ type: "setPublish", open: false })} workspaceId={state.activeWorkspaceId} />}
    </AppLayout>
  );
}

function MobileNavButton({
  icon: Icon,
  label,
  active,
  badge,
  live,
  onClick,
}: {
  icon: React.ComponentType<{ className?: string }>;
  label: string;
  active: boolean;
  badge?: number;
  live?: boolean;
  onClick: () => void;
}) {
  return (
    <button type="button" onClick={onClick} aria-current={active ? "page" : undefined} className={`relative flex min-h-12 flex-col items-center justify-center gap-0.5 text-xs ${active ? "text-primary" : "text-muted-foreground"}`}>
      <Icon className="h-4 w-4" /><span>{label}</span>
      {!!badge && <span className="absolute right-3 top-1 min-w-4 rounded-full bg-warning px-1 font-mono text-xs text-white">{badge}</span>}
      {live && <span className="absolute right-4 top-1 h-2 w-2 rounded-full bg-success" />}
    </button>
  );
}
