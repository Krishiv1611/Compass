import { createContext, useCallback, useContext, useMemo, useRef, useState } from "react";
import type { RunEvent } from "@/types/run";

export type LiveRunEvent = RunEvent;

interface RunContextValue {
  currentRunEvents: LiveRunEvent[];
  currentSessionId: string | null;
  isRunActive: boolean;
  startedAt: string | null;
  connection: "ready" | "connecting" | "streaming" | "offline";
  firstEventLatencyMs: number | null;
  startRun: (sessionId: string) => void;
  addEvent: (event: LiveRunEvent) => void;
  finishRun: () => void;
  markFirstToken: () => void;
  setOffline: () => void;
  clearRun: () => void;
}

const RunContext = createContext<RunContextValue | null>(null);

export function RunProvider({ children }: { children: React.ReactNode }) {
  const [currentRunEvents, setCurrentRunEvents] = useState<LiveRunEvent[]>([]);
  const [currentSessionId, setCurrentSessionId] = useState<string | null>(null);
  const [isRunActive, setIsRunActive] = useState(false);
  const [startedAt, setStartedAt] = useState<string | null>(null);
  const [connection, setConnection] = useState<RunContextValue["connection"]>("ready");
  const [firstEventLatencyMs, setFirstEventLatencyMs] = useState<number | null>(null);
  const startedAtMs = useRef<number | null>(null);
  const queue = useRef<LiveRunEvent[]>([]);
  const firstTokenSeen = useRef(false);
  const frame = useRef<number | null>(null);

  const flush = useCallback(() => {
    frame.current = null;
    if (!queue.current.length) return;
    const batch = queue.current.splice(0);
    setCurrentRunEvents((previous) => [...previous, ...batch]);
  }, []);
    firstTokenSeen.current = false;

  const startRun = useCallback((sessionId: string) => {
    const now = Date.now();
    startedAtMs.current = now;
    setCurrentSessionId(sessionId);
    setCurrentRunEvents([]);
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
      id: event.id || `${event.type}-${Date.now()}-${queue.current.length}`,
      created_at: event.created_at || new Date().toISOString(),
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
    setIsRunActive(false);
    setConnection("ready");
  }, [flush]);
  const setOffline = useCallback(() => {
    setIsRunActive(false);
    setConnection("offline");
  }, []);
  const clearRun = useCallback(() => {
    queue.current = [];
    if (frame.current !== null) window.clearTimeout(frame.current);
    frame.current = null;
    setCurrentRunEvents([]);
    setCurrentSessionId(null);
    setStartedAt(null);
    setFirstEventLatencyMs(null);
    setConnection("ready");
    setIsRunActive(false);
  }, []);

  const value = useMemo<RunContextValue>(() => ({
    currentRunEvents, currentSessionId, isRunActive, startedAt, connection,
    firstEventLatencyMs, startRun, addEvent, markFirstToken, finishRun, setOffline, clearRun,
  }), [
    addEvent, clearRun, connection, currentRunEvents, currentSessionId,
    finishRun, firstEventLatencyMs, isRunActive, markFirstToken, setOffline, startRun, startedAt,
  ]);

  return <RunContext.Provider value={value}>{children}</RunContext.Provider>;
}

export function useRunEvents() {
  const value = useContext(RunContext);
  if (!value) throw new Error("useRunEvents must be used inside RunProvider");
  return value;
}
