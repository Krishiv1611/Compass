import { useState } from "react";
import { CheckCircle2, GitFork, Loader2, RefreshCcw, Unplug } from "lucide-react";
import { githubApi } from "@/api";
import { useGitHubConnection } from "@/hooks/useGitHubConnection";
import GitHubPatForm from "./GitHubPatForm";
import { Button } from "@/components/ui/button";

export default function GitHubConnectionPanel({ compact = false, onConnected }: { compact?: boolean; onConnected?: () => void }) {
  const { status, loading, error, refresh, setStatus } = useGitHubConnection();
  const [showPat, setShowPat] = useState(false);
  const [busy, setBusy] = useState(false);

  const connectOAuth = async () => {
    setBusy(true);
    try {
      sessionStorage.setItem("compass_oauth_intent", "connect_github");
      sessionStorage.setItem("compass_oauth_provider", "github");
      sessionStorage.setItem("compass_oauth_return_to", `${window.location.pathname}${window.location.search}`);
      const { url } = await githubApi.getOAuthUrl(`${window.location.pathname}${window.location.search}`);
      window.location.assign(url);
    } finally {
      setBusy(false);
    }
  };

  const disconnect = async () => {
    setBusy(true);
    try {
      await githubApi.disconnect();
      await refresh();
    } finally {
      setBusy(false);
    }
  };

  if (loading && !status) return <div className="flex items-center gap-2 py-6 text-sm text-muted-foreground"><Loader2 className="h-4 w-4 animate-spin" /> Checking GitHub connection</div>;
  if (status?.connected) {
    return (
      <section className={compact ? "space-y-3" : "space-y-4"}>
        <div className="flex items-center gap-3">
          {status.avatarUrl ? <img src={status.avatarUrl} alt="" className="h-9 w-9 rounded-full" /> : <span className="flex h-9 w-9 items-center justify-center rounded-full border border-border"><GitFork className="h-4 w-4" /></span>}
          <div className="min-w-0 flex-1"><p className="truncate text-sm font-semibold">{status.login || "GitHub connected"}</p><p className="text-xs text-muted-foreground">{status.method?.replace("_", " ")}{status.repositoryCount != null ? ` · ${status.repositoryCount} repositories` : ""}</p></div>
          <CheckCircle2 className="h-4 w-4 text-success" />
        </div>
        <div className="grid grid-cols-2 gap-x-4 gap-y-1 text-xs">
          <span className="text-muted-foreground">Read repositories</span><span>{status.capabilities.readContents ? "Available" : "Unavailable"}</span>
          <span className="text-muted-foreground">Commit changes</span><span>{status.capabilities.writeContents ? "Available" : "Permission needed"}</span>
          <span className="text-muted-foreground">Open pull requests</span><span>{status.capabilities.createPullRequests ? "Available" : "Permission needed"}</span>
          {status.lastValidatedAt && <><span className="text-muted-foreground">Last validated</span><span>{new Date(status.lastValidatedAt).toLocaleString()}</span></>}
        </div>
        <div className="flex flex-wrap gap-2">
          <Button variant="outline" size="sm" onClick={() => void refresh(true)} disabled={busy}><RefreshCcw className="h-4 w-4" /> Validate</Button>
          <Button variant="outline" size="sm" onClick={() => setShowPat(true)} disabled={busy}>Replace credential</Button>
          <Button variant="ghost" size="sm" onClick={() => void disconnect()} disabled={busy} className="text-destructive"><Unplug className="h-4 w-4" /> Disconnect</Button>
        </div>
        {showPat && <div className="border-t border-border pt-4"><GitHubPatForm onCancel={() => setShowPat(false)} onConnected={(next) => { setStatus(next); setShowPat(false); onConnected?.(); }} /></div>}
      </section>
    );
  }

  return (
    <section className="space-y-4">
      <div><p className="text-sm font-semibold">Connect GitHub repositories</p><p className="mt-1 text-xs leading-5 text-muted-foreground">Repository access is separate from signing in to Compass. Connect only the code you want to import or publish.</p></div>
      {error && <p role="alert" className="text-xs text-destructive">{error}</p>}
      <Button onClick={() => void connectOAuth()} disabled={busy}>{busy ? <Loader2 className="h-4 w-4 animate-spin" /> : <GitFork className="h-4 w-4" />} Connect with GitHub</Button>
      <button type="button" onClick={() => setShowPat((value) => !value)} className="block text-xs text-primary hover:underline">Advanced: use a fine-grained PAT</button>
      {showPat && <GitHubPatForm onCancel={() => setShowPat(false)} onConnected={(next) => { setStatus(next); setShowPat(false); onConnected?.(); }} />}
    </section>
  );
}
