import { useEffect, useMemo, useRef, useState } from "react";
import {
  Activity,
  ArrowLeft,
  Bot,
  Boxes,
  BrainCircuit,
  Download,
  FileCode2,
  FileSearch,
  FolderSearch,
  GitPullRequest,
  HelpCircle,
  History,
  Layers3,
  ListTree,
  Search,
  Settings2,
  Sparkles,
  Target,
} from "lucide-react";
import { Input } from "@/components/ui/input";
import { Dialog } from "@base-ui/react/dialog";
import { workspaceApi } from "@/api";
import type { ChatMode } from "@/types/chat";
import { useWorkbench } from "@/contexts/WorkbenchContext";

type PaletteView = "commands" | "files" | "modes";

type Command = {
  id: string;
  label: string;
  hint: string;
  icon: React.ComponentType<{ className?: string }>;
  run: () => void;
};

interface CommandPaletteProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onContext: () => void;
  workspaceId: string | null;
}

const modeCommands: Array<{
  mode: ChatMode;
  label: string;
  hint: string;
  icon: React.ComponentType<{ className?: string }>;
}> = [
  { mode: "ask", label: "Ask", hint: "Read and explain without editing", icon: HelpCircle },
  { mode: "edit", label: "Edit", hint: "Work directly with project tools", icon: FileCode2 },
  { mode: "plan", label: "Plan", hint: "Propose a plan and wait for approval", icon: ListTree },
  { mode: "goal", label: "Goal", hint: "Work autonomously; risky actions still require approval", icon: Target },
];

export default function CommandPalette({
  open,
  onOpenChange,
  onContext,
  workspaceId,
}: CommandPaletteProps) {
  const {
    openFile,
    openChanges,
    openActivity,
    openSettings,
    refreshBackendContext,
    setMode,
    dispatch,
  } = useWorkbench();
  const [query, setQuery] = useState("");
  const [selected, setSelected] = useState(0);
  const [view, setView] = useState<PaletteView>("commands");
  const [files, setFiles] = useState<string[]>([]);
  const [loadingFiles, setLoadingFiles] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);

  const showView = (next: PaletteView) => {
    setView(next);
    setQuery("");
    setSelected(0);
  };

  const commands = useMemo<Command[]>(() => [
    { id: "open", label: "Open file", hint: "Find a project file by name or path", icon: FileSearch, run: () => showView("files") },
    { id: "search", label: "Browse project", hint: "Open the workspace file tree", icon: FolderSearch, run: () => dispatch({ type: "setMobileDestination", destination: "files" }) },
    { id: "review", label: "Review changes", hint: "Open consolidated patch review", icon: GitPullRequest, run: () => openChanges() },
    { id: "checkpoints", label: "Snapshots & rollback", hint: "Browse and restore workspace checkpoints", icon: History, run: () => dispatch({ type: "setCenterTab", tab: "checkpoints" }) },
    { id: "download", label: "Export project (ZIP)", hint: "Download current project files as an archive", icon: Download, run: () => { if (workspaceId) void workspaceApi.downloadWorkspace(workspaceId); } },
    { id: "mode", label: "Change mode", hint: "Choose Ask, Edit, Plan, or Goal", icon: ListTree, run: () => showView("modes") },
    { id: "model", label: "Change model", hint: "Open model preferences", icon: Bot, run: () => openSettings("model") },
    { id: "index", label: "Refresh project index", hint: "Update revision and retrieval context", icon: Layers3, run: () => { if (workspaceId) void refreshBackendContext(workspaceId); } },
    { id: "context", label: "Inspect context", hint: "Files, uploads, memory, skills, and tools", icon: BrainCircuit, run: onContext },
    { id: "skills", label: "Choose skills", hint: "Inspect skills available to this task", icon: Sparkles, run: onContext },
    { id: "mcp", label: "View connectors", hint: "Inspect approved remote capabilities", icon: Boxes, run: onContext },
    { id: "settings", label: "Open settings", hint: "Account, model, appearance, and advanced", icon: Settings2, run: () => openSettings() },
    { id: "activity", label: "Open run activity", hint: "Inspect stages, duration, tools, and files", icon: Activity, run: openActivity },
  ], [dispatch, onContext, openActivity, openChanges, openSettings, refreshBackendContext, workspaceId]);

  useEffect(() => {
    if (!open) return;
    setQuery("");
    setSelected(0);
    setView("commands");
    window.setTimeout(() => inputRef.current?.focus(), 0);
  }, [open]);

  useEffect(() => {
    if (!open || view !== "files" || !workspaceId) {
      setFiles([]);
      return;
    }
    let cancelled = false;
    const timer = window.setTimeout(async () => {
      setLoadingFiles(true);
      try {
        const results = await workspaceApi.searchFiles(workspaceId, query, 50);
        if (!cancelled) setFiles(results);
      } catch {
        if (!cancelled) setFiles([]);
      } finally {
        if (!cancelled) setLoadingFiles(false);
      }
    }, 100);
    return () => {
      cancelled = true;
      window.clearTimeout(timer);
    };
  }, [open, query, view, workspaceId]);

  const visibleCommands = view === "commands"
    ? commands.filter((command) =>
        `${command.label} ${command.hint}`.toLowerCase().includes(query.toLowerCase())
      )
    : view === "modes"
      ? modeCommands
          .filter((item) => `${item.label} ${item.hint}`.toLowerCase().includes(query.toLowerCase()))
          .map<Command>((item) => ({
            id: item.mode,
            label: item.label,
            hint: item.hint,
            icon: item.icon,
            run: () => setMode(item.mode),
          }))
      : files.map<Command>((path) => ({
          id: path,
          label: path.split("/").pop() || path,
          hint: path,
          icon: FileCode2,
          run: () => openFile({ path, name: path.split("/").pop() || path, type: "file" }),
        }));

  useEffect(() => {
    if (selected >= visibleCommands.length) setSelected(0);
  }, [selected, visibleCommands.length]);

  if (!open) return null;

  const execute = (command: Command) => {
    if ((command.id === "open" || command.id === "mode") && view === "commands") {
      command.run();
      return;
    }
    onOpenChange(false);
    command.run();
  };

  const goBack = () => {
    setView("commands");
    setQuery("");
    setSelected(0);
  };

  const title = view === "files" ? "Open file" : view === "modes" ? "Choose mode" : "Search commands";

  return (
    <Dialog.Root open={open} onOpenChange={onOpenChange}>
      <Dialog.Portal>
        <Dialog.Backdrop className="fixed inset-0 z-[100] bg-black/45 transition-opacity duration-150 data-ending-style:opacity-0 data-starting-style:opacity-0" />
        <Dialog.Popup aria-labelledby="command-palette-title" className="fixed left-1/2 top-[10vh] z-[101] w-[calc(100%-24px)] max-w-xl -translate-x-1/2 overflow-hidden rounded-md border border-border bg-popover shadow-[var(--shadow-lg)] outline-none transition duration-150 data-ending-style:scale-[0.98] data-ending-style:opacity-0 data-starting-style:scale-[0.98] data-starting-style:opacity-0 sm:top-[12vh]">
          <Dialog.Title id="command-palette-title" className="sr-only">{title}</Dialog.Title>
        <div className="flex items-center gap-2 border-b border-border px-3">
          {view === "commands" ? (
            <Search className="h-4 w-4 text-muted-foreground" />
          ) : (
            <button type="button" onClick={goBack} className="rounded p-1 text-muted-foreground hover:bg-accent hover:text-foreground" title="Back to commands">
              <ArrowLeft className="h-4 w-4" />
            </button>
          )}
          <Input
            ref={inputRef}
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            onKeyDown={(event) => {
              if (event.key === "Escape") {
                if (view === "commands") onOpenChange(false);
                else goBack();
              }
              if (event.key === "ArrowDown") {
                event.preventDefault();
                setSelected((value) => Math.min(value + 1, visibleCommands.length - 1));
              }
              if (event.key === "ArrowUp") {
                event.preventDefault();
                setSelected((value) => Math.max(value - 1, 0));
              }
              if (event.key === "Enter" && visibleCommands[selected]) execute(visibleCommands[selected]);
            }}
            placeholder={title}
            className="h-12 border-0 bg-transparent px-0 shadow-none focus-visible:ring-0"
          />
          <kbd className="rounded border border-border bg-muted px-1.5 py-0.5 text-xs text-muted-foreground">Esc</kbd>
        </div>
        <div className="max-h-[min(430px,65vh)] overflow-y-auto p-1.5">
          {view === "files" && !workspaceId ? (
            <div className="px-3 py-10 text-center text-sm text-muted-foreground">Open a project before searching files.</div>
          ) : loadingFiles ? (
            <div className="px-3 py-10 text-center text-sm text-muted-foreground">Searching project files…</div>
          ) : visibleCommands.length === 0 ? (
            <div className="px-3 py-10 text-center text-sm text-muted-foreground">No matching {view === "files" ? "files" : "commands"}.</div>
          ) : visibleCommands.map((command, index) => {
            const Icon = command.icon;
            return (
              <button
                key={command.id}
                type="button"
                onMouseEnter={() => setSelected(index)}
                onClick={() => execute(command)}
                className={`flex w-full items-center gap-3 rounded px-3 py-2.5 text-left ${selected === index ? "bg-accent text-accent-foreground" : "text-foreground"}`}
              >
                <Icon className="h-4 w-4 shrink-0 text-muted-foreground" />
                <span className="min-w-0 flex-1">
                  <span className="block text-sm font-medium">{command.label}</span>
                  <span className="block truncate text-xs text-muted-foreground">{command.hint}</span>
                </span>
              </button>
            );
          })}
        </div>
        </Dialog.Popup>
      </Dialog.Portal>
    </Dialog.Root>
  );
}
