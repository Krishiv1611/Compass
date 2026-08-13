import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Check, ExternalLink, GitBranch, GitCommitHorizontal, GitPullRequest, Loader2 } from "lucide-react";
import { githubApi, patchesApi, workspaceApi } from "@/api";
import type { WorkspaceContext } from "@/types/project";
import type { WorkspacePatch } from "@/types/patch";
import { useGitHubConnection } from "@/hooks/useGitHubConnection";
import { parseGitHubRemote, resetPublishState, workspacePaths } from "./publishState";
import { Sheet, SheetContent, SheetDescription, SheetHeader, SheetTitle } from "@/components/ui/sheet";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";

const statsFor = (patches: WorkspacePatch[]) => {
  const byPath = new Map<string, { additions: number; deletions: number }>();
  for (const patch of patches) {
    for (const change of patch.changes || []) {
      if ((change.status || patch.status) !== "applied") continue;
      let additions = change.additions ?? 0;
      let deletions = change.deletions ?? 0;
      if (change.diff && change.additions == null) {
        additions = change.diff.split(/\r?\n/).filter((line) => line.startsWith("+") && !line.startsWith("+++")).length;
        deletions = change.diff.split(/\r?\n/).filter((line) => line.startsWith("-") && !line.startsWith("---")).length;
      }
      byPath.set(change.path, { additions, deletions });
    }
  }
  return byPath;
};

export default function GitHubPublishDialog({ open, onClose, workspaceId }: { open: boolean; onClose: () => void; workspaceId: string }) {
  const { status } = useGitHubConnection(open);
  const [context, setContext] = useState<WorkspaceContext | null>(null);
  const [patches, setPatches] = useState<WorkspacePatch[]>([]);
  const [selectedPaths, setSelectedPaths] = useState<string[]>([]);
  const [step, setStep] = useState<"branch" | "commit" | "pr">("branch");
  const [branch, setBranch] = useState("");
  const [newBranch, setNewBranch] = useState("");
  const [message, setMessage] = useState("Apply Compass changes");
  const [prTitle, setPrTitle] = useState("Apply Compass changes");
  const [prBody, setPrBody] = useState("");
  const [base, setBase] = useState("main");
  const [draft, setDraft] = useState(true);
  const [pullUrl, setPullUrl] = useState<string | null>(null);
  const [commitSha, setCommitSha] = useState<string | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const loadGeneration = useRef(0);
  const repository = useMemo(() => parseGitHubRemote(context?.git_remote), [context?.git_remote]);
  const fileStats = useMemo(() => statsFor(patches), [patches]);
  const [allPaths, setAllPaths] = useState<string[]>([]);
  const paths = useMemo(() => allPaths, [allPaths]);
  const totals = useMemo(() => selectedPaths.reduce((result, path) => {
    const stats = fileStats.get(path);
    return { additions: result.additions + (stats?.additions || 0), deletions: result.deletions + (stats?.deletions || 0) };
  }, { additions: 0, deletions: 0 }), [fileStats, selectedPaths]);

  const load = useCallback(async () => {
    const generation = ++loadGeneration.current;
    const reset = resetPublishState();
    setContext(null); setPatches([]); setSelectedPaths(reset.selectedPaths); setBranch(reset.branch); setNewBranch(reset.newBranch); setCommitSha(reset.commitSha); setPullUrl(reset.pullUrl); setStep(reset.step); setAllPaths([]);
    setError(null);
    try {
      const [meta, nextPatches, tree] = await Promise.all([workspaceApi.getContext(workspaceId), patchesApi.getPatches(workspaceId), workspaceApi.getTree(workspaceId)]);
      if (generation !== loadGeneration.current) return;
      setContext(meta);
      setPatches(nextPatches);
      const nextStats = statsFor(nextPatches);
      setSelectedPaths([...nextStats.keys()]);
      setAllPaths(workspacePaths((tree.tree || tree.children || []) as Parameters<typeof workspacePaths>[0]));
      setBranch(meta.git_branch || "");
      setBase(meta.git_branch || "main");
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "Could not prepare publishing");
    }
  }, [workspaceId]);

  useEffect(() => { if (open) void load(); }, [load, open]);

  const createBranch = async () => {
    if (!repository || !newBranch.trim()) return;
    setBusy("branch"); setError(null);
    try {
      const result = await githubApi.createBranch({ workspace_id: workspaceId, ...repository, source_branch: branch, name: newBranch.trim() });
      setBranch(result.name);
      setNewBranch("");
      setStep("commit");
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "Could not create branch");
    } finally { setBusy(null); }
  };

  const commit = async () => {
    if (!repository || !selectedPaths.length) return;
    setBusy("commit"); setError(null);
    try {
      const result = await githubApi.commit({ workspace_id: workspaceId, ...repository, branch, message, paths: selectedPaths });
      setCommitSha(result.sha);
      setStep("pr");
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "Could not commit changes");
    } finally { setBusy(null); }
  };

  const openPullRequest = async () => {
    if (!repository) return;
    setBusy("pr"); setError(null);
    try {
      const result = await githubApi.openPullRequest({ workspace_id: workspaceId, ...repository, title: prTitle, body: prBody, head: branch, base, draft });
      setPullUrl(result.url);
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "Could not open pull request");
    } finally { setBusy(null); }
  };

  const canWrite = status?.capabilities.writeContents ?? false;
  const canPullRequest = status?.capabilities.createPullRequests ?? false;

  return (
    <Sheet open={open} onOpenChange={(next) => { if (!next) onClose(); }}>
      <SheetContent side="right" className="w-full gap-0 sm:max-w-[520px]">
        <SheetHeader className="border-b border-border">
          <SheetTitle>Publish to GitHub</SheetTitle>
          <SheetDescription>{repository ? `${repository.owner}/${repository.repo} · ${branch || "no branch"}` : "This workspace is not linked to a GitHub repository."}</SheetDescription>
        </SheetHeader>
        <div className="grid grid-cols-3 border-b border-border">
          {(["branch", "commit", "pr"] as const).map((item, index) => (
            <button key={item} type="button" onClick={() => setStep(item)} className={`flex h-10 items-center justify-center gap-1.5 border-b-2 text-xs font-medium capitalize ${step === item ? "border-primary text-primary" : "border-transparent text-muted-foreground"}`}>
              <span className="font-mono">{index + 1}</span> {item === "pr" ? "Pull request" : item}
            </button>
          ))}
        </div>
        <div className="min-h-0 flex-1 overflow-y-auto p-5">
          {error && <div role="alert" className="mb-4 border border-destructive/30 bg-destructive/10 px-3 py-2 text-xs text-destructive">{error}<p className="mt-1 text-muted-foreground">If the remote branch moved, refresh or re-import the project before publishing.</p></div>}
          {!repository ? <Empty>Import this project from GitHub before publishing.</Empty> : !status?.connected ? <Empty>Connect GitHub repositories before publishing.</Empty> : (
            <>
              {step === "branch" && (
                <section className="space-y-5">
                  <div><h3 className="text-sm font-semibold">Choose the branch</h3><p className="mt-1 text-xs leading-5 text-muted-foreground">The workspace is currently based on <span className="font-mono">{branch}</span> at <span className="font-mono">{context?.git_head?.slice(0, 8) || "unknown HEAD"}</span>. Compass checks the remote head before writing.</p></div>
                  <div><label htmlFor="publish-branch" className="text-xs font-medium">New branch name</label><Input id="publish-branch" className="mt-2 font-mono" value={newBranch} onChange={(event) => setNewBranch(event.target.value)} placeholder="feature/compass-changes" /></div>
                  {!canWrite && <Permission>Contents write permission is required to create a branch.</Permission>}
                  <div className="flex justify-end"><Button onClick={() => void createBranch()} disabled={!newBranch.trim() || !canWrite || !!busy}>{busy === "branch" && <Loader2 className="h-4 w-4 animate-spin" />}<GitBranch className="h-4 w-4" /> Create branch</Button></div>
                </section>
              )}
              {step === "commit" && (
                <section className="space-y-4">
                  <div><h3 className="text-sm font-semibold">Review the commit</h3><p className="mt-1 text-xs text-muted-foreground">{selectedPaths.length} selected · <span className="text-success">+{totals.additions}</span> <span className="text-destructive">−{totals.deletions}</span></p></div>
                  <div className="max-h-56 overflow-y-auto border-y border-border">
                    {paths.length ? paths.map((path) => {
                      const checked = selectedPaths.includes(path);
                      const stats = fileStats.get(path);
                      return <button key={path} type="button" onClick={() => setSelectedPaths((items) => checked ? items.filter((item) => item !== path) : [...items, path])} className="flex w-full items-center gap-2 border-b border-border px-1 py-2.5 text-left last:border-0 hover:bg-muted/50"><span className={`flex h-4 w-4 items-center justify-center rounded-sm border ${checked ? "border-primary bg-primary text-primary-foreground" : "border-input"}`}>{checked && <Check className="h-3 w-3" />}</span><span className="min-w-0 flex-1 truncate font-mono text-xs">{path}</span><span className="font-mono text-xs"><span className="text-success">+{stats?.additions || 0}</span> <span className="text-destructive">−{stats?.deletions || 0}</span></span></button>;
                    }) : <Empty>Apply project changes before creating a commit.</Empty>}
                  </div>
                  <div><label htmlFor="commit-message" className="text-xs font-medium">Commit message</label><Input id="commit-message" className="mt-2" value={message} onChange={(event) => setMessage(event.target.value)} /></div>
                  {!canWrite && <Permission>Contents write permission is required to commit.</Permission>}
                  <div className="flex justify-end"><Button onClick={() => void commit()} disabled={!message.trim() || !selectedPaths.length || !canWrite || !!busy}>{busy === "commit" && <Loader2 className="h-4 w-4 animate-spin" />}<GitCommitHorizontal className="h-4 w-4" /> Commit to {branch}</Button></div>
                </section>
              )}
              {step === "pr" && (
                <section className="space-y-4">
                  <div><h3 className="text-sm font-semibold">Open a pull request</h3><p className="mt-1 text-xs text-muted-foreground">{commitSha ? `Commit ${commitSha.slice(0, 8)} is ready.` : "Create a commit before opening the pull request."}</p></div>
                  <div><label htmlFor="pr-title" className="text-xs font-medium">Title</label><Input id="pr-title" className="mt-2" value={prTitle} onChange={(event) => setPrTitle(event.target.value)} /></div>
                  <div><label htmlFor="pr-body" className="text-xs font-medium">Description</label><textarea id="pr-body" className="mt-2 min-h-28 w-full rounded-md border border-input bg-background px-3 py-2 text-sm" value={prBody} onChange={(event) => setPrBody(event.target.value)} /></div>
                  <div><label htmlFor="pr-base" className="text-xs font-medium">Base branch</label><Input id="pr-base" className="mt-2 font-mono" value={base} onChange={(event) => setBase(event.target.value)} /></div>
                  <label className="flex items-center gap-2 text-sm"><input type="checkbox" checked={draft} onChange={(event) => setDraft(event.target.checked)} /> Open as draft</label>
                  {!canPullRequest && <Permission>Pull requests write permission is required.</Permission>}
                  <div className="flex justify-end"><Button onClick={() => void openPullRequest()} disabled={!commitSha || !prTitle.trim() || !base.trim() || !canPullRequest || !!busy}>{busy === "pr" && <Loader2 className="h-4 w-4 animate-spin" />}<GitPullRequest className="h-4 w-4" /> Open {draft ? "draft " : ""}pull request</Button></div>
                  {pullUrl && <div className="border border-success/30 bg-success/10 p-3 text-sm"><p className="font-medium text-success">Pull request opened</p><a href={pullUrl} target="_blank" rel="noreferrer" className="mt-2 inline-flex items-center gap-1 text-primary hover:underline">View on GitHub <ExternalLink className="h-3.5 w-3.5" /></a></div>}
                </section>
              )}
            </>
          )}
        </div>
      </SheetContent>
    </Sheet>
  );
}

function Empty({ children }: { children: React.ReactNode }) {
  return <div className="py-10 text-center text-sm text-muted-foreground">{children}</div>;
}

function Permission({ children }: { children: React.ReactNode }) {
  return <div className="border border-warning/30 bg-warning/10 px-3 py-2 text-xs text-warning">{children}</div>;
}
