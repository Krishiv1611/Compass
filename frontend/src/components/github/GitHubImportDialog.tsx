import { useCallback, useEffect, useState } from "react";
import { Archive, CalendarClock, GitFork, Loader2, Lock, Search } from "lucide-react";
import { githubApi } from "@/api";
import { useGitHubConnection } from "@/hooks/useGitHubConnection";
import type { GitHubBranch, GitHubRepository } from "@/types/github";
import type { Workspace } from "@/types/project";
import GitHubConnectionPanel from "./GitHubConnectionPanel";
import Modal from "@/components/ui/modal";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";

type ImportStage = "idle" | "creating" | "cloning" | "indexing" | "ready";

export default function GitHubImportDialog({
  open,
  onClose,
  sessionId,
  onImported,
}: {
  open: boolean;
  onClose: () => void;
  sessionId: string;
  onImported: (workspace: Workspace) => void;
}) {
  const { status, loading: connectionLoading, refresh } = useGitHubConnection(open);
  const [repositories, setRepositories] = useState<GitHubRepository[]>([]);
  const [owners, setOwners] = useState<string[]>([]);
  const [owner, setOwner] = useState("");
  const [query, setQuery] = useState("");
  const [cursor, setCursor] = useState<string | null>(null);
  const [selected, setSelected] = useState<GitHubRepository | null>(null);
  const [branches, setBranches] = useState<GitHubBranch[]>([]);
  const [branch, setBranch] = useState("");
  const [loading, setLoading] = useState(false);
  const [loadingMore, setLoadingMore] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [stage, setStage] = useState<ImportStage>("idle");

  const loadRepositories = useCallback(async (append = false) => {
    if (!status?.connected) return;
    if (append) setLoadingMore(true);
    else setLoading(true);
    setError(null);
    try {
      const page = await githubApi.listRepositories({
        cursor: append ? cursor || undefined : undefined,
        owner: owner || undefined,
        query: query || undefined,
      });
      setRepositories((items) => append ? [...items, ...page.repositories.filter((repo) => !items.some((item) => item.id === repo.id))] : page.repositories);
      setCursor(page.nextCursor || null);
      if (!append) setOwners(page.owners || []);
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "Could not load repositories");
    } finally {
      setLoading(false);
      setLoadingMore(false);
    }
  }, [cursor, owner, query, status?.connected]);

  useEffect(() => {
    if (!open || !status?.connected) return;
    const timer = window.setTimeout(() => void loadRepositories(false), query ? 220 : 0);
    return () => window.clearTimeout(timer);
  }, [loadRepositories, open, query, owner, status?.connected]);

  const chooseRepository = async (repository: GitHubRepository) => {
    setSelected(repository);
    setLoading(true);
    setError(null);
    try {
      const [repoOwner, name] = repository.full_name.split("/");
      const items = await githubApi.listBranches(repoOwner, name);
      setBranches(items);
      setBranch(repository.default_branch || items[0]?.name || "");
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "Could not load repository branches");
    } finally {
      setLoading(false);
    }
  };

  const importRepository = async () => {
    if (!selected || !branch) return;
    const [repoOwner, repo] = selected.full_name.split("/");
    setStage("creating");
    setError(null);
    try {
      setStage("cloning");
      const workspace = await githubApi.importRepository({ session_id: sessionId, owner: repoOwner, repo, branch });
      setStage("indexing");
      await new Promise<void>((resolve) => window.setTimeout(resolve, 250));
      setStage("ready");
      onImported(workspace);
      onClose();
    } catch (requestError) {
      setStage("idle");
      setError(requestError instanceof Error ? requestError.message : "Repository import failed");
    }
  };

  return (
    <Modal open={open} onClose={onClose} maxWidth="max-w-3xl" showClose ariaLabel="Import from GitHub">
      <div className="border-b border-border px-5 py-4">
        <div className="flex items-center gap-2"><GitFork className="h-4 w-4 text-primary" /><h2 className="text-base font-semibold">Import from GitHub</h2></div>
        <p className="mt-1 text-xs text-muted-foreground">Choose an accessible repository and the branch Compass should isolate.</p>
      </div>
      <div className="max-h-[78vh] overflow-y-auto p-5">
        {connectionLoading ? (
          <StateMessage><Loader2 className="h-5 w-5 animate-spin" /> Checking GitHub connection</StateMessage>
        ) : !status?.connected ? (
          <GitHubConnectionPanel onConnected={() => void refresh(true)} />
        ) : stage !== "idle" ? (
          <StateMessage>
            <Loader2 className="h-5 w-5 animate-spin text-primary" />
            <span className="font-medium">{stage === "creating" ? "Creating workspace" : stage === "cloning" ? "Cloning repository" : stage === "indexing" ? "Indexing project" : "Ready"}</span>
            <span className="text-xs text-muted-foreground">{selected?.full_name} · {branch}</span>
          </StateMessage>
        ) : (
          <div className="grid min-h-[420px] gap-5 sm:grid-cols-[minmax(0,1fr)_240px]">
            <div className="min-w-0">
              <div className="mb-3 flex gap-2">
                <div className="relative min-w-0 flex-1"><Search className="absolute left-3 top-2.5 h-4 w-4 text-muted-foreground" /><Input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Search repositories" className="pl-9" /></div>
                <select value={owner} onChange={(event) => setOwner(event.target.value)} className="h-9 max-w-36 rounded-md border border-input bg-background px-2 text-xs" aria-label="Filter by owner"><option value="">All owners</option>{owners.map((item) => <option key={item} value={item}>{item}</option>)}</select>
              </div>
              {error && <div role="alert" className="mb-3 flex items-center justify-between gap-3 border border-destructive/30 bg-destructive/10 px-3 py-2 text-xs text-destructive"><span>{error}</span><Button variant="ghost" size="sm" onClick={() => void loadRepositories(false)}>Retry</Button></div>}
              <div className="max-h-[340px] overflow-y-auto border-y border-border">
                {loading ? <StateMessage><Loader2 className="h-4 w-4 animate-spin" /> Loading repositories</StateMessage> : repositories.length ? repositories.map((repository) => (
                  <button key={repository.id} type="button" disabled={repository.archived} onClick={() => void chooseRepository(repository)} className={`flex w-full items-start gap-2 border-b border-border px-2 py-3 text-left last:border-0 hover:bg-muted/50 disabled:opacity-50 ${selected?.id === repository.id ? "bg-primary/10" : ""}`}>
                    {repository.private ? <Lock className="mt-0.5 h-3.5 w-3.5 shrink-0 text-muted-foreground" /> : <GitFork className="mt-0.5 h-3.5 w-3.5 shrink-0 text-muted-foreground" />}
                    <span className="min-w-0 flex-1"><span className="block truncate text-sm font-medium">{repository.full_name}</span><span className="mt-1 flex flex-wrap items-center gap-2 font-mono text-xs text-muted-foreground"><span>{repository.default_branch}</span>{repository.updated_at && <span className="flex items-center gap-1"><CalendarClock className="h-3 w-3" /> {new Date(repository.updated_at).toLocaleDateString()}</span>}{repository.archived && <span className="flex items-center gap-1"><Archive className="h-3 w-3" /> Archived</span>}</span></span>
                  </button>
                )) : <StateMessage>No repositories match this search. Check the owner filter or validate repository permissions.</StateMessage>}
              </div>
              {cursor && <Button variant="outline" size="sm" className="mt-3 w-full" onClick={() => void loadRepositories(true)} disabled={loadingMore}>{loadingMore && <Loader2 className="h-4 w-4 animate-spin" />} Load more</Button>}
            </div>
            <aside className="border-t border-border pt-4 sm:border-l sm:border-t-0 sm:pl-5 sm:pt-0">
              <h3 className="text-sm font-semibold">Import branch</h3>
              {selected ? (
                <div className="mt-3 space-y-3">
                  <p className="truncate text-sm">{selected.full_name}</p>
                  <label className="block text-xs text-muted-foreground" htmlFor="github-import-branch">Branch</label>
                  <select id="github-import-branch" value={branch} onChange={(event) => setBranch(event.target.value)} className="h-9 w-full rounded-md border border-input bg-background px-2 text-xs">{branches.map((item) => <option key={item.name} value={item.name}>{item.name}{item.protected ? " · protected" : ""}</option>)}</select>
                  {!selected.permissions?.pull && <p className="text-xs text-warning">This credential may not have permission to read repository contents.</p>}
                  <Button className="w-full" onClick={() => void importRepository()} disabled={!branch || loading || !selected.permissions?.pull}>{loading && <Loader2 className="h-4 w-4 animate-spin" />} Import repository</Button>
                  <p className="text-xs leading-5 text-muted-foreground">Repository archives are limited to 50 MB. Compass creates a server-isolated workspace before indexing.</p>
                </div>
              ) : <p className="mt-3 text-xs leading-5 text-muted-foreground">Select a repository to inspect branches and import permissions.</p>}
            </aside>
          </div>
        )}
      </div>
    </Modal>
  );
}

function StateMessage({ children }: { children: React.ReactNode }) {
  return <div className="flex min-h-40 flex-col items-center justify-center gap-2 px-5 text-center text-sm text-muted-foreground">{children}</div>;
}
