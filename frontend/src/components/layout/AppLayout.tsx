import { useEffect, useState, type ReactNode } from "react";
import { useSearchParams } from "react-router-dom";
import SettingsModal from "@/components/settings/SettingsModal";
import TopBar from "./TopBar";
import ProjectRail from "./ProjectRail";
import StatusBar from "./StatusBar";
import { useAuth } from "@/contexts/AuthContext";
import { useSessions } from "@/hooks/useSessions";
import { useWorkbench } from "@/contexts/WorkbenchContext";

interface AppLayoutProps {
  children: ReactNode;
  headerActions?: ReactNode;
}

export default function AppLayout({ children, headerActions }: AppLayoutProps) {
  const [searchParams] = useSearchParams();
  const activeSessionId = searchParams.get("session");
  const [isMobileOpen, setIsMobileOpen] = useState(false);
  const [isDesktopSidebarOpen, setIsDesktopSidebarOpen] = useState(true);
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [settingsInitialTab, setSettingsInitialTab] = useState<string | undefined>(undefined);

  const { user } = useAuth();
  const { state } = useWorkbench();
  const sessionState = useSessions(activeSessionId);
  const { sessions } = sessionState;

  const activeSession = sessions.find((s) => s.id === activeSessionId);

  const handleOpenSettings = (tab?: string) => {
    setSettingsInitialTab(tab);
    setSettingsOpen(true);
  };

  useEffect(() => {
    if (!state.settingsRequest.version) return;
    setSettingsInitialTab(state.settingsRequest.section);
    setSettingsOpen(true);
  }, [state.settingsRequest]);

  const sidebarContent = (
    <ProjectRail
      sessionState={sessionState}
      onOpenSettings={handleOpenSettings}
      onCloseMobile={() => setIsMobileOpen(false)}
    />
  );

  return (
    <div className="flex h-screen w-full overflow-hidden bg-background text-foreground selection:bg-primary/20 font-sans flex-col">
      <TopBar
        title={activeSession?.title || "New Chat"}
        isMobileOpen={isMobileOpen}
        setIsMobileOpen={setIsMobileOpen}
        isDesktopSidebarOpen={isDesktopSidebarOpen}
        setIsDesktopSidebarOpen={setIsDesktopSidebarOpen}
        SidebarContent={sidebarContent}
        headerActions={headerActions}
        user={user}
        onOpenSettings={() => handleOpenSettings(undefined)}
      />

      <div className="flex min-w-0 flex-1 relative z-0 mt-[48px] overflow-hidden">
        {isDesktopSidebarOpen && (
          <div className="hidden w-[232px] shrink-0 border-r border-border md:block">
            {sidebarContent}
          </div>
        )}

        <main className="min-w-0 flex-1 flex flex-col overflow-hidden">
          {children}
        </main>
      </div>

      <StatusBar />

      <SettingsModal
        open={settingsOpen}
        onOpenChange={(v) => { setSettingsOpen(v); if (!v) setSettingsInitialTab(undefined); }}
        user={user}
        projectId={state.activeWorkspaceId}
        initialTab={settingsInitialTab}
      />
    </div>
  );
}
