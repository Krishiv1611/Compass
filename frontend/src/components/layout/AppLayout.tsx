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
import SettingsDrawer from "@/components/settings/SettingsDrawer";
import Modal from "@/components/ui/modal";
import { Input } from "@/components/ui/input";
import { API_BASE_URL, authApi, sessionsApi } from "@/api";

type SessionSummary = {
  id: string;
  title: string | null;
  updated_at: string;
  message_count: number;
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
  const [sessionToRename, setSessionToRename] = useState<SessionSummary | null>(null);
  const [sessionToDelete, setSessionToDelete] = useState<SessionSummary | null>(null);
  const [renameTitle, setRenameTitle] = useState("");
  const [sessions, setSessions] = useState<SessionSummary[]>([]);
  const [user, setUser] = useState<any | null>(null);
  const [isLoadingSessions, setIsLoadingSessions] = useState(false);
  const [sessionsPage, setSessionsPage] = useState(1);
  const [hasMoreSessions, setHasMoreSessions] = useState(false);
  const [backendOffline, setBackendOffline] = useState(false);

  const activeSession = useMemo(
    () => sessions.find((session) => session.id === activeSessionId),
    [activeSessionId, sessions]
  );

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
    let active = true;

    const checkHealth = async () => {
      try {
        const response = await fetch(`${API_BASE_URL}/health`, { cache: "no-store" });
        if (active) setBackendOffline(!response.ok);
      } catch {
        if (active) setBackendOffline(true);
      }
    };

    checkHealth();
    return () => {
      active = false;
    };
  }, []);

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
      <div className="flex h-14 items-center gap-3 border-b border-border px-4">
        <div className="flex size-8 items-center justify-center rounded-lg bg-primary text-primary-foreground">
          <Compass className="h-4 w-4" />
        </div>
        <div className="min-w-0">
          <div className="truncate text-sm font-semibold">Compass</div>
          <div className="text-[11px] text-muted-foreground">agentic workspace</div>
        </div>
      </div>

      <div className="space-y-2 border-b border-border p-3">
        <Button className="h-9 w-full justify-start" onClick={handleNewChat}>
          <Plus className="h-4 w-4" /> New Chat
        </Button>
        <div className="grid grid-cols-1 gap-2">
          <Button variant="outline" className="h-9 w-full justify-start" onClick={handleOpenFolder}>
            <FolderOpen className="h-4 w-4" /> Folder
          </Button>
        </div>
      </div>

      <ScrollArea className="flex-1">
        <div className="space-y-2 p-3">
          <div className="flex items-center justify-between px-1">
            <h4 className="text-[11px] font-semibold uppercase tracking-[0.12em] text-muted-foreground">Chats</h4>
            {isLoadingSessions && <Loader2 className="h-3.5 w-3.5 animate-spin text-muted-foreground" />}
          </div>

          {sessions.length === 0 && !isLoadingSessions ? (
            <div className="rounded-lg border border-dashed border-border p-3 text-xs leading-5 text-muted-foreground">
              Your chats will appear here after the first message.
            </div>
          ) : (
            <div className="space-y-1">
              {sessions.map((session) => {
                const active = session.id === activeSessionId;
                return (
                  <div
                    key={session.id}
                    className={`group flex items-center gap-1 rounded-lg border px-2 py-1.5 transition-colors ${
                      active
                        ? "border-l-2 border-l-primary border-primary/30 bg-primary/8 text-foreground"
                        : "border-transparent text-muted-foreground hover:border-border hover:bg-muted/50 hover:text-foreground"
                    }`}
                  >
                    <button
                      className="flex min-w-0 flex-1 items-center gap-2 text-left"
                      onClick={() => {
                        navigate(`/chat?session=${session.id}`);
                        setIsMobileOpen(false);
                      }}
                    >
                      <MessageSquare className="h-3.5 w-3.5 shrink-0" />
                      <span className="truncate text-sm">{session.title || "Untitled chat"}</span>
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
              })}
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

      <div className="border-t border-border p-3">
        <Button variant="ghost" className="h-9 w-full justify-start" onClick={() => setSettingsOpen(true)}>
          <Settings className="h-4 w-4" /> Settings
        </Button>
      </div>
    </aside>
  );

  return (
    <div className="flex h-screen w-full overflow-hidden bg-background text-foreground selection:bg-primary/20">
      {isDesktopSidebarOpen && (
        <div className="hidden md:block w-[280px] shrink-0 border-r border-border">
          {SidebarContent}
        </div>
      )}

      <div className="flex min-w-0 flex-1 flex-col">
        <header className="glass-header flex h-14 shrink-0 items-center justify-between px-3">
          <div className="flex min-w-0 items-center gap-2">
            <Sheet open={isMobileOpen} onOpenChange={setIsMobileOpen}>
              <SheetTrigger className="inline-flex size-9 items-center justify-center rounded-lg hover:bg-muted md:hidden">
                <Menu className="h-5 w-5" />
              </SheetTrigger>
              <SheetContent side="left" className="w-72 border-r-0 p-0" showCloseButton={false}>
                {SidebarContent}
              </SheetContent>
            </Sheet>
            <button
              onClick={() => setIsDesktopSidebarOpen(!isDesktopSidebarOpen)}
              aria-label={isDesktopSidebarOpen ? "Collapse sidebar" : "Expand sidebar"}
              className="hidden md:inline-flex size-9 items-center justify-center rounded-lg hover:bg-muted transition-colors duration-150 focus-visible:ring-2 focus-visible:ring-primary/40"
            >
              <Menu className="h-5 w-5" />
            </button>

            <div className="flex min-w-0 items-center gap-2 text-sm">
              <Bot className="h-4 w-4 text-primary" />
              <span className="truncate font-medium">{activeSession?.title || "New Chat"}</span>
              <ChevronRight className="h-3.5 w-3.5 text-muted-foreground" />
              <span className="hidden truncate text-muted-foreground sm:inline">Workspace</span>
            </div>
          </div>

          <div className="flex items-center gap-2">
            {backendOffline && (
              <span
                className="inline-flex items-center gap-1 rounded-full border border-red-500/30 bg-red-500/10 px-2 py-1 text-[11px] font-medium text-red-500"
                title="Backend health check failed"
              >
                <WifiOff className="h-3 w-3" /> Offline
              </span>
            )}
            <Badge variant="outline" className="hidden gap-1 text-muted-foreground lg:inline-flex">
              <Terminal className="h-3 w-3" /> tools enabled
            </Badge>
            <Button variant="ghost" size="icon" onClick={() => setSettingsOpen(true)} title="Settings">
              {user ? <UserCircle className="h-4 w-4" /> : <Settings className="h-4 w-4" />}
            </Button>
          </div>
        </header>

        <main className="min-h-0 flex-1 overflow-hidden">
          <Outlet context={{ user, refreshUser: fetchUser }} />
        </main>
      </div>

      <SettingsDrawer
        open={settingsOpen}
        onOpenChange={setSettingsOpen}
        user={user}
        sessionId={activeSessionId}
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

