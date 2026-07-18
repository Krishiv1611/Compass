import { createContext, useCallback, useContext, useMemo, useState } from "react";

export type LiveRunEvent = {
  id?: string;
  type: string;
  content?: any;
  data?: any;
  tool_call?: any;
  tool_call_id?: string;
  run_id?: string;
  session_id?: string;
  created_at?: string;
};

type RunContextValue = {
  currentRunEvents: LiveRunEvent[];
  currentSessionId: string | null;
  isRunActive: boolean;
  startedAt: string | null;
  startRun: (sessionId: string) => void;
  addEvent: (event: LiveRunEvent) => void;
  finishRun: () => void;
  clearRun: () => void;
};

const RunContext = createContext<RunContextValue | null>(null);

export function RunProvider({ children }: { children: React.ReactNode }) {
  const [currentRunEvents, setCurrentRunEvents] = useState<LiveRunEvent[]>([]);
  const [currentSessionId, setCurrentSessionId] = useState<string | null>(null);
  const [isRunActive, setIsRunActive] = useState(false);
  const [startedAt, setStartedAt] = useState<string | null>(null);

  const startRun = useCallback((sessionId: string) => {
    setCurrentSessionId(sessionId);
    setCurrentRunEvents([]);
    setStartedAt(new Date().toISOString());
    setIsRunActive(true);
  }, []);

  const addEvent = useCallback((event: LiveRunEvent) => {
    if (event.type === "ping" || event.type === "token") return;
    setCurrentRunEvents((prev) => [
      ...prev,
      {
        ...event,
        id: event.id || `${event.type}-${Date.now()}-${prev.length}`,
        created_at: event.created_at || new Date().toISOString(),
      },
    ]);
  }, []);

  const finishRun = useCallback(() => {
    setIsRunActive(false);
  }, []);

  const clearRun = useCallback(() => {
    setCurrentRunEvents([]);
    setCurrentSessionId(null);
    setStartedAt(null);
    setIsRunActive(false);
  }, []);

  const value = useMemo(
    () => ({
      currentRunEvents,
      currentSessionId,
      isRunActive,
      startedAt,
      startRun,
      addEvent,
      finishRun,
      clearRun,
    }),
    [addEvent, clearRun, currentRunEvents, currentSessionId, finishRun, isRunActive, startRun, startedAt]
  );

  return <RunContext.Provider value={value}>{children}</RunContext.Provider>;
}

export function useRunEvents() {
  const value = useContext(RunContext);
  if (!value) throw new Error("useRunEvents must be used inside RunProvider");
  return value;
}
