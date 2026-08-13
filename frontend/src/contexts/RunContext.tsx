import { createContext, useCallback, useContext, useMemo, useRef, useState } from "react";
import type { RunEvent } from "@/types/run";
import type { RunArtifact } from "@/types/artifact";
import { emptyRunArtifact, projectRunEvent } from "@/runtime/projectRunEvent";

export type LiveRunEvent = RunEvent;

interface RunContextValue {
  currentRunEvents: LiveRunEvent[];
  artifact: RunArtifact;
  currentSessionId: string | null;
  isRunActive: boolean;
  startedAt: string | null;
  connection: "ready" | "connecting" | "streaming" | "offline";
  firstEventLatencyMs: number | null;
  startRun: (sessionId: string) => void;
  addEvent: (event: LiveRunEvent) => void;
  hydrateRun: (sessionId: string, events: LiveRunEvent[]) => void;
  finishRun: () => void;
  markFirstToken: () => void;
  setOffline: () => void;
  clearRun: () => void;
}

const RunContext = createContext<RunContextValue | null>(null);

export function RunProvider({ children }: { children: React.ReactNode }) {
  const [currentRunEvents, setCurrentRunEvents] = useState<LiveRunEvent[]>([]);
  const [artifact, setArtifact] = useState<RunArtifact>(emptyRunArtifact);
  const [currentSessionId, setCurrentSessionId] = useState<string | null>(null);
  const [isRunActive, setIsRunActive] = useState(false);
  const [startedAt, setStartedAt] = useState<string | null>(null);
  const [connection, setConnection] = useState<RunContextValue["connection"]>("ready");
  const [firstEventLatencyMs, setFirstEventLatencyMs] = useState<number | null>(null);
  const startedAtMs = useRef<number | null>(null);
  const queue = useRef<LiveRunEvent[]>([]);
  const firstTokenSeen = useRef(false);
  const activeRef = useRef(false);
  const frame = useRef<number | null>(null);

  const flush = useCallback(() => {
    frame.current = null;
    if (!queue.current.length) return;
    const batch = queue.current.splice(0);
    setCurrentRunEvents((previous) => [...previous, ...batch]);
    setArtifact(previous => batch.reduce(projectRunEvent, previous));
  }, []);

  const startRun = useCallback((sessionId: string) => {
    const now = Date.now();
    startedAtMs.current = now;
    firstTokenSeen.current = false;
    activeRef.current = true;
    queue.current = [];
    if (frame.current !== null) window.clearTimeout(frame.current);
    frame.current = null;
    setCurrentSessionId(sessionId);
    setCurrentRunEvents([]);
    setArtifact(emptyRunArtifact());
    setStartedAt(new Date(now).toISOString());
    setFirstEventLatencyMs(null);
    setConnection("connecting");
    setIsRunActive(true);
  }, []);

  const addEvent = useCallback((event: LiveRunEvent) => {
    if (event.type === "ping" || event.type === "token") return;
    setConnection("streaming");
    queue.current.push({
      ...event,
      id: event.id || (event.seq != null ? `${event.type}-${event.seq}` : undefined),
    });
    if (frame.current === null) frame.current = window.setTimeout(flush, 50);
  }, [flush]);

  const markFirstToken = useCallback(() => {
    if (firstTokenSeen.current || startedAtMs.current === null) return;
    firstTokenSeen.current = true;
    setFirstEventLatencyMs(Date.now() - startedAtMs.current);
    setConnection("streaming");
  }, []);

  const finishRun = useCallback(() => {
    flush();
    activeRef.current = false;
    setIsRunActive(false);
    setConnection("ready");
  }, [flush]);
  const setOffline = useCallback(() => {
    activeRef.current = false;
    setIsRunActive(false);
    setConnection("offline");
  }, []);
  const clearRun = useCallback(() => {
    activeRef.current = false;
    queue.current = [];
    if (frame.current !== null) window.clearTimeout(frame.current);
    frame.current = null;
    setCurrentRunEvents([]);
    setArtifact(emptyRunArtifact());
    setCurrentSessionId(null);
    setStartedAt(null);
    setFirstEventLatencyMs(null);
    setConnection("ready");
    setIsRunActive(false);
  }, []);
  const hydrateRun = useCallback((sessionId: string, events: LiveRunEvent[]) => {
    if (activeRef.current) return;
    queue.current = [];
    if (frame.current !== null) window.clearTimeout(frame.current);
    frame.current = null;
    setCurrentSessionId(sessionId);
    setCurrentRunEvents(events);
    setArtifact(events.reduce(projectRunEvent, emptyRunArtifact()));
    setIsRunActive(false);
  }, []);

  const value = useMemo<RunContextValue>(() => ({
    currentRunEvents, artifact, currentSessionId, isRunActive, startedAt, connection,
    firstEventLatencyMs, startRun, addEvent, hydrateRun, markFirstToken, finishRun, setOffline, clearRun,
  }), [
    addEvent, artifact, clearRun, connection, currentRunEvents, currentSessionId,
    finishRun, firstEventLatencyMs, hydrateRun, isRunActive, markFirstToken, setOffline, startRun, startedAt,
  ]);

  return <RunContext.Provider value={value}>{children}</RunContext.Provider>;
}

export function useRunEvents() {
  const value = useContext(RunContext);
  if (!value) throw new Error("useRunEvents must be used inside RunProvider");
  return value;
}
