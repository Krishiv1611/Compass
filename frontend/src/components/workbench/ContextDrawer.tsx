import { useCallback, useEffect, useState } from "react";
import {
  Boxes,
  BrainCircuit,
  CheckSquare,
  Database,
  File,
  FileUp,
  ScrollText,
  Loader2,
  RefreshCcw,
  Sparkles,
  Wrench,
  X,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Sheet, SheetContent, SheetHeader, SheetTitle } from "@/components/ui/sheet";
import { ScrollArea } from "@/components/ui/scroll-area";
import { mcpApi, skillsApi, toolsApi, uploadsApi, workspaceApi } from "@/api";
import { useWorkbench } from "@/contexts/WorkbenchContext";
import type { WorkspaceContext } from "@/types/project";

interface InspectorProps {
  workspaceId: string | null;
  sessionId: string | null;
  selectedFiles: string[];
  compact?: boolean;
}

interface InspectorData {
  context: WorkspaceContext | null;
  uploads: Array<{ id?: string; filename?: string; name?: string }>;
  memories: Array<{ key: string }>;
  tasks: Array<{ id?: string; text: string; done?: boolean }>;
  skills: Array<{ name: string }>;
  tools: Array<{ name: string }>;
  mcpServers: string[];
}

const emptyData: InspectorData = {
  context: null,
  uploads: [],
  memories: [],
  tasks: [],
  skills: [],
  tools: [],
  mcpServers: [],
};

export function ContextInspector({ workspaceId, sessionId, selectedFiles, compact = false }: InspectorProps) {
  const [loading, setLoading] = useState(false);
  const [data, setData] = useState<InspectorData>(emptyData);
  const { state, removeContextFile, refreshBackendContext } = useWorkbench();

  const load = useCallback(async () => {
    setLoading(true);
    const results = await Promise.allSettled([
      workspaceId ? workspaceApi.getContext(workspaceId) : Promise.resolve(null),
      sessionId ? uploadsApi.listUploads(sessionId) : Promise.resolve([]),
      toolsApi.getMemories(),
      toolsApi.getTasks(),
      skillsApi.listSkills(),
      toolsApi.listTools(),
      mcpApi.getMcpServers(),
    ]);
    const value = <T,>(index: number, fallback: T): T =>
      results[index].status === "fulfilled" ? results[index].value as T : fallback;
    const mcp = value<{ mcpServers?: Record<string, unknown> }>(6, {});
    setData({
      context: value<WorkspaceContext | null>(0, null),
      uploads: value(1, []),
      memories: value<{ memories?: InspectorData["memories"] }>(2, {}).memories || [],
      tasks: value(3, []),
      skills: value(4, []),
      tools: value(5, []),
      mcpServers: Object.keys(mcp.mcpServers || {}),
    });
    setLoading(false);
  }, [sessionId, workspaceId]);

  useEffect(() => { void load(); }, [load, state.refreshWorkspaceVersion]);

  const refreshIndex = async () => {
    if (!workspaceId) return;
    setLoading(true);
    try {
      await refreshBackendContext(workspaceId);
      await load();
    } finally {
      setLoading(false);
    }
  };

  const revision = data.context?.git_head?.slice(0, 8)
    || data.context?.context_version?.slice(0, 16)
    || "not indexed";

  return (
    <div className="flex h-full min-h-0 flex-col bg-background">
      <div className="flex h-11 shrink-0 items-center justify-between border-b border-border px-3">
        <div className="min-w-0">
          <div className="truncate text-sm font-semibold">Working context</div>
          <div className="truncate font-mono text-xs text-muted-foreground">
            {data.context?.git_branch ? `${data.context.git_branch} · ` : ""}{revision}
          </div>
        </div>
        <Button variant="ghost" size="icon-sm" onClick={() => void refreshIndex()} disabled={loading} aria-label="Refresh project context" title="Refresh project context">
          <RefreshCcw className={`h-4 w-4 ${loading ? "animate-spin" : ""}`} />
        </Button>
      </div>
      <ScrollArea className="min-h-0 flex-1">
        <div className={compact ? "space-y-4 p-3" : "space-y-6 p-4"}>
          {loading && <div className="flex items-center gap-2 text-xs text-muted-foreground"><Loader2 className="h-4 w-4 animate-spin" /> Updating context</div>}
          <Section icon={File} title="Selected files" count={selectedFiles.length}>
            {selectedFiles.length ? selectedFiles.map((path) => (
              <Row key={path} text={path} mono action={<button type="button" onClick={() => removeContextFile(path)} aria-label={`Remove ${path} from context`} title="Remove from context"><X className="h-3.5 w-3.5" /></button>} />
            )) : <Empty text="Type @ in the composer to add a project file." />}
          </Section>
          <Section icon={Database} title="Project index">
            <Row text={`${data.context?.indexed_file_count ?? 0} files · ${data.context?.indexed_chunk_count ?? 0} chunks`} />
            <Row text={data.context?.context_tokens == null ? "Token usage unavailable from backend" : `${data.context.context_tokens.toLocaleString()} indexed tokens`} />
          </Section>
          <InstructionRows instructions={data.context?.instructions ?? []} />
          <Section icon={CheckSquare} title="Tasks" count={data.tasks.length}>
            {data.tasks.length ? data.tasks.slice(0, 8).map((item) => <Row key={item.id || item.text} text={`${item.done ? "✓" : "○"} ${item.text}`} />) : <Empty text="No active tasks." />}
          </Section>
          <Section icon={FileUp} title="Uploads" count={data.uploads.length}>
            {data.uploads.length ? data.uploads.map((item) => <Row key={item.id || item.filename || item.name} text={item.filename || item.name || "Upload"} />) : <Empty text="No uploaded context." />}
          </Section>
          <Section icon={BrainCircuit} title="Memory" count={data.memories.length}>
            {data.memories.length ? data.memories.slice(0, 5).map((item) => <Row key={item.key} text={item.key} mono />) : <Empty text="No stored memories." />}
          </Section>
          <Section icon={Sparkles} title="Available skills" count={data.skills.length}>
            {data.skills.length ? data.skills.slice(0, 8).map((item) => <Row key={item.name} text={item.name} />) : <Empty text="No skills available." />}
          </Section>
          <Section icon={Boxes} title="Remote capabilities" count={data.mcpServers.length}>
            {data.mcpServers.length ? data.mcpServers.map((name) => <Row key={name} text={name} />) : <Empty text="No approved remote connectors." />}
          </Section>
          <Section icon={Wrench} title="Agent tools" count={data.tools.length}>
            {data.tools.slice(0, 10).map((item) => <Row key={item.name} text={item.name} mono />)}
          </Section>
        </div>
      </ScrollArea>
    </div>
  );
}

export default function ContextDrawer({ open, onOpenChange, workspaceId, sessionId, selectedFiles }: InspectorProps & { open: boolean; onOpenChange: (open: boolean) => void }) {
  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetContent side="right" className="w-full max-w-[410px] gap-0 p-0 sm:max-w-[410px]">
        <SheetHeader className="h-12 shrink-0 justify-center border-b border-border px-4 py-0">
          <SheetTitle className="flex items-center gap-2 text-sm font-semibold"><BrainCircuit className="h-4 w-4 text-primary" /> Context inspector</SheetTitle>
        </SheetHeader>
        <div className="min-h-0 flex-1"><ContextInspector workspaceId={workspaceId} sessionId={sessionId} selectedFiles={selectedFiles} /></div>
      </SheetContent>
    </Sheet>
  );
}

function Section({ icon: Icon, title, count, children }: { icon: React.ComponentType<{ className?: string }>; title: string; count?: number; children: React.ReactNode }) {
  return (
    <section>
      <div className="mb-2 flex items-center gap-2 text-xs font-semibold text-muted-foreground">
        <Icon className="h-3.5 w-3.5" /><span>{title}</span>
        {count !== undefined && <span className="ml-auto font-mono font-normal">{count}</span>}
      </div>
      <div className="divide-y divide-border border-y border-border">{children}</div>
    </section>
  );
}

function Row({ text, mono = false, action }: { text: string; mono?: boolean; action?: React.ReactNode }) {
  return <div className={`flex items-center gap-2 px-1 py-2 text-xs ${mono ? "font-mono" : ""}`} title={text}><span className="min-w-0 flex-1 truncate">{text}</span>{action}</div>;
}

function Empty({ text }: { text: string }) {
  return <div className="px-1 py-3 text-xs text-muted-foreground">{text}</div>;
}

export function InstructionRows({ instructions }: { instructions: NonNullable<WorkspaceContext["instructions"]> }) {
  return (
    <Section icon={ScrollText} title="Project instructions" count={instructions.length}>
      {instructions.length ? instructions.map((item) => (
        <Row
          key={`${item.path}-${item.precedence}`}
          text={`${item.path} · p${item.precedence} · ${item.digest}${item.included ? item.truncated ? " · truncated" : " · included" : " · excluded"}`}
          mono
        />
      )) : <Empty text="No AGENTS.md, CLAUDE.md, GEMINI.md, or COMPASS.md rules loaded." />}
    </Section>
  );
}
