import { useEffect, useRef, useState } from "react";
import { ArrowRight, Clock, FolderUp, GitFork, Loader2, Plus } from "lucide-react";
import { toast } from "react-toastify";
import { workspaceApi } from "@/api";
import type { Workspace } from "@/types/project";
import GitHubImportDialog from "@/components/github/GitHubImportDialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";

export default function WorkspaceLanding({
  sessionId,
  ensureSession,
  onWorkspaceReady,
}: {
  sessionId: string | null;
  ensureSession: (title?: string) => Promise<string>;
  onWorkspaceReady: (workspaceId: string, folderName: string) => void;
}) {
  const [recent, setRecent] = useState<Workspace[]>([]);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState<"upload" | "create" | null>(null);
  const [projectName, setProjectName] = useState("");
  const [showCreate, setShowCreate] = useState(false);
  const [githubSessionId, setGithubSessionId] = useState<string | null>(null);
  const folderInput = useRef<HTMLInputElement>(null);

  useEffect(() => {
    let cancelled = false;
    workspaceApi.listWorkspaces()
      .then((items) => {
        if (!cancelled) setRecent([...items].sort((a, b) => (b.created_at || "").localeCompare(a.created_at || "")).slice(0, 6));
      })
      .catch(() => undefined)
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, []);

  const openGitHub = async () => {
    try {
      setGithubSessionId(sessionId || await ensureSession("GitHub project"));
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Could not prepare repository import");
    }
  };

  const uploadFolder = async (files: FileList | null) => {
    if (!files?.length) return;
    setBusy("upload");
    try {
      const sid = sessionId || await ensureSession(files[0].webkitRelativePath?.split("/")[0] || "Uploaded project");
      const result = await workspaceApi.uploadFolder(sid, files);
      const name = files[0].webkitRelativePath?.split("/")[0] || "Uploaded project";
      onWorkspaceReady(result.workspace_id, name);
      toast.success(`${files.length} files uploaded`);
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Could not upload project");
    } finally {
      setBusy(null);
      if (folderInput.current) folderInput.current.value = "";
    }
  };

  const createProject = async () => {
    if (!projectName.trim()) return;
    setBusy("create");
    try {
      const sid = sessionId || await ensureSession(projectName.trim());
      const workspace = await workspaceApi.createWorkspace(sid, projectName.trim());
      onWorkspaceReady(workspace.id, workspace.name || projectName.trim());
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Could not create project");
    } finally {
      setBusy(null);
    }
  };

  return (
    <div className="h-full overflow-y-auto bg-background px-5 py-8 sm:px-8">
      <div className="mx-auto max-w-2xl">
        <p className="text-sm font-medium text-brand">Start a project</p>
        <h1 className="mt-1 text-xl font-semibold">Choose the code Compass can work with</h1>
        <p className="mt-2 max-w-xl text-sm leading-6 text-muted-foreground">Each project runs in an isolated workspace. Import a repository, upload a folder, or begin with an empty project.</p>

        <section className="mt-7 border-y border-border">
          <button type="button" onClick={() => void openGitHub()} className="flex w-full items-center gap-4 border-b border-border px-1 py-5 text-left hover:bg-muted/50">
            <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-md bg-primary text-primary-foreground"><GitFork className="h-5 w-5" /></span>
            <span className="min-w-0 flex-1"><span className="block text-sm font-semibold">Import from GitHub</span><span className="mt-1 block text-xs text-muted-foreground">Browse accessible repositories and choose a branch.</span></span>
            <ArrowRight className="h-4 w-4 text-muted-foreground" />
          </button>
          <button type="button" onClick={() => folderInput.current?.click()} className="flex w-full items-center gap-4 border-b border-border px-1 py-4 text-left hover:bg-muted/50" disabled={busy === "upload"}>
            <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-md border border-border"><FolderUp className="h-4 w-4" /></span>
            <span className="min-w-0 flex-1"><span className="block text-sm font-medium">Upload project folder</span><span className="mt-0.5 block text-xs text-muted-foreground">Copy a local folder into a safe web workspace.</span></span>
            {busy === "upload" ? <Loader2 className="h-4 w-4 animate-spin" /> : <ArrowRight className="h-4 w-4 text-muted-foreground" />}
          </button>
          <input ref={folderInput} type="file" multiple className="sr-only" onChange={(event) => void uploadFolder(event.target.files)} {...({ webkitdirectory: "", directory: "" } as React.InputHTMLAttributes<HTMLInputElement>)} />
          <div>
            <button type="button" onClick={() => setShowCreate((value) => !value)} className="flex w-full items-center gap-4 px-1 py-4 text-left hover:bg-muted/50">
              <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-md border border-border"><Plus className="h-4 w-4" /></span>
              <span className="min-w-0 flex-1"><span className="block text-sm font-medium">Create empty project</span><span className="mt-0.5 block text-xs text-muted-foreground">Start with a named workspace and add files as you go.</span></span>
              <ArrowRight className={`h-4 w-4 text-muted-foreground transition-transform ${showCreate ? "rotate-90" : ""}`} />
            </button>
            {showCreate && (
              <form className="flex gap-2 pb-4 pl-[53px]" onSubmit={(event) => { event.preventDefault(); void createProject(); }}>
                <Input value={projectName} onChange={(event) => setProjectName(event.target.value)} placeholder="Project name" aria-label="Project name" />
                <Button type="submit" disabled={!projectName.trim() || busy === "create"}>{busy === "create" && <Loader2 className="h-4 w-4 animate-spin" />} Create</Button>
              </form>
            )}
          </div>
        </section>

        <section className="mt-8">
          <div className="mb-3 flex items-center gap-2 text-sm font-semibold"><Clock className="h-4 w-4 text-muted-foreground" /> Recent projects</div>
          {loading ? (
            <div className="flex items-center gap-2 py-4 text-sm text-muted-foreground"><Loader2 className="h-4 w-4 animate-spin" /> Loading projects</div>
          ) : recent.length ? (
            <div className="divide-y divide-border border-y border-border">
              {recent.map((workspace) => (
                <button key={workspace.id} type="button" onClick={() => onWorkspaceReady(workspace.id, workspace.name)} className="flex w-full items-center justify-between gap-3 px-1 py-3 text-left hover:bg-muted/50">
                  <span className="min-w-0"><span className="block truncate text-sm font-medium">{workspace.name}</span><span className="block font-mono text-xs text-muted-foreground">{workspace.source_type || "workspace"}{workspace.git_branch ? ` · ${workspace.git_branch}` : ""}</span></span>
                  <ArrowRight className="h-4 w-4 shrink-0 text-muted-foreground" />
                </button>
              ))}
            </div>
          ) : <p className="py-4 text-sm text-muted-foreground">No recent projects yet.</p>}
        </section>
      </div>
      {githubSessionId && <GitHubImportDialog open onClose={() => setGithubSessionId(null)} sessionId={githubSessionId} onImported={(workspace) => onWorkspaceReady(workspace.id, workspace.name)} />}
    </div>
  );
}
