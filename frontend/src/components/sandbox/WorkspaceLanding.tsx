import { useState } from "react";
import { FolderOpen, FolderPlus, Loader2, Layers } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { toast } from "react-toastify";
import { workspaceApi } from "@/api";

interface WorkspaceLandingProps {
  sessionId: string | null;
  ensureSession: (title?: string) => Promise<string>;
  onWorkspaceReady: (workspaceId: string, folderName: string) => void;
  onOpenFolder: () => void;
}

const TECH_STACKS = [
  { label: "React / TypeScript", value: "react-ts" },
  { label: "Python / FastAPI", value: "python-fastapi" },
  { label: "Next.js", value: "nextjs" },
  { label: "Node.js / Express", value: "node-express" },
  { label: "Vue 3", value: "vue3" },
  { label: "Blank", value: "blank" },
];

export default function WorkspaceLanding({
  ensureSession,
  onWorkspaceReady,
  onOpenFolder,
}: WorkspaceLandingProps) {
  const [projectName, setProjectName] = useState("");
  const [techStack, setTechStack] = useState("blank");
  const [isCreating, setIsCreating] = useState(false);

  const handleCreate = async () => {
    if (!projectName.trim()) {
      toast.error("Enter a project name.");
      return;
    }
    setIsCreating(true);
    try {
      const sid = await ensureSession(projectName.trim());
      const ws = await workspaceApi.createWorkspace(sid, projectName.trim());
      toast.success(`Workspace "${projectName.trim()}" created`);
      onWorkspaceReady(ws.id, projectName.trim());
    } catch (err: any) {
      toast.error(err?.response?.data?.detail || "Could not create workspace");
    } finally {
      setIsCreating(false);
    }
  };

  return (
    <div className="flex h-full flex-col items-center justify-center gap-6 p-8">
      <div className="mb-2 text-center">
        <div className="mx-auto mb-3 flex size-12 items-center justify-center rounded-xl bg-primary/10 text-primary">
          <Layers className="h-6 w-6" />
        </div>
        <h2 className="text-base font-semibold">Open a workspace</h2>
        <p className="mt-1 text-xs text-muted-foreground max-w-xs">
          Upload an existing project or create a fresh one for the agent to work in.
        </p>
      </div>

      <div className="grid w-full max-w-sm gap-3 sm:grid-cols-2">
        {/* Upload card */}
        <button
          onClick={onOpenFolder}
          className="flex flex-col items-center gap-3 rounded-xl border border-border bg-card p-5 text-center transition-colors duration-150 hover:border-primary/50 hover:bg-primary/5 focus-visible:ring-2 focus-visible:ring-primary/40"
        >
          <div className="flex size-10 items-center justify-center rounded-lg bg-primary/10 text-primary">
            <FolderOpen className="h-5 w-5" />
          </div>
          <div>
            <div className="text-sm font-medium">Upload Existing Project</div>
            <div className="mt-0.5 text-xs text-muted-foreground">
              Select a local folder to upload
            </div>
          </div>
        </button>

        {/* Create card */}
        <div className="flex flex-col items-start gap-3 rounded-xl border border-border bg-card p-5 transition-colors duration-150 hover:border-primary/50 hover:bg-primary/5">
          <div className="flex size-10 items-center justify-center rounded-lg bg-accent/10 text-accent">
            <FolderPlus className="h-5 w-5" />
          </div>
          <div className="w-full">
            <div className="text-sm font-medium mb-2">Create New Project</div>
            <Input
              placeholder="Project name"
              value={projectName}
              onChange={(e) => setProjectName(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && handleCreate()}
              className="h-8 text-xs mb-2 focus-visible:ring-2 focus-visible:ring-primary/40"
            />
            <select
              value={techStack}
              onChange={(e) => setTechStack(e.target.value)}
              className="h-8 w-full rounded-md border border-input bg-background px-2 text-xs text-foreground outline-none focus:border-ring focus:ring-2 focus:ring-ring/30 mb-3"
            >
              {TECH_STACKS.map((s) => (
                <option key={s.value} value={s.value}>
                  {s.label}
                </option>
              ))}
            </select>
            <Button
              size="sm"
              className="w-full h-8 text-xs"
              onClick={handleCreate}
              disabled={isCreating || !projectName.trim()}
            >
              {isCreating ? (
                <Loader2 className="h-3.5 w-3.5 animate-spin mr-1" />
              ) : (
                <FolderPlus className="h-3.5 w-3.5 mr-1" />
              )}
              Create
            </Button>
          </div>
        </div>
      </div>
    </div>
  );
}

