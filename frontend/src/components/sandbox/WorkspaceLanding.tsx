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
import { motion } from "framer-motion";
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
    <div className="h-full overflow-y-auto bg-[#080A0E] px-6 py-10 sm:px-10">
      <div className="mx-auto max-w-3xl space-y-8">
        {/* Header title */}
        <div>
          <div className="flex items-center gap-2 mb-2">
            <span className="flex size-6 items-center justify-center rounded-md bg-sky-500/10 text-sky-400 border border-sky-500/25">
              <Sparkles className="h-3.5 w-3.5" />
            </span>
            <span className="text-xs font-mono uppercase tracking-wider text-sky-400 font-semibold">Studio Launchpad</span>
          </div>
          <h1 className="text-xl font-bold tracking-tight text-foreground sm:text-2xl">
            New Workspace
          </h1>
          <p className="mt-1 text-xs sm:text-sm text-muted-foreground leading-relaxed">
            Initialize an isolated project sandbox from a template, connect an existing GitHub repository, or open local code.
          </p>
        </div>

        {/* 4 Launchpad Action Cards */}
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
          {/* Card 1: 1-Click Starter Web App */}
          <motion.button
            type="button"
            whileHover={{ y: -3, scale: 1.01 }}
            whileTap={{ scale: 0.99 }}
            onClick={() => void createStarterApp()}
            disabled={busy === "starter"}
            className="group relative flex flex-col justify-between rounded-xl border border-border/80 bg-[#0D1117]/80 p-5 text-left transition-all hover:border-sky-500/60 hover:bg-[#131822] hover:shadow-[0_0_24px_rgba(56,189,248,0.12)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-sky-500"
          >
            <div>
              <div className="flex items-center justify-between">
                <span className="flex h-10 w-10 items-center justify-center rounded-lg bg-sky-500/15 text-sky-400 border border-sky-500/30">
                  <Globe className="h-5 w-5" />
                </span>
                <span className="rounded-full bg-sky-500/15 px-2.5 py-0.5 font-mono text-[10px] font-semibold text-sky-400 border border-sky-500/30">
                  Vite + React
                </span>
              </div>
              <h2 className="mt-3.5 text-sm font-semibold text-foreground group-hover:text-sky-400 transition-colors">
                React + Vite Starter
              </h2>
              <p className="mt-1 text-xs text-muted-foreground leading-relaxed">
                Full-stack web application with Vite, Tailwind CSS, live Canvas preview, and DOM element inspection.
              </p>
            </div>
            <div className="mt-4 flex items-center gap-1.5 text-xs font-medium text-sky-400">
              {busy === "starter" ? (
                <>
                  <Loader2 className="h-3.5 w-3.5 animate-spin" />
                  <span>Creating workspace...</span>
                </>
              ) : (
                <>
                  <span>Launch Template</span>
                  <ArrowRight className="h-3.5 w-3.5 transition-transform group-hover:translate-x-1" />
                </>
              )}
            </div>
          </motion.button>

          {/* Card 2: Import from GitHub */}
          <motion.button
            type="button"
            whileHover={{ y: -3, scale: 1.01 }}
            whileTap={{ scale: 0.99 }}
            onClick={() => void openGitHub()}
            className="group relative flex flex-col justify-between rounded-xl border border-border/80 bg-[#0D1117]/80 p-5 text-left transition-all hover:border-purple-500/60 hover:bg-[#131822] hover:shadow-[0_0_24px_rgba(168,85,247,0.12)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-purple-500"
          >
            <div>
              <div className="flex items-center justify-between">
                <span className="flex h-10 w-10 items-center justify-center rounded-lg bg-purple-500/15 text-purple-400 border border-purple-500/30">
                  <GitFork className="h-5 w-5" />
                </span>
                <span className="rounded-full bg-muted/60 px-2.5 py-0.5 font-mono text-[10px] text-muted-foreground border border-border">
                  GitHub
                </span>
              </div>
              <h2 className="mt-3.5 text-sm font-semibold text-foreground group-hover:text-purple-400 transition-colors">
                Import from GitHub
              </h2>
              <p className="mt-1 text-xs text-muted-foreground leading-relaxed">
                Clone repositories with branch tracking, pull request opening, and staged commit reviews.
              </p>
            </div>
            <div className="mt-4 flex items-center gap-1.5 text-xs font-medium text-purple-400">
              <span>Select Repository</span>
              <ArrowRight className="h-3.5 w-3.5 transition-transform group-hover:translate-x-1" />
            </div>
          </motion.button>

          {/* Card 3: Upload Local Folder */}
          <motion.button
            type="button"
            whileHover={{ y: -3, scale: 1.01 }}
            whileTap={{ scale: 0.99 }}
            onClick={() => folderInput.current?.click()}
            disabled={busy === "upload"}
            className="group relative flex flex-col justify-between rounded-xl border border-border/80 bg-[#0D1117]/80 p-5 text-left transition-all hover:border-emerald-500/60 hover:bg-[#131822] hover:shadow-[0_0_24px_rgba(16,185,129,0.12)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-emerald-500"
          >
            <div>
              <div className="flex items-center justify-between">
                <span className="flex h-10 w-10 items-center justify-center rounded-lg bg-emerald-500/15 text-emerald-400 border border-emerald-500/30">
                  <FolderUp className="h-5 w-5" />
                </span>
                <span className="rounded-full bg-muted/60 px-2.5 py-0.5 font-mono text-[10px] text-muted-foreground border border-border">
                  Local
                </span>
              </div>
              <h2 className="mt-3.5 text-sm font-semibold text-foreground group-hover:text-emerald-400 transition-colors">
                Upload Project Folder
              </h2>
              <p className="mt-1 text-xs text-muted-foreground leading-relaxed">
                Import project files directly from your disk into an isolated workspace with live sync.
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
          </motion.button>
          <input
            ref={folderInput}
            type="file"
            multiple
            className="sr-only"
            onChange={(event) => void uploadFolder(event.target.files)}
            {...({ webkitdirectory: "", directory: "" } as React.InputHTMLAttributes<HTMLInputElement>)}
          />

          {/* Card 4: Empty / Custom Project */}
          <motion.div
            whileHover={{ y: -3, scale: 1.01 }}
            className="group relative flex flex-col justify-between rounded-xl border border-border/80 bg-[#0D1117]/80 p-5 text-left transition-all hover:border-amber-500/60 hover:bg-[#131822] hover:shadow-[0_0_24px_rgba(245,158,11,0.12)]"
          >
            <div>
              <div className="flex items-center justify-between">
                <span className="flex h-10 w-10 items-center justify-center rounded-lg bg-amber-500/15 text-amber-400 border border-amber-500/30">
                  <Terminal className="h-5 w-5" />
                </span>
                <span className="rounded-full bg-muted/60 px-2.5 py-0.5 font-mono text-[10px] text-muted-foreground border border-border">
                  Blank
                </span>
              </div>
              <h2 className="mt-3.5 text-sm font-semibold text-foreground">
                Blank Studio Workspace
              </h2>
              <p className="mt-1 text-xs text-muted-foreground leading-relaxed">
                Start with a clean slate for backend Python/FastAPI services, CLI tools, or automated scripts.
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
                    className="h-8 text-xs font-mono bg-background/80"
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
          </motion.div>
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
              <span>Loading workspaces...</span>
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
