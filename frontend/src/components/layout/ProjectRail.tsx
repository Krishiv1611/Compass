import { useState } from "react";
import { Compass, Copy, FolderOpen, Loader2, MoreHorizontal, Pencil, Plus, Sparkles, Plug, Settings, Trash2 } from "lucide-react";
import { useNavigate, useSearchParams } from "react-router-dom";
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
import { useSessions, type SessionSummary } from "@/hooks/useSessions";
import { useWorkbench } from "@/contexts/WorkbenchContext";
import { sessionsApi } from "@/api";
import { toast } from "react-toastify";

interface ProjectRailProps {
  onOpenSettings: (tab?: string) => void;
  onCloseMobile?: () => void;
}

export default function ProjectRail({ onOpenSettings, onCloseMobile }: ProjectRailProps) {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const activeSessionId = searchParams.get("session");
  const { startNewTask } = useWorkbench();
  const {
    sessions,
    isLoadingSessions,
    hasMoreSessions,
    loadMoreSessions,
    renameSession,
    deleteSession
  } = useSessions(activeSessionId);

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
    await renameSession(sessionToRename.id, renameTitle.trim());
    setSessionToRename(null);
    setRenameTitle("");
  };

  const executeDelete = async () => {
    if (!sessionToDelete) return;
    await deleteSession(sessionToDelete.id);
    if (activeSessionId === sessionToDelete.id) {
      navigate("/chat");
      startNewTask();
    }
    setSessionToDelete(null);
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
    <aside className="flex h-full w-full flex-col bg-sidebar text-sidebar-foreground">
      <div className="flex h-14 items-center gap-3 border-b border-border px-4 bg-header">
        <div className="flex size-8 items-center justify-center rounded-md border border-primary/25 bg-primary/10 text-primary">
          <Compass className="h-4 w-4" />
        </div>
        <div className="min-w-0">
          <div className="truncate text-sm font-semibold">Compass</div>
          <div className="text-xs text-muted-foreground">Coding workspace</div>
        </div>
      </div>

      <div className="space-y-3 border-b border-border p-4">
        <Button className="h-9 w-full justify-start" onClick={handleNewChat}>
          <Plus className="mr-2 h-4 w-4" /> New task
        </Button>
        <div className="grid grid-cols-1 gap-2">
          <Button variant="ghost" className="h-9 w-full justify-start text-muted-foreground hover:text-foreground hover:bg-muted" onClick={() => onOpenSettings("skills")}>
            <Sparkles className="h-4 w-4 mr-2" /> Skills
          </Button>
          <Button variant="ghost" className="h-9 w-full justify-start text-muted-foreground hover:text-foreground hover:bg-muted" onClick={() => onOpenSettings("mcp")}>
            <Plug className="h-4 w-4 mr-2" /> Connectors
          </Button>
        </div>
      </div>

      <ScrollArea className="flex-1">
        <div className="space-y-2 p-3">
          <div className="flex items-center justify-between px-1">
            <h4 className="text-xs font-semibold text-muted-foreground">Projects</h4>
            {isLoadingSessions && <Loader2 className="h-3.5 w-3.5 animate-spin text-muted-foreground" />}
          </div>

          {sessions.length === 0 && !isLoadingSessions ? (
            <div className="rounded-lg border border-dashed border-border p-3 text-xs leading-5 text-muted-foreground">
              Your tasks will appear here after the first message.
            </div>
          ) : (
            <div className="space-y-4">
              {Object.entries(groupedSessions).map(([groupName, groupSessions]) => (
                <div key={groupName} className="space-y-0.5">
                  <div className="flex items-center gap-2 px-1 py-1.5 text-sm font-semibold text-foreground">
                    <FolderOpen className="h-4 w-4 text-muted-foreground" />
                    <span className="truncate">{groupName}</span>
                  </div>
                  {groupSessions.length === 0 ? (
                    <div className="pl-7 text-xs text-muted-foreground py-1">No tasks</div>
                  ) : (
                    groupSessions.map((session) => {
                      const active = session.id === activeSessionId;
                      return (
                        <div
                          key={session.id}
                          className={`group flex items-center gap-1 rounded-md px-2 py-1.5 ml-2 transition-none border-l-2 ${
                            active
                              ? "bg-muted border-accent text-foreground font-medium"
                              : "border-transparent text-muted-foreground hover:bg-secondary hover:text-foreground"
                          }`}
                        >
                          <button
                            className="flex min-w-0 flex-1 items-center gap-2 text-left pl-1"
                            onClick={() => {
                              navigate(`/chat?session=${session.id}`);
                              onCloseMobile?.();
                            }}
                          >
                            <span className="truncate text-[13px]">{session.title || "Untitled task"}</span>
                          </button>
                          <DropdownMenu>
                            <DropdownMenuTrigger className="flex size-7 items-center justify-center rounded-md opacity-0 transition-opacity hover:bg-muted group-hover:opacity-100 aria-expanded:opacity-100">
                              <MoreHorizontal className="h-4 w-4" />
                            </DropdownMenuTrigger>
                            <DropdownMenuContent align="end" className="w-36">
                              <DropdownMenuItem
                                disabled={forkingSessionId === session.id}
                                onClick={() => void executeFork(session)}
                              >
                                {forkingSessionId === session.id ? (
                                  <Loader2 className="h-4 w-4 animate-spin" />
                                ) : (
                                  <Copy className="h-4 w-4" />
                                )}
                                Fork task
                              </DropdownMenuItem>
                              <DropdownMenuItem onClick={() => { setSessionToRename(session); setRenameTitle(session.title || ""); }}>
                                <Pencil className="h-4 w-4" /> Rename
                              </DropdownMenuItem>
                              <DropdownMenuItem variant="destructive" onClick={() => setSessionToDelete(session)}>
                                <Trash2 className="h-4 w-4" /> Delete
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
