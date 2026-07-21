import { useCallback, useEffect, useMemo, useState } from "react";
import { Outlet, useNavigate, useSearchParams } from "react-router-dom";
import {
  Bot,
  ChevronRight,
  Compass,
  FolderOpen,
  Loader2,
  Menu,
  MessageSquare,
  MoreHorizontal,
  Pencil,
  Plus,
  Settings,
  Terminal,
  Trash2,
  UserCircle,
  WifiOff,
  Sparkles,
  Plug,
  BrainCircuit,
  CheckSquare,
  History,
  Clock,
  FileDiff,
} from "lucide-react";
import { toast } from "react-toastify";
import { Button } from "@/components/ui/button";
import { Sheet, SheetContent, SheetTrigger } from "@/components/ui/sheet";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Badge } from "@/components/ui/badge";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import SettingsModal from "@/components/settings/SettingsModal";
import Modal from "@/components/ui/modal";
import { Input } from "@/components/ui/input";
import { API_BASE_URL, authApi, sessionsApi } from "@/api";

type SessionSummary = {
  id: string;
  title: string | null;
  updated_at: string;
  message_count: number;
  workspace_name?: string | null;
};

const sidebarEvent = (name: string, detail?: Record<string, unknown>) => {
  window.dispatchEvent(new CustomEvent(name, { detail }));
};

export default function AppLayout() {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const activeSessionId = searchParams.get("session");
  const [isMobileOpen, setIsMobileOpen] = useState(false);
  const [isDesktopSidebarOpen, setIsDesktopSidebarOpen] = useState(true);
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [settingsInitialTab, setSettingsInitialTab] = useState<string | undefined>(undefined);
  const [sessionToRename, setSessionToRename] = useState<SessionSummary | null>(null);
  const [sessionToDelete, setSessionToDelete] = useState<SessionSummary | null>(null);
  const [renameTitle, setRenameTitle] = useState("");
  const [sessions, setSessions] = useState<SessionSummary[]>([]);
  const [user, setUser] = useState<any | null>(null);
  const [isLoadingSessions, setIsLoadingSessions] = useState(false);
  const [sessionsPage, setSessionsPage] = useState(1);
  const [hasMoreSessions, setHasMoreSessions] = useState(false);

  const activeSession = useMemo(
    () => sessions.find((session) => session.id === activeSessionId),
    [activeSessionId, sessions]
  );

  const groupedSessions = useMemo(() => {
    const groups: Record<string, SessionSummary[]> = {};
    for (const session of sessions) {
      const groupName = session.workspace_name || "Playground";
      if (!groups[groupName]) {
        groups[groupName] = [];
      }
      groups[groupName].push(session);
    }
    return groups;
  }, [sessions]);

  const fetchUser = useCallback(async () => {
    const token = sessionStorage.getItem("compass_access_token");
    if (!token) {
      setUser(null);
      return;
    }
    try {
      const userData = await authApi.getMe();
      setUser(userData);
    } catch (error: any) {
      if (error?.response?.status === 401 || error?.response?.status === 403) {
        sessionStorage.removeItem("compass_access_token");
      }
      setUser(null);
    }
  }, []);

  const fetchSessions = useCallback(async () => {
    const token = sessionStorage.getItem("compass_access_token");
    if (!token) {
      setSessions([]);
      return;
    }
    setIsLoadingSessions(true);
    try {
      const data = await sessionsApi.listSessions(1, 20);
      setSessions(data);
      setSessionsPage(1);
      setHasMoreSessions(data.length === 20);
    } catch {
      setSessions([]);
    } finally {
      setIsLoadingSessions(false);
    }
  }, []);

  const loadMoreSessions = useCallback(async () => {
    const nextPage = sessionsPage + 1;
    setIsLoadingSessions(true);
    try {
      const data = await sessionsApi.listSessions(nextPage, 20);
      setSessions((prev) => [...prev, ...data]);
      setSessionsPage(nextPage);
      setHasMoreSessions(data.length === 20);
    } catch {
      // ignore
    } finally {
      setIsLoadingSessions(false);
    }
  }, [sessionsPage]);



  useEffect(() => {
    fetchUser();
    fetchSessions();
    const refresh = () => {
      fetchUser();
      fetchSessions();
    };
    window.addEventListener("auth-changed", refresh);
    window.addEventListener("sessions-refresh", fetchSessions);
    return () => {
      window.removeEventListener("auth-changed", refresh);
      window.removeEventListener("sessions-refresh", fetchSessions);
    };
  }, [fetchSessions, fetchUser]);

  const handleNewChat = () => {
    sidebarEvent("new-chat");
    navigate("/chat");
    setIsMobileOpen(false);
  };

  const executeRename = async (e?: React.FormEvent) => {
    e?.preventDefault();
    if (!sessionToRename || !renameTitle.trim()) return;
    try {
      await sessionsApi.renameSession(sessionToRename.id, renameTitle.trim());
      toast.success("Chat renamed");
      fetchSessions();
    } catch (error: any) {
      toast.error(error?.response?.data?.detail || "Could not rename chat");
    } finally {
      setSessionToRename(null);
      setRenameTitle("");
    }
  };

  const handleRename = (session: SessionSummary) => {
    setSessionToRename(session);
    setRenameTitle(session.title || "");
  };

  const executeDelete = async () => {
    if (!sessionToDelete) return;
    try {
      await sessionsApi.deleteSession(sessionToDelete.id);
      toast.success("Chat deleted");
      if (activeSessionId === sessionToDelete.id) {
        navigate("/chat");
        sidebarEvent("new-chat");
      }
      fetchSessions();
    } catch (error: any) {
      toast.error(error?.response?.data?.detail || "Could not delete chat");
    } finally {
      setSessionToDelete(null);
    }
  };

  const handleDelete = (session: SessionSummary) => {
    setSessionToDelete(session);
  };

  const handleOpenFolder = () => {
    sidebarEvent("open-folder-request");
  };

  const SidebarContent = (
    <aside className="flex h-full w-full flex-col bg-sidebar text-sidebar-foreground">
      <div className="flex h-14 items-center gap-3 border-b border-border px-4 bg-header">
        <div className="flex size-8 items-center justify-center bg-card text-primary border border-border">
          <Compass className="h-4 w-4" />
        </div>
        <div className="min-w-0">
          <div className="truncate text-sm font-semibold tracking-wide">Compass</div>
          <div className="text-[10px] text-muted-foreground uppercase tracking-widest">agentic workspace</div>
        </div>
      </div>

      <div className="space-y-3 border-b border-border p-4">
        <Button className="h-10 w-full justify-start rounded-none bg-muted hover:bg-secondary text-foreground border border-border transition-colors" onClick={handleNewChat}>
          <Plus className="h-4 w-4 mr-2 text-accent" /> New Chat
        </Button>
        <div className="grid grid-cols-1 gap-2">
          <Button variant="ghost" className="h-9 w-full justify-start rounded-none text-muted-foreground hover:text-foreground hover:bg-muted" onClick={handleOpenFolder}>
            <FolderOpen className="h-4 w-4 mr-2" /> Folder
          </Button>
          <Button variant="ghost" className="h-9 w-full justify-start rounded-none text-muted-foreground hover:text-foreground hover:bg-muted" onClick={() => { setSettingsInitialTab("skills"); setSettingsOpen(true); }}>
            <Sparkles className="h-4 w-4 mr-2" /> Skills
          </Button>
          <Button variant="ghost" className="h-9 w-full justify-start rounded-none text-muted-foreground hover:text-foreground hover:bg-muted" onClick={() => { setSettingsInitialTab("mcp"); setSettingsOpen(true); }}>
            <Plug className="h-4 w-4 mr-2" /> Connectors
          </Button>
        </div>
      </div>

      <ScrollArea className="flex-1">
        <div className="space-y-2 p-3">
          <div className="flex items-center justify-between px-1">
            <h4 className="text-[11px] font-semibold uppercase tracking-[0.12em] text-muted-foreground">Projects</h4>
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
                              setIsMobileOpen(false);
                            }}
                          >
                            <span className="truncate text-[13px]">{session.title || "Untitled task"}</span>
                          </button>
                          <DropdownMenu>
                            <DropdownMenuTrigger className="flex size-7 items-center justify-center rounded-md opacity-0 transition-opacity hover:bg-muted group-hover:opacity-100 aria-expanded:opacity-100">
                              <MoreHorizontal className="h-4 w-4" />
                            </DropdownMenuTrigger>
                            <DropdownMenuContent align="end" className="w-36">
                              <DropdownMenuItem onClick={() => handleRename(session)}>
                                <Pencil className="h-4 w-4" /> Rename
                              </DropdownMenuItem>
                              <DropdownMenuItem variant="destructive" onClick={() => handleDelete(session)}>
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
        <Button variant="ghost" className="h-10 w-full justify-start rounded-none text-muted-foreground hover:text-foreground hover:bg-muted" onClick={() => { setSettingsInitialTab(undefined); setSettingsOpen(true); }}>
          <Settings className="h-4 w-4 mr-2" /> Settings
        </Button>
      </div>
    </aside>
  );

  return (
    <div className="flex h-screen w-full overflow-hidden bg-background text-foreground selection:bg-primary/20 font-sans">
      {isDesktopSidebarOpen && (
        <div className="hidden md:block w-[280px] shrink-0 border-r border-border">
          {SidebarContent}
        </div>
      )}

      <div className="flex min-w-0 flex-1 flex-col relative z-0">
        <header className="glass-header absolute inset-x-0 top-0 z-10 flex h-14 shrink-0 items-center justify-between px-6">
          <div className="flex min-w-0 items-center gap-3">
            <Sheet open={isMobileOpen} onOpenChange={setIsMobileOpen}>
              <SheetTrigger className="inline-flex size-8 items-center justify-center rounded-none hover:bg-muted md:hidden">
                <Menu className="h-5 w-5" />
              </SheetTrigger>
              <SheetContent side="left" className="w-72 border-r-0 p-0" showCloseButton={false}>
                {SidebarContent}
              </SheetContent>
            </Sheet>
            <button
              onClick={() => setIsDesktopSidebarOpen(!isDesktopSidebarOpen)}
              aria-label={isDesktopSidebarOpen ? "Collapse sidebar" : "Expand sidebar"}
              className="hidden md:inline-flex size-8 items-center justify-center rounded-none hover:bg-muted transition-none focus-visible:ring-1 focus-visible:ring-ring"
            >
              <Menu className="h-4 w-4 text-muted-foreground" />
            </button>

            <div className="flex min-w-0 items-center gap-2 text-sm font-medium">
              <Bot className="h-4 w-4 text-primary opacity-80" />
              <span className="truncate">{activeSession?.title || "New Chat"}</span>
              <ChevronRight className="h-3.5 w-3.5 text-muted-foreground opacity-50" />
              <span className="hidden truncate text-muted-foreground opacity-50 sm:inline">Workspace</span>
            </div>
          </div>

          <div className="flex items-center gap-3">
            <div id="header-actions" className="flex items-center gap-2 mr-4"></div>
            <Button variant="ghost" size="icon" className="rounded-none hover:bg-muted" onClick={() => { setSettingsInitialTab(undefined); setSettingsOpen(true); }} title="Settings">
              {user ? <UserCircle className="h-4 w-4" /> : <Settings className="h-4 w-4" />}
            </Button>
          </div>
        </header>

        <main className="min-h-0 flex-1 overflow-hidden pt-14">
          <Outlet context={{ user, refreshUser: fetchUser }} />
        </main>
      </div>

      <SettingsModal
        open={settingsOpen}
        onOpenChange={(v) => { setSettingsOpen(v); if (!v) setSettingsInitialTab(undefined); }}
        user={user}
        sessionId={activeSessionId}
        initialTab={settingsInitialTab}
      />

      {/* Rename Dialog */}
      <Modal
        open={!!sessionToRename}
        onClose={() => setSessionToRename(null)}
        ariaLabel="Rename chat"
      >
        <h3 className="text-lg font-semibold mb-4">Rename Chat</h3>
        <form onSubmit={executeRename} className="flex flex-col gap-4">
          <Input
            autoFocus
            type="text"
            value={renameTitle}
            onChange={(e) => setRenameTitle(e.target.value)}
            className="h-9 focus-visible:ring-2 focus-visible:ring-primary/40"
          />
          <div className="flex justify-end gap-2">
            <Button type="button" variant="ghost" onClick={() => setSessionToRename(null)}>
              Cancel
            </Button>
            <Button type="submit">Rename</Button>
          </div>
        </form>
      </Modal>

      {/* Delete Dialog */}
      <Modal
        open={!!sessionToDelete}
        onClose={() => setSessionToDelete(null)}
        ariaLabel="Delete chat"
      >
        <h3 className="text-lg font-semibold mb-2">Delete Chat</h3>
        <p className="text-sm text-muted-foreground mb-6">
          Are you sure you want to delete &ldquo;
          {sessionToDelete?.title || "Untitled chat"}&rdquo;? This action
          cannot be undone.
        </p>
        <div className="flex justify-end gap-2">
          <Button variant="ghost" onClick={() => setSessionToDelete(null)}>
            Cancel
          </Button>
          <Button variant="destructive" onClick={executeDelete}>
            Delete
          </Button>
        </div>
      </Modal>
    </div>
  );
}

