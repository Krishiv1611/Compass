import { useState } from "react";
import { Compass, Copy, FolderOpen, Loader2, MoreHorizontal, Pencil, Plus, Sparkles, Plug, Settings, Trash2 } from "lucide-react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { motion, AnimatePresence } from "framer-motion";
import { Button } from "@/components/ui/button";
import { ScrollArea } from "@/components/ui/scroll-area";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import Modal from "@/components/ui/modal";
import { Input } from "@/components/ui/input";
import type { SessionSummary, UseSessionsResult } from "@/hooks/useSessions";
import { useWorkbench } from "@/contexts/WorkbenchContext";
import { sessionsApi } from "@/api";
import { toast } from "react-toastify";

interface ProjectRailProps {
  sessionState: UseSessionsResult;
  onOpenSettings: (tab?: string) => void;
  onCloseMobile?: () => void;
}

export default function ProjectRail({ sessionState, onOpenSettings, onCloseMobile }: ProjectRailProps) {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const activeSessionId = searchParams.get("session");
  const { startNewTask } = useWorkbench();
  const { sessions, isLoadingSessions, hasMoreSessions, loadMoreSessions, renameSession, deleteSession } = sessionState;

  const [sessionToRename, setSessionToRename] = useState<SessionSummary | null>(null);
  const [sessionToDelete, setSessionToDelete] = useState<SessionSummary | null>(null);
  const [renameTitle, setRenameTitle] = useState("");
  const [forkingSessionId, setForkingSessionId] = useState<string | null>(null);

  const handleNewChat = () => {
    startNewTask();
    navigate("/chat");
    onCloseMobile?.();
  };

  const executeRename = async (e?: React.FormEvent) => {
    e?.preventDefault();
    if (!sessionToRename || !renameTitle.trim()) return;
    try {
      await renameSession(sessionToRename.id, renameTitle.trim());
      setSessionToRename(null);
      setRenameTitle("");
    } catch {
      // The hook reports the failure; keep the dialog open so the title can be corrected.
    }
  };

  const executeDelete = async () => {
    if (!sessionToDelete) return;
    try {
      await deleteSession(sessionToDelete.id);
      if (activeSessionId === sessionToDelete.id) {
        navigate("/chat");
        startNewTask();
      }
      setSessionToDelete(null);
    } catch {
      // The hook reports the failure; retain the confirmation dialog for retry/cancel.
    }
  };

  const executeFork = async (session: SessionSummary) => {
    setForkingSessionId(session.id);
    try {
      const forked = await sessionsApi.forkSession(session.id);
      startNewTask();
      navigate(`/chat?session=${forked.id}`);
      onCloseMobile?.();
      toast.success("Task forked into an isolated workspace");
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Could not fork task");
    } finally {
      setForkingSessionId(null);
    }
  };

  const groupedSessions = sessions.reduce((acc, session) => {
    const groupName = session.workspace_name || "Playground";
    if (!acc[groupName]) acc[groupName] = [];
    acc[groupName].push(session);
    return acc;
  }, {} as Record<string, SessionSummary[]>);

  return (
    <aside className="flex h-full w-full flex-col bg-[#080A0E] text-sidebar-foreground border-r border-border">
      <div className="flex h-12 items-center gap-2.5 border-b border-border px-3 bg-header/60">
        <div className="flex size-7 items-center justify-center rounded-md border border-primary/30 bg-primary/10 text-primary shadow-[0_0_10px_rgba(56,189,248,0.2)]">
          <Compass className="h-4 w-4" />
        </div>
        <div className="min-w-0">
          <div className="truncate text-xs font-semibold text-foreground tracking-tight">Compass Studio</div>
          <div className="text-[10px] text-muted-foreground font-mono">Autonomous Workspace</div>
        </div>
      </div>

      <div className="space-y-2 border-b border-border p-3">
        <Button
          className="group relative h-8 w-full justify-start text-xs font-medium bg-primary/15 text-primary hover:bg-primary/25 border border-primary/30 transition-all shadow-[0_0_12px_rgba(56,189,248,0.1)]"
          onClick={handleNewChat}
        >
          <Plus className="mr-2 h-3.5 w-3.5 transition-transform group-hover:rotate-90" />
          <span>New task</span>
        </Button>
        <div className="grid grid-cols-2 gap-1.5 pt-1">
          <Button
            variant="ghost"
            size="sm"
            className="h-7 w-full justify-start text-[11px] text-muted-foreground hover:text-foreground hover:bg-muted font-normal px-2"
            onClick={() => onOpenSettings("skills")}
          >
            <Sparkles className="h-3 w-3 mr-1.5 text-amber-400" />
            <span>Skills</span>
          </Button>
          <Button
            variant="ghost"
            size="sm"
            className="h-7 w-full justify-start text-[11px] text-muted-foreground hover:text-foreground hover:bg-muted font-normal px-2"
            onClick={() => onOpenSettings("mcp")}
          >
            <Plug className="h-3 w-3 mr-1.5 text-sky-400" />
            <span>Connectors</span>
          </Button>
        </div>
      </div>

      <ScrollArea className="flex-1">
        <div className="space-y-2 p-3">
          <div className="flex items-center justify-between px-1">
            <h4 className="text-[11px] font-mono uppercase tracking-wider text-muted-foreground font-semibold">Projects</h4>
            {isLoadingSessions && <Loader2 className="h-3 w-3 animate-spin text-sky-400" />}
          </div>

          {sessions.length === 0 && !isLoadingSessions ? (
            <div className="rounded-lg border border-dashed border-border/80 p-3 text-xs leading-5 text-muted-foreground">
              Your tasks will appear here after the first message.
            </div>
          ) : (
            <div className="space-y-4">
              {Object.entries(groupedSessions).map(([groupName, groupSessions]) => (
                <div key={groupName} className="space-y-0.5">
                  <div className="flex items-center gap-1.5 px-1 py-1 text-xs font-semibold text-slate-300">
                    <FolderOpen className="h-3.5 w-3.5 text-sky-400/80" />
                    <span className="truncate">{groupName}</span>
                  </div>
                  {groupSessions.length === 0 ? (
                    <div className="pl-6 text-[11px] text-muted-foreground py-1">No tasks</div>
                  ) : (
                    groupSessions.map((session) => {
                      const active = session.id === activeSessionId;
                      return (
                        <div
                          key={session.id}
                          className={`group relative flex items-center gap-1 rounded-md px-2 py-1.5 ml-1 transition-all border ${
                            active
                              ? "bg-sky-500/10 border-sky-500/30 text-foreground font-medium shadow-[0_0_12px_rgba(56,189,248,0.1)]"
                              : "border-transparent text-muted-foreground hover:bg-muted/60 hover:text-foreground"
                          }`}
                        >
                          <button
                            className="flex min-w-0 flex-1 items-center gap-2 text-left pl-1"
                            onClick={() => {
                              navigate(`/chat?session=${session.id}`);
                              onCloseMobile?.();
                            }}
                          >
                            <span className="truncate text-[12px]">{session.title || "Untitled task"}</span>
                          </button>
                          <DropdownMenu>
                            <DropdownMenuTrigger
                              aria-label={`Task actions for ${session.title || "Untitled task"}`}
                              className="flex size-6 items-center justify-center rounded-md opacity-0 transition-opacity hover:bg-muted group-hover:opacity-100 aria-expanded:opacity-100 text-muted-foreground hover:text-foreground"
                            >
                              <MoreHorizontal className="h-3.5 w-3.5" />
                            </DropdownMenuTrigger>
                            <DropdownMenuContent align="end" className="w-36">
                              <DropdownMenuItem
                                disabled={forkingSessionId === session.id}
                                onClick={() => void executeFork(session)}
                              >
                                {forkingSessionId === session.id ? (
                                  <Loader2 className="h-3.5 w-3.5 animate-spin" />
                                ) : (
                                  <Copy className="h-3.5 w-3.5" />
                                )}
                                Fork task
                              </DropdownMenuItem>
                              <DropdownMenuItem onClick={() => { setSessionToRename(session); setRenameTitle(session.title || ""); }}>
                                <Pencil className="h-3.5 w-3.5" /> Rename
                              </DropdownMenuItem>
                              <DropdownMenuItem variant="destructive" onClick={() => setSessionToDelete(session)}>
                                <Trash2 className="h-3.5 w-3.5" /> Delete
                              </DropdownMenuItem>
                            </DropdownMenuContent>
                          </DropdownMenu>
                        </div>
                      );
                    })
                  )}
                </div>
              ))}
              {hasMoreSessions && (
                <button
                  onClick={loadMoreSessions}
                  disabled={isLoadingSessions}
                  className="w-full rounded-lg border border-dashed border-border px-2 py-1.5 text-xs text-muted-foreground transition-colors hover:border-primary/30 hover:text-foreground flex items-center justify-center gap-1"
                >
                  {isLoadingSessions ? (
                    <Loader2 className="h-3 w-3 animate-spin" />
                  ) : (
                    "Load more"
                  )}
                </button>
              )}
            </div>
          )}
        </div>
      </ScrollArea>

      <div className="border-t border-border p-4">
        <Button variant="ghost" className="h-9 w-full justify-start text-muted-foreground hover:text-foreground hover:bg-muted" onClick={() => onOpenSettings(undefined)}>
          <Settings className="h-4 w-4 mr-2" /> Settings
        </Button>
      </div>

      <Modal open={!!sessionToRename} onClose={() => setSessionToRename(null)} title="Rename chat" maxWidth="max-w-md">
        <form onSubmit={executeRename} className="p-5">
          <Input autoFocus value={renameTitle} onChange={(e) => setRenameTitle(e.target.value)} placeholder="Chat title" />
          <div className="mt-5 flex justify-end gap-3">
            <Button type="button" variant="outline" onClick={() => setSessionToRename(null)}>Cancel</Button>
            <Button type="submit">Rename</Button>
          </div>
        </form>
      </Modal>

      <Modal open={!!sessionToDelete} onClose={() => setSessionToDelete(null)} title="Delete chat" maxWidth="max-w-md">
        <div className="p-5">
          <p className="text-sm text-muted-foreground">Are you sure you want to delete this chat? This action cannot be undone.</p>
          <div className="mt-5 flex justify-end gap-3">
            <Button variant="outline" onClick={() => setSessionToDelete(null)}>Cancel</Button>
            <Button variant="destructive" onClick={executeDelete}>Delete</Button>
          </div>
        </div>
      </Modal>
    </aside>
  );
}
