import { useEffect, useRef, useState } from "react";
import {
  ArrowRight,
  Clock,
  Code2,
  Cpu,
  FolderUp,
  GitFork,
  Globe,
  Loader2,
  Plus,
  Radio,
  Sparkles,
  Terminal,
} from "lucide-react";
import { lazy, Suspense } from "react";
import { toast } from "react-toastify";
import { workspaceApi } from "@/api";
import type { Workspace } from "@/types/project";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";

const GitHubImportDialog = lazy(() => import("@/components/github/GitHubImportDialog"));

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
  const [busy, setBusy] = useState<"upload" | "create" | "starter" | null>(null);
  const [projectName, setProjectName] = useState("");
  const [showCreate, setShowCreate] = useState(false);
  const [githubSessionId, setGithubSessionId] = useState<string | null>(null);
  const folderInput = useRef<HTMLInputElement>(null);

  useEffect(() => {
    let cancelled = false;
    workspaceApi
      .listWorkspaces()
      .then((items) => {
        if (!cancelled) {
          setRecent(
            [...items]
              .sort((a, b) => (b.created_at || "").localeCompare(a.created_at || ""))
              .slice(0, 8)
          );
        }
      })
      .catch(() => undefined)
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const openGitHub = async () => {
    try {
      setGithubSessionId(sessionId || (await ensureSession("GitHub project")));
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Could not prepare repository import");
    }
  };

  const uploadFolder = async (files: FileList | null) => {
    if (!files?.length) return;
    setBusy("upload");
    try {
      const sid =
        sessionId ||
        (await ensureSession(files[0].webkitRelativePath?.split("/")[0] || "Uploaded project"));
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

  const createStarterApp = async () => {
    setBusy("starter");
    try {
      const sid = sessionId || (await ensureSession("Fullstack Web App"));
      const randomSuffix = Math.floor(1000 + Math.random() * 9000);
      const defaultName = `react-vite-${randomSuffix}`;
      const workspace = await workspaceApi.createWorkspace(sid, defaultName);
      onWorkspaceReady(workspace.id, workspace.name || defaultName);
      toast.success("Ready-to-run React + Vite project initialized");
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Could not initialize starter project");
    } finally {
      setBusy(null);
    }
  };

  const createProject = async () => {
    if (!projectName.trim()) return;
    setBusy("create");
    try {
      const sid = sessionId || (await ensureSession(projectName.trim()));
      const workspace = await workspaceApi.createWorkspace(sid, projectName.trim());
      onWorkspaceReady(workspace.id, workspace.name || projectName.trim());
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Could not create project");
    } finally {
      setBusy(null);
    }
  };

  const selectRecent = async (workspace: Workspace) => {
    try {
      const sid = sessionId || (await ensureSession(workspace.name));
      await workspaceApi.attachWorkspace(sid, workspace.id);
      onWorkspaceReady(workspace.id, workspace.name);
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Could not attach project to this task");
    }
  };

  return (
    <div className="h-full overflow-y-auto bg-background px-6 py-10 sm:px-10">
      <div className="mx-auto max-w-3xl space-y-8">
        {/* Header telemetry badge & title */}
        <div>
          <div className="inline-flex items-center gap-2 rounded-full border border-sky-500/30 bg-sky-500/10 px-3 py-1 text-xs font-mono text-sky-400">
            <Radio className="h-3 w-3 animate-pulse text-sky-400" />
            <span>Dual-Engine Developer Workbench</span>
            <span className="text-muted-foreground">·</span>
            <span className="text-emerald-400 font-semibold">$0 Cloud / Hardware Cost</span>
          </div>

          <h1 className="mt-3 text-2xl font-bold tracking-tight text-foreground sm:text-3xl">
            What do you want to build today?
          </h1>
          <p className="mt-2 text-sm leading-relaxed text-muted-foreground">
            Compass bridges <span className="text-foreground font-medium">Lovable</span> (0-to-1 visual preview canvas with click-to-inspect) and <span className="text-foreground font-medium">Devin</span> (1-to-N autonomous terminal, remote sandboxes & Playwright QA).
          </p>
        </div>

        {/* 4 Launchpad Action Cards */}
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
          {/* Card 1: 1-Click Starter Web App */}
          <button
            type="button"
            onClick={() => void createStarterApp()}
            disabled={busy === "starter"}
            className="group relative flex flex-col justify-between rounded-lg border border-border bg-card/60 p-4 text-left transition-all hover:border-sky-500/60 hover:bg-card hover:shadow-lg hover:shadow-sky-500/5 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-sky-500"
          >
            <div>
              <div className="flex items-center justify-between">
                <span className="flex h-10 w-10 items-center justify-center rounded-md bg-sky-500/15 text-sky-400 border border-sky-500/30">
                  <Globe className="h-5 w-5" />
                </span>
                <span className="rounded-full bg-emerald-500/15 px-2 py-0.5 font-mono text-[10px] font-semibold text-emerald-400 border border-emerald-500/30">
                  Ready in 2s
                </span>
              </div>
              <h2 className="mt-3 text-sm font-semibold text-foreground group-hover:text-sky-400 transition-colors">
                Instant React + Vite App
              </h2>
              <p className="mt-1 text-xs text-muted-foreground">
                Pre-warmed React 19, Tailwind CSS & Vite starter. Boots directly into in-browser WebContainer Canvas.
              </p>
            </div>
            <div className="mt-4 flex items-center gap-1.5 text-xs font-medium text-sky-400">
              {busy === "starter" ? (
                <>
                  <Loader2 className="h-3.5 w-3.5 animate-spin" />
                  <span>Bootstrapping...</span>
                </>
              ) : (
                <>
                  <span>Launch Canvas</span>
                  <ArrowRight className="h-3.5 w-3.5 transition-transform group-hover:translate-x-1" />
                </>
              )}
            </div>
          </button>

          {/* Card 2: Import from GitHub */}
          <button
            type="button"
            onClick={() => void openGitHub()}
            className="group relative flex flex-col justify-between rounded-lg border border-border bg-card/60 p-4 text-left transition-all hover:border-purple-500/60 hover:bg-card hover:shadow-lg hover:shadow-purple-500/5 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-purple-500"
          >
            <div>
              <div className="flex items-center justify-between">
                <span className="flex h-10 w-10 items-center justify-center rounded-md bg-purple-500/15 text-purple-400 border border-purple-500/30">
                  <GitFork className="h-5 w-5" />
                </span>
                <span className="rounded-full bg-muted/60 px-2 py-0.5 font-mono text-[10px] text-muted-foreground border border-border">
                  Git Clone
                </span>
              </div>
              <h2 className="mt-3 text-sm font-semibold text-foreground group-hover:text-purple-400 transition-colors">
                Import from GitHub
              </h2>
              <p className="mt-1 text-xs text-muted-foreground">
                Connect your GitHub account or clone public/private repositories with branch switching.
              </p>
            </div>
            <div className="mt-4 flex items-center gap-1.5 text-xs font-medium text-purple-400">
              <span>Select Repository</span>
              <ArrowRight className="h-3.5 w-3.5 transition-transform group-hover:translate-x-1" />
            </div>
          </button>

          {/* Card 3: Upload Local Folder */}
          <button
            type="button"
            onClick={() => folderInput.current?.click()}
            disabled={busy === "upload"}
            className="group relative flex flex-col justify-between rounded-lg border border-border bg-card/60 p-4 text-left transition-all hover:border-emerald-500/60 hover:bg-card hover:shadow-lg hover:shadow-emerald-500/5 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-emerald-500"
          >
            <div>
              <div className="flex items-center justify-between">
                <span className="flex h-10 w-10 items-center justify-center rounded-md bg-emerald-500/15 text-emerald-400 border border-emerald-500/30">
                  <FolderUp className="h-5 w-5" />
                </span>
                <span className="rounded-full bg-muted/60 px-2 py-0.5 font-mono text-[10px] text-muted-foreground border border-border">
                  Local
                </span>
              </div>
              <h2 className="mt-3 text-sm font-semibold text-foreground group-hover:text-emerald-400 transition-colors">
                Upload Project Folder
              </h2>
              <p className="mt-1 text-xs text-muted-foreground">
                Copy existing source code from your machine into an isolated, sandboxed web workspace.
              </p>
            </div>
            <div className="mt-4 flex items-center gap-1.5 text-xs font-medium text-emerald-400">
              {busy === "upload" ? (
                <>
                  <Loader2 className="h-3.5 w-3.5 animate-spin" />
                  <span>Uploading files...</span>
                </>
              ) : (
                <>
                  <span>Select Directory</span>
                  <ArrowRight className="h-3.5 w-3.5 transition-transform group-hover:translate-x-1" />
                </>
              )}
            </div>
          </button>
          <input
            ref={folderInput}
            type="file"
            multiple
            className="sr-only"
            onChange={(event) => void uploadFolder(event.target.files)}
            {...({ webkitdirectory: "", directory: "" } as React.InputHTMLAttributes<HTMLInputElement>)}
          />

          {/* Card 4: Empty / Custom Project */}
          <div className="group relative flex flex-col justify-between rounded-lg border border-border bg-card/60 p-4 text-left transition-all hover:border-amber-500/60 hover:bg-card">
            <div>
              <div className="flex items-center justify-between">
                <span className="flex h-10 w-10 items-center justify-center rounded-md bg-amber-500/15 text-amber-400 border border-amber-500/30">
                  <Terminal className="h-5 w-5" />
                </span>
                <span className="rounded-full bg-muted/60 px-2 py-0.5 font-mono text-[10px] text-muted-foreground border border-border">
                  Scratchpad
                </span>
              </div>
              <h2 className="mt-3 text-sm font-semibold text-foreground">
                Custom / Blank Workspace
              </h2>
              <p className="mt-1 text-xs text-muted-foreground">
                Start from a blank slate for CLI pipelines, Python scripts, or custom microservices.
              </p>
            </div>

            <div className="mt-4">
              {showCreate ? (
                <form
                  className="flex gap-2"
                  onSubmit={(event) => {
                    event.preventDefault();
                    void createProject();
                  }}
                >
                  <Input
                    value={projectName}
                    onChange={(event) => setProjectName(event.target.value)}
                    placeholder="Workspace name..."
                    className="h-8 text-xs font-mono"
                    aria-label="Project name"
                    autoFocus
                  />
                  <Button
                    type="submit"
                    size="sm"
                    className="h-8 text-xs shrink-0"
                    disabled={!projectName.trim() || busy === "create"}
                  >
                    {busy === "create" ? <Loader2 className="h-3 w-3 animate-spin" /> : "Create"}
                  </Button>
                </form>
              ) : (
                <button
                  type="button"
                  onClick={() => setShowCreate(true)}
                  className="flex items-center gap-1.5 text-xs font-medium text-amber-400 hover:text-amber-300"
                >
                  <Plus className="h-3.5 w-3.5" />
                  <span>Name Workspace</span>
                </button>
              )}
            </div>
          </div>
        </div>

        {/* Architectural Pillars Pillbox */}
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-2.5 rounded-lg border border-border/80 bg-muted/20 p-3">
          <div className="flex items-center gap-2.5 text-xs text-muted-foreground">
            <Globe className="h-4 w-4 shrink-0 text-sky-400" />
            <div>
              <span className="block font-medium text-foreground">StackBlitz WebContainer</span>
              <span className="text-[11px]">Instant client-side Node.js</span>
            </div>
          </div>
          <div className="flex items-center gap-2.5 text-xs text-muted-foreground">
            <Cpu className="h-4 w-4 shrink-0 text-purple-400" />
            <div>
              <span className="block font-medium text-foreground">E2B Firecracker VMs</span>
              <span className="text-[11px]">Remote cloud Linux execution</span>
            </div>
          </div>
          <div className="flex items-center gap-2.5 text-xs text-muted-foreground">
            <Sparkles className="h-4 w-4 shrink-0 text-emerald-400" />
            <div>
              <span className="block font-medium text-foreground">Gemini 2.0 Flash</span>
              <span className="text-[11px]">Sub-350ms streaming TTFT</span>
            </div>
          </div>
        </div>

        {/* Recent Projects Section */}
        <section className="space-y-3">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2 text-sm font-semibold text-foreground">
              <Clock className="h-4 w-4 text-muted-foreground" />
              <span>Recent Workspaces</span>
            </div>
            {recent.length > 0 && (
              <span className="text-xs text-muted-foreground font-mono">
                {recent.length} {recent.length === 1 ? "project" : "projects"} found
              </span>
            )}
          </div>

          {loading ? (
            <div className="flex items-center justify-center gap-2 rounded-lg border border-border p-8 text-sm text-muted-foreground">
              <Loader2 className="h-4 w-4 animate-spin text-primary" />
              <span>Scanning local database...</span>
            </div>
          ) : recent.length ? (
            <div className="overflow-hidden rounded-lg border border-border divide-y divide-border bg-card/40">
              {recent.map((workspace) => (
                <button
                  key={workspace.id}
                  type="button"
                  onClick={() => void selectRecent(workspace)}
                  className="group flex w-full items-center justify-between gap-4 px-4 py-3 text-left transition-colors hover:bg-muted/50 focus-visible:outline-none focus-visible:bg-muted/50"
                >
                  <div className="min-w-0 flex-1">
                    <div className="flex items-center gap-2">
                      <span className="truncate text-sm font-medium text-foreground group-hover:text-primary transition-colors">
                        {workspace.name}
                      </span>
                      {workspace.git_branch && (
                        <span className="rounded bg-muted px-1.5 py-0.5 font-mono text-[10px] text-muted-foreground border border-border/80">
                          {workspace.git_branch}
                        </span>
                      )}
                    </div>
                    <span className="mt-0.5 block font-mono text-[11px] text-muted-foreground">
                      {workspace.source_type || "workspace"} · {workspace.id.slice(0, 8)}
                    </span>
                  </div>
                  <div className="flex items-center gap-2 text-xs text-muted-foreground group-hover:text-foreground">
                    <span className="hidden sm:inline">Open</span>
                    <ArrowRight className="h-4 w-4 shrink-0 transition-transform group-hover:translate-x-1" />
                  </div>
                </button>
              ))}
            </div>
          ) : (
            <div className="rounded-lg border border-dashed border-border p-6 text-center text-sm text-muted-foreground">
              No recent projects yet. Launch one of the templates above to get started.
            </div>
          )}
        </section>
      </div>

      {githubSessionId && (
        <Suspense fallback={null}>
          <GitHubImportDialog
            open
            onClose={() => setGithubSessionId(null)}
            sessionId={githubSessionId}
            onImported={(workspace) => onWorkspaceReady(workspace.id, workspace.name)}
          />
        </Suspense>
      )}
    </div>
  );
}
