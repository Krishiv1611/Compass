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
    <footer className="flex h-6 w-full shrink-0 items-center justify-between border-t border-border bg-[#080A0E] px-3 text-[11px] font-mono text-muted-foreground select-none">
      <div className="flex min-w-0 items-center gap-3">
        <span className="flex items-center gap-1.5">
          {connection === "offline" ? (
            <span className="flex items-center gap-1 text-destructive font-medium">
              <WifiOff className="h-3 w-3" /> Offline
            </span>
          ) : connection === "streaming" ? (
            <span className="flex items-center gap-1 text-sky-400 font-medium">
              <Radio className="h-3 w-3 animate-pulse" /> Live Stream
            </span>
          ) : (
            <span className="flex items-center gap-1 text-emerald-400">
              <Radio className="h-3 w-3" /> Connected
            </span>
          )}
        </span>

        <span className="text-border">|</span>

        <button
          type="button"
          onClick={reviewPatches}
          className={`flex items-center gap-1.5 px-1.5 py-0.5 rounded transition-colors ${
            state.pendingPatchCount > 0
              ? "bg-sky-500/15 text-sky-400 border border-sky-500/30 font-semibold"
              : "hover:text-foreground text-muted-foreground"
          }`}
          title="Review staged file patches"
        >
          <Activity className="h-3 w-3" />
          <span>{state.pendingPatchCount} {state.pendingPatchCount === 1 ? "patch" : "patches"}</span>
        </button>

        <span className="text-border hidden sm:inline">|</span>

        <span className="hidden min-w-0 items-center gap-1.5 sm:flex text-slate-400">
          <GitBranch className="h-3 w-3 text-sky-400/80" />
          <span className="truncate max-w-[160px]">{state.projectName || "Studio"}</span>
        </span>
      </div>

      <div className="flex items-center gap-3">
        <span
          className="hidden max-w-64 items-center gap-1.5 sm:flex rounded bg-surface-raised/60 px-1.5 py-0.5 border border-border/60 text-slate-300"
          title={`LLM Provider: ${profile.provider} | Model: ${profile.model}`}
        >
          <Bot className="h-3 w-3 text-sky-400 shrink-0" />
          <span className="truncate">{profile.model !== "model" ? profile.model : "Universal Router"}</span>
        </span>

        <span className="hidden items-center gap-1 md:flex text-slate-400">
          <ShieldCheck className="h-3 w-3 text-emerald-400" />
          <span>{profile.permission === "fast" ? "Autonomous" : "Hybrid Safety"}</span>
        </span>

        <span className="rounded bg-sky-500/10 px-1.5 py-0.2 text-[10px] uppercase font-bold text-sky-400 border border-sky-500/20">
          {state.mode}
        </span>
      </div>
    </footer>
  );
}
