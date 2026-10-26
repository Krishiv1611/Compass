import type { ReactNode } from "react";
import { Compass, ChevronRight, Menu, Settings, UserCircle } from "lucide-react";
import { Sheet, SheetContent, SheetTrigger } from "@/components/ui/sheet";
import { Button } from "@/components/ui/button";
import type { AuthUser } from "@/types/auth";

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
  return (
    <header className="glass-header absolute inset-x-0 top-0 z-10 flex h-[48px] shrink-0 items-center justify-between px-4 lg:px-6 border-b border-border">
      <div className="flex min-w-0 items-center gap-3">
        <Sheet open={isMobileOpen} onOpenChange={setIsMobileOpen}>
          <SheetTrigger aria-label="Open navigation" className="inline-flex size-8 items-center justify-center rounded-none hover:bg-muted md:hidden">
            <Menu className="h-5 w-5" />
          </SheetTrigger>
          <SheetContent side="left" title="Navigation" className="w-72 border-r-0 p-0" showCloseButton={false}>
            {SidebarContent}
          </SheetContent>
        </Sheet>
        <button
          onClick={() => setIsDesktopSidebarOpen(!isDesktopSidebarOpen)}
          aria-label={isDesktopSidebarOpen ? "Collapse sidebar" : "Expand sidebar"}
          className="hidden size-8 items-center justify-center rounded-md hover:bg-muted focus-visible:ring-1 focus-visible:ring-ring md:inline-flex"
        >
          <Menu className="h-4 w-4 text-muted-foreground" />
        </button>

        <div className="flex min-w-0 items-center gap-2 text-[13px] font-medium">
          <Compass className="h-4 w-4 text-sky-400" />
          <span className="truncate">{title}</span>
          <ChevronRight className="h-3.5 w-3.5 text-muted-foreground opacity-50" />
          <span className="hidden truncate text-muted-foreground opacity-50 sm:inline">Workspace</span>
        </div>
      </div>

      <div className="flex items-center gap-3">
        <div className="flex items-center gap-2 mr-2">
          {headerActions}
        </div>
        <Button variant="ghost" size="icon" className="h-8 w-8 hover:bg-muted" onClick={onOpenSettings} title="Settings" aria-label="Settings">
          {user ? <UserCircle className="h-4 w-4" /> : <Settings className="h-4 w-4" />}
        </Button>
      </div>
    </header>
  );
}
