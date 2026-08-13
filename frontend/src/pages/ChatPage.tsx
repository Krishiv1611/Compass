import { lazy, Suspense, useCallback, useEffect, useRef, useState } from "react";
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
import { chatApi, patchesApi, runsApi, sessionsApi, uploadsApi, workspaceApi } from "@/api";
import { useRunEvents } from "@/contexts/RunContext";
import { useWorkbench } from "@/contexts/WorkbenchContext";
import type { ChatMode } from "@/types/chat";
import type { InterruptKind, ResumePayload } from "@/types/protocol";
import type { TranscriptMessage } from "@/components/chat/MessageList";
import AppLayout from "@/components/layout/AppLayout";
import AgentPanel from "@/components/agent/AgentPanel";
import WorkbenchComposition from "@/components/workbench/WorkbenchComposition";
import WorkspaceLanding from "@/components/sandbox/WorkspaceLanding";
import CommandPalette from "@/components/workbench/CommandPalette";
import ContextDrawer from "@/components/workbench/ContextDrawer";
import RunTimeline from "@/components/chat/RunTimeline";
import GitHubPublishDialog from "@/components/github/GitHubPublishDialog";
import { Button } from "@/components/ui/button";
import { useRunController } from "@/hooks/useRunController";
import type { RunSocket } from "@/runtime/RunController";

const CenterWorkbench = lazy(() => import("@/components/workbench/CenterWorkbench"));

type ApprovalState = {
  content?: string;
  data?: {
    reason?: string;
    kind?: InterruptKind;
    prompt?: string;
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
    markFirstToken,
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
        if (state.activeWorkspaceId && state.dirtyWorkspaceIds.includes(state.activeWorkspaceId) && !window.confirm("Discard unsaved project changes?")) return;
        dispatch({ type: "setWorkspace", workspaceId: null });
        dispatch({ type: "setPendingPatchCount", count: 0 });
        return;
      }
      if (state.activeWorkspaceId && workspace.id !== state.activeWorkspaceId && state.dirtyWorkspaceIds.includes(state.activeWorkspaceId) && !window.confirm("Discard unsaved project changes?")) return;
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
  }, [dispatch, state.activeWorkspaceId, state.dirtyWorkspaceIds]);

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

  const appendAssistantText = useCallback((content: string) => {
    const id = assistantMessageId.current;
    if (!id || !content) return;
    setMessages((items) => items.map((item) =>
      item.id === id ? { ...item, content: `${item.content || ""}${content}`, pending: true } : item
    ));
  }, []);

  const runController = useRunController({
    createSocket: currentSessionId => chatApi.createWebSocket(currentSessionId) as unknown as RunSocket,
    cancelRun: (currentSessionId, runId) => runsApi.cancelRun(currentSessionId, runId),
    onOpen: () => setStreamStatus("Connected · waiting for first event"),
    onText: content => {
      markFirstToken();
      appendAssistantText(content);
      setStreamStatus("Writing response");
    },
    onEvent: (event, handle) => {
      const type = event.type || "status";
      addEvent(event);
      if (type === "status") setStreamStatus(String(event.content || "Working"));
      if (type === "approval_required" || type === "clarification_required") {
        setPendingApproval({
          content: event.content == null ? undefined : String(event.content),
          data: event.data as ApprovalState["data"],
        });
        setStreamStatus("Waiting for approval");
      }
      if (type === "workspace_patch") {
        setStreamStatus("Changes ready for review");
        void refreshWorkspace(handle.sessionId);
      }
      if (type === "error") {
        toast.error(String(event.content || "The run failed"));
        setStreamStatus("Run failed");
      }
      if (type === "done" || type === "error") {
        const id = assistantMessageId.current;
        setMessages((items) => items.map((item) => item.id === id ? { ...item, pending: false } : item));
        setIsLoading(false);
        setActiveSocket(null);
        finishRun();
        dispatch({ type: "sessionsChanged" });
      }
    },
    onError: () => {
      setOffline();
      setStreamStatus("Connection lost");
    },
    onClose: () => {
      const id = assistantMessageId.current;
      setActiveSocket(null);
      setIsLoading(false);
      setMessages((items) => items.map((item) => item.id === id ? { ...item, pending: false } : item));
    },
  });

  useEffect(() => () => runController.dispose(), [runController, sessionParam]);

  const handleSend = async (content: string, files: File[], mode: ChatMode, contextFiles: string[]) => {
    if (!content.trim() && files.length === 0 && contextFiles.length === 0) return;
    setIsLoading(true);
    setPendingApproval(null);
    setStreamStatus("Preparing task");
    try {
      const currentSessionId = await ensureSession(content.split(/\s+/).slice(0, 7).join(" ") || "New task");
      if (files.length) {
        setStreamStatus("Uploading context");
        const capabilities = await uploadsApi.getCapabilities(currentSessionId) as { max_upload_bytes: number; supported_extensions: string[] };
        for (const file of files) {
          const extension = `.${file.name.split(".").pop()?.toLowerCase() || ""}`;
          if (file.size > capabilities.max_upload_bytes) throw new Error(`${file.name} exceeds the upload size limit.`);
          if (!capabilities.supported_extensions.map(value => value.toLowerCase()).includes(extension)) throw new Error(`${file.name} is not a supported context file.`);
        }
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
      runController.start({
        sessionId: currentSessionId,
        content,
        mode,
        contextFiles,
        activeSkill: state.activeSkill,
      });
      setActiveSocket(runController.socket as WebSocket | null);
    } catch (error) {
      runController.dispose();
      setIsLoading(false);
      finishRun();
      toast.error(error instanceof Error ? error.message : "Could not start task");
      throw error;
    }
  };

  const handleResume = (payload: ResumePayload) => {
    if (!runController.resume(payload)) return;
    setPendingApproval(null);
    setStreamStatus("Resuming");
  };

  const handleCancel = async () => {
    try { await runController.cancel(); } catch { /* The socket may already be closing. */ }
    finishRun();
    setIsLoading(false);
    setStreamStatus("Stopped");
  };

  const centerPanel = state.activeWorkspaceId ? (
    <Suspense fallback={<div className="flex h-full items-center justify-center text-xs text-muted-foreground">Opening project workbench…</div>}>
      <CenterWorkbench activeWorkspaceId={state.activeWorkspaceId} />
    </Suspense>
  ) : (
    <WorkspaceLanding
      sessionId={sessionId}
      ensureSession={ensureSession}
      onWorkspaceReady={(workspaceId, name) => {
        if (state.activeWorkspaceId && workspaceId !== state.activeWorkspaceId && state.dirtyWorkspaceIds.includes(state.activeWorkspaceId) && !window.confirm("Discard unsaved project changes?")) return;
        dispatch({ type: "setWorkspace", workspaceId, projectName: name });
      }}
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
          handleResume={handleResume}
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
