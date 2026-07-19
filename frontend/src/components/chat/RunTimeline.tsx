import { useEffect, useMemo, useRef, useState } from "react";
import { runsApi } from "@/api";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Badge } from "@/components/ui/badge";
import {
  Activity,
  AlertTriangle,
  CheckCircle2,
  Circle,
  Clock,
  FilePenLine,
  FileText,
  Loader2,
  Search,
  Terminal,
  Wifi,
  Wrench,
  XCircle,
} from "lucide-react";
import { formatDistanceToNow } from "date-fns";
import { useRunEvents } from "@/contexts/RunContext";
import type { LiveRunEvent } from "@/contexts/RunContext";

function sumTokenUsage(value: any): number | null {
  if (!value) return null;
  if (typeof value === "number") return value;
  if (typeof value !== "object") return null;
  const direct = value.total_tokens ?? value.totalTokens ?? value.total ?? value.tokens;
  if (typeof direct === "number") return direct;
  const numbers = Object.values(value).filter((item): item is number => typeof item === "number");
  return numbers.length ? numbers.reduce((total, item) => total + item, 0) : null;
}

function formatTokenUsage(value: any): string | null {
  const total = sumTokenUsage(value);
  return total == null ? null : `${total.toLocaleString()} tokens`;
}

function eventPayload(event: any) {
  return event.content && typeof event.content === "object" ? event.content : event;
}

function toolName(event: any): string {
  const payload = eventPayload(event);
  return payload.tool_call?.name || event.tool_call?.name || payload.name || "tool";
}

function toolArgs(event: any): any {
  const payload = eventPayload(event);
  return payload.tool_call?.args || event.tool_call?.args || payload.args || event.data || {};
}

function eventLabel(event: LiveRunEvent) {
  const name = toolName(event);
  const args = toolArgs(event);
  
  // Safely extract string content if event.content is an object (due to DB serialization)
  const safeContentString = event.content 
    ? (typeof event.content === "string" ? event.content : event.content.content || JSON.stringify(event.content))
    : "";

  if (event.type === "approval_required") return { icon: AlertTriangle, label: "Scroll to approve", tone: "text-destructive" };
  if (event.type === "loop_detected") return { icon: AlertTriangle, label: `Retrying (attempt ${event.data?.loop_count || 1}/3)`, tone: "text-muted-foreground" };
  if (event.type === "done") return { icon: CheckCircle2, label: "Completed", tone: "text-primary" };
  if (event.type === "error") return { icon: XCircle, label: safeContentString || "Error", tone: "text-destructive" };
  if (event.type === "plan_created") return { icon: Circle, label: "Plan created", tone: "text-primary" };
  if (event.type === "tool_result") return { icon: CheckCircle2, label: "Tool completed", tone: "text-muted-foreground" };
  if (name === "read_file") return { icon: FileText, label: `Reading: ${args.path || args.file_path || "file"}`, tone: "text-foreground" };
  if (name === "write_to_file") return { icon: FilePenLine, label: `Writing: ${args.path || "file"}`, tone: "text-foreground" };
  if (name === "edit_file") return { icon: FilePenLine, label: `Editing: ${args.path || "file"}`, tone: "text-foreground" };
  if (name === "shell_execute") return { icon: Terminal, label: `Running: ${args.command || "command"}`, tone: "text-foreground" };
  if (name === "web_search") return { icon: Wifi, label: `Searching: ${args.query || "web"}`, tone: "text-foreground" };
  if (name === "grep_search") return { icon: Search, label: `Searching: ${args.pattern || args.query || "workspace"}`, tone: "text-foreground" };
  return { icon: Wrench, label: event.type === "tool_call" ? `Using: ${name}` : event.type, tone: "text-muted-foreground" };
}

function EventRow({ event }: { event: LiveRunEvent }) {
  const meta = eventLabel(event);
  const Icon = meta.icon;
  return (
    <div className="relative flex items-start gap-3">
      <div className="absolute -left-[3px] top-1.5 h-2 w-2 rounded-full border-2 border-card bg-primary/40 ring-1 ring-border" />
      <div className="flex-1 rounded-md bg-muted/40 p-2 text-xs">
        <div className={`flex items-center gap-1 font-semibold ${meta.tone}`}>
          <Icon className="h-3 w-3" /> {meta.label}
        </div>
        {event.type === "tool_call" && Object.keys(toolArgs(event)).length > 0 && (
          <div className="mt-1 overflow-x-auto rounded-md bg-card border border-border/50 p-2 font-mono text-[10px] text-muted-foreground shadow-sm">
            {JSON.stringify(toolArgs(event), null, 2)}
          </div>
        )}
        {event.type === "tool_result" && event.content && (
          <div className="mt-1 line-clamp-3 overflow-hidden rounded-md bg-card border border-border/50 p-2 font-mono text-[10px] text-muted-foreground shadow-sm">
            {typeof event.content === "string" ? event.content : event.content?.content}
          </div>
        )}
      </div>
    </div>
  );
}

export default function RunTimeline({ sessionId }: { sessionId: string | null }) {
  const [runs, setRuns] = useState<any[]>([]);
  const [loading, setLoading] = useState(false);
  const bottomRef = useRef<HTMLDivElement | null>(null);
  const { currentRunEvents, currentSessionId, isRunActive, startedAt } = useRunEvents();

  const loadRuns = async (activeSessionId: string) => {
    setLoading(true);
    try {
      setRuns(await runsApi.getSessionRuns(activeSessionId));
    } catch (err) {
      console.error("Failed to load runs", err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (!sessionId) {
      setRuns([]);
      return;
    }
    loadRuns(sessionId);
    const refresh = () => loadRuns(sessionId);
    window.addEventListener("agent-done", refresh);
    return () => window.removeEventListener("agent-done", refresh);
  }, [sessionId]);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [currentRunEvents.length, runs.length]);

  const liveRun = useMemo(() => {
    if (!sessionId || currentSessionId !== sessionId || currentRunEvents.length === 0) return null;
    return {
      id: currentRunEvents.find((event) => event.run_id)?.run_id || "live",
      status: isRunActive ? "running" : "completed",
      started_at: startedAt || currentRunEvents[0]?.created_at || new Date().toISOString(),
      ended_at: isRunActive ? null : currentRunEvents[currentRunEvents.length - 1]?.created_at,
      token_usage: null,
      events: currentRunEvents,
      live: true,
    };
  }, [currentRunEvents, currentSessionId, isRunActive, sessionId, startedAt]);

  const visibleRuns = liveRun ? [liveRun, ...runs.filter((run) => run.id !== liveRun.id)] : runs;

  if (!sessionId) {
    return <div className="flex h-full items-center justify-center p-4 text-center text-sm text-muted-foreground">No active session to display runs.</div>;
  }

  if (loading && visibleRuns.length === 0) {
    return <div className="flex h-full items-center justify-center text-muted-foreground"><Loader2 className="mr-2 h-5 w-5 animate-spin" />Loading runs...</div>;
  }

  if (visibleRuns.length === 0) {
    return <div className="flex h-full items-center justify-center p-4 text-center text-sm text-muted-foreground">No runs found for this session yet.</div>;
  }

  return (
    <ScrollArea className="h-full">
      <div className="flex flex-col gap-4 p-4">
        {visibleRuns.map((run) => {
          const tokenLabel = formatTokenUsage(run.token_usage);
          return (
            <div key={run.id} className="rounded-lg border border-border bg-card p-4 shadow-sm">
              <div className="mb-3 flex items-center justify-between border-b border-border/50 pb-2">
                <div className="flex items-center gap-2 font-medium">
                  <Activity className="h-4 w-4 text-primary" />
                  Run <span className="font-mono text-xs text-muted-foreground">{String(run.id).slice(0, 8)}</span>
                  {run.live && <span className="h-2 w-2 rounded-full bg-green-500 animate-pulse" title="Live" />}
                </div>
                <div className="flex items-center gap-2">
                  {tokenLabel && <Badge variant="outline" className="text-muted-foreground">{tokenLabel}</Badge>}
                  {run.status === "completed" && <Badge variant="outline" className="border-primary/30 bg-primary/10 text-primary"><CheckCircle2 className="mr-1 h-3 w-3" />Completed</Badge>}
                  {run.status === "error" && <Badge variant="outline" className="border-destructive/30 bg-destructive/10 text-destructive"><XCircle className="mr-1 h-3 w-3" />Error</Badge>}
                  {run.status === "running" && <Badge variant="outline" className="border-primary/30 bg-primary/10 text-primary"><Loader2 className="mr-1 h-3 w-3 animate-spin" />Running</Badge>}
                </div>
              </div>

              <div className="mb-4 flex items-center gap-1 text-xs text-muted-foreground">
                <Clock className="h-3 w-3" />
                {formatDistanceToNow(new Date(run.started_at), { addSuffix: true })}
                {run.ended_at && ` - duration ${((new Date(run.ended_at).getTime() - new Date(run.started_at).getTime()) / 1000).toFixed(1)}s`}
              </div>

              <div className="relative flex flex-col gap-2 pl-3 before:absolute before:inset-y-0 before:left-[5px] before:w-px before:bg-border">
                {run.events.filter((event: any) => event.type !== "token").map((event: any) => <EventRow key={event.id} event={event} />)}
                {run.events.filter((event: any) => event.type !== "token").length === 0 && <div className="pl-3 text-xs italic text-muted-foreground">No significant events recorded.</div>}
              </div>
            </div>
          );
        })}
        <div ref={bottomRef} />
      </div>
    </ScrollArea>
  );
}

