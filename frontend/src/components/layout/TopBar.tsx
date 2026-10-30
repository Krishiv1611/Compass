import type { ReactNode } from "react";
import { Compass, ChevronRight, Menu, Settings, UserCircle, Radio, WifiOff } from "lucide-react";
import { Sheet, SheetContent, SheetTrigger } from "@/components/ui/sheet";
import { Button } from "@/components/ui/button";
import type { AuthUser } from "@/types/auth";
import { useRunEvents } from "@/contexts/RunContext";

interface TopBarProps {
  title: string;
  isMobileOpen: boolean;
  setIsMobileOpen: (open: boolean) => void;
  isDesktopSidebarOpen: boolean;
  setIsDesktopSidebarOpen: (open: boolean) => void;
  SidebarContent: ReactNode;
  headerActions?: ReactNode;
  user: AuthUser | null;
  onOpenSettings: () => void;
}

export default function TopBar({
  title,
  isMobileOpen,
  setIsMobileOpen,
  isDesktopSidebarOpen,
  setIsDesktopSidebarOpen,
  SidebarContent,
  headerActions,
  user,
  onOpenSettings
}: TopBarProps) {
  let connection: "ready" | "connecting" | "streaming" | "offline" = "ready";
  let isRunActive = false;
  try {
    const runEvents = useRunEvents();
    connection = runEvents.connection;
    isRunActive = runEvents.isRunActive;
  } catch {
    // Graceful fallback when rendered outside RunProvider (e.g. isolated component unit tests)
  }

  return (
    <header className="glass-header absolute inset-x-0 top-0 z-10 flex h-[48px] shrink-0 items-center justify-between px-3 lg:px-4 border-b border-border bg-card/80 backdrop-blur-md">
      <div className="flex min-w-0 items-center gap-2.5">
        <Sheet open={isMobileOpen} onOpenChange={setIsMobileOpen}>
          <SheetTrigger aria-label="Open navigation" className="inline-flex size-8 items-center justify-center rounded-md hover:bg-muted md:hidden">
            <Menu className="h-4 w-4" />
          </SheetTrigger>
          <SheetContent side="left" title="Navigation" className="w-72 border-r-0 p-0" showCloseButton={false}>
            {SidebarContent}
          </SheetContent>
        </Sheet>
        <button
          onClick={() => setIsDesktopSidebarOpen(!isDesktopSidebarOpen)}
          aria-label={isDesktopSidebarOpen ? "Collapse sidebar" : "Expand sidebar"}
          className="hidden size-8 items-center justify-center rounded-md hover:bg-muted focus-visible:ring-1 focus-visible:ring-ring md:inline-flex text-muted-foreground hover:text-foreground transition-colors"
        >
          <Menu className="h-4 w-4" />
        </button>

        <div className="flex min-w-0 items-center gap-2 text-[13px] font-medium">
          <div className="flex size-6 items-center justify-center rounded-md bg-sky-500/10 text-sky-400 border border-sky-500/25">
            <Compass className="h-3.5 w-3.5" />
          </div>
          <span className="truncate text-foreground font-semibold">{title}</span>
          <ChevronRight className="h-3.5 w-3.5 text-muted-foreground/50 shrink-0" />
          <span className="hidden truncate text-muted-foreground sm:inline text-xs font-mono">Studio</span>
        </div>

        {/* Real-time Agent Status Halo */}
        <div className="hidden sm:flex items-center ml-2">
          {connection === "offline" ? (
            <span className="inline-flex items-center gap-1.5 px-2 py-0.5 rounded-full text-[10px] font-mono font-medium bg-destructive/10 text-destructive border border-destructive/20">
              <span className="h-1.5 w-1.5 rounded-full bg-destructive" />
              Offline
            </span>
          ) : isRunActive || connection === "streaming" ? (
            <span className="inline-flex items-center gap-1.5 px-2 py-0.5 rounded-full text-[10px] font-mono font-medium bg-sky-500/15 text-sky-400 border border-sky-500/30 shadow-[0_0_12px_rgba(56,189,248,0.2)]">
              <span className="h-1.5 w-1.5 rounded-full bg-sky-400 animate-ping" />
              Thinking
            </span>
          ) : (
            <span className="inline-flex items-center gap-1.5 px-2 py-0.5 rounded-full text-[10px] font-mono font-medium bg-emerald-500/10 text-emerald-400 border border-emerald-500/25">
              <span className="h-1.5 w-1.5 rounded-full bg-emerald-400" />
              Ready
            </span>
          )}
        </div>
      </div>

      <div className="flex items-center gap-2">
        <div className="flex items-center gap-1.5">
          {headerActions}
        </div>
        <div className="h-4 w-px bg-border/80 mx-1 hidden sm:block" />
        <Button variant="ghost" size="icon" className="h-8 w-8 text-muted-foreground hover:text-foreground hover:bg-muted" onClick={onOpenSettings} title="Settings" aria-label="Settings">
          {user ? <UserCircle className="h-4 w-4" /> : <Settings className="h-4 w-4" />}
        </Button>
      </div>
    </header>
  );
}
