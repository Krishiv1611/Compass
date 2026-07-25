import { useState } from "react";
import { Eye, EyeOff, KeyRound, Loader2 } from "lucide-react";
import { githubApi } from "@/api";
import type { GitHubConnectionStatus } from "@/types/github";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";

export default function GitHubPatForm({ onConnected, onCancel }: { onConnected: (status: GitHubConnectionStatus) => void; onCancel?: () => void }) {
  const [token, setToken] = useState("");
  const [visible, setVisible] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const submit = async (event: React.FormEvent) => {
    event.preventDefault();
    setSaving(true);
    setError(null);
    try {
      const status = await githubApi.connectPat(token.trim());
      setToken("");
      onConnected(status);
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "GitHub rejected this credential");
    } finally {
      setSaving(false);
    }
  };

  return (
    <form onSubmit={submit} className="space-y-3">
      <div>
        <label htmlFor="github-pat" className="text-sm font-medium">Fine-grained personal access token</label>
        <p className="mt-1 text-xs leading-5 text-muted-foreground">Choose only the repositories Compass needs. Grant Metadata read, Contents read/write, and Pull requests read/write. Set an expiration date.</p>
      </div>
      <div className="relative">
        <KeyRound className="absolute left-3 top-2.5 h-4 w-4 text-muted-foreground" />
        <Input id="github-pat" type={visible ? "text" : "password"} autoComplete="off" value={token} onChange={(event) => setToken(event.target.value)} className="pl-9 pr-10" placeholder="github_pat_…" aria-describedby={error ? "github-pat-error" : undefined} />
        <button type="button" onClick={() => setVisible((value) => !value)} className="absolute right-2 top-2 rounded p-1 text-muted-foreground hover:text-foreground" aria-label={visible ? "Hide token" : "Show token"}>{visible ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}</button>
      </div>
      {error && <p id="github-pat-error" role="alert" className="text-xs text-destructive">{error}</p>}
      <p className="text-xs text-muted-foreground">The token is submitted once over HTTPS, encrypted by the backend, and never returned to this browser.</p>
      <div className="flex justify-end gap-2">
        {onCancel && <Button type="button" variant="outline" onClick={onCancel}>Cancel</Button>}
        <Button type="submit" disabled={saving || token.trim().length < 20}>{saving && <Loader2 className="h-4 w-4 animate-spin" />} Connect token</Button>
      </div>
    </form>
  );
}
