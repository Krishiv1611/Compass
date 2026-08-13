import { useEffect, useState } from "react";
import { Activity, Bot, GitBranch, Radio, ShieldCheck, WifiOff } from "lucide-react";
import { preferencesApi } from "@/api";
import { useRunEvents } from "@/contexts/RunContext";
import { useWorkbench } from "@/contexts/WorkbenchContext";

export default function StatusBar() {
  const { connection } = useRunEvents();
  const { state, reviewPatches } = useWorkbench();
  const [profile, setProfile] = useState({ provider: "provider", model: "model", permission: "standard" });

  useEffect(() => {
    const apply = (value: { llm_provider?: string; model?: string; safe_mode?: boolean; fast_mode?: boolean }) => {
      setProfile({
        provider: value.llm_provider || "provider",
        model: value.model || "model",
        permission: value.safe_mode ? "review" : value.fast_mode ? "fast" : "standard",
      });
    };
    void preferencesApi.getSettings().then(apply).catch(() => undefined);
    const onSettings = (event: Event) => apply((event as CustomEvent).detail || {});
    window.addEventListener("compass:settings-changed", onSettings);
    return () => window.removeEventListener("compass:settings-changed", onSettings);
  }, []);

  return (
    <footer className="flex h-6 w-full shrink-0 items-center justify-between border-t border-border bg-card px-3 text-xs text-muted-foreground">
      <div className="flex min-w-0 items-center gap-4">
        <span className="flex items-center gap-1.5">
          {connection === "offline" ? <WifiOff className="h-3 w-3 text-destructive" /> : <Radio className={`h-3 w-3 ${connection === "streaming" ? "text-success" : ""}`} />}
          {connection}
        </span>
        <button type="button" onClick={reviewPatches} className="flex items-center gap-1.5 hover:text-foreground">
          <Activity className="h-3 w-3" /> {state.pendingPatchCount} changed
        </button>
        <span className="hidden min-w-0 items-center gap-1.5 sm:flex">
          <GitBranch className="h-3 w-3" /><span className="truncate">{state.projectName}</span>
        </span>
      </div>
      <div className="flex items-center gap-4">
        <span className="hidden max-w-64 items-center gap-1.5 sm:flex" title={`${profile.provider} / ${profile.model}`}><Bot className="h-3 w-3 shrink-0" /><span className="truncate">{profile.provider} / {profile.model}</span></span>
        <span className="hidden items-center gap-1.5 md:flex"><ShieldCheck className="h-3 w-3" /> {profile.permission}</span>
        <span className="capitalize">{state.mode}</span>
      </div>
    </footer>
  );
}
