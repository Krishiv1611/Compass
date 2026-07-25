import { useState, useCallback, useEffect } from "react";
import { sessionsApi } from "@/api";
import { toast } from "react-toastify";
import { useAuth } from "@/contexts/AuthContext";
import { useWorkbench } from "@/contexts/WorkbenchContext";

export type SessionSummary = {
  id: string;
  title: string | null;
  updated_at: string;
  message_count: number;
  workspace_name?: string | null;
};

export function useSessions(_activeSessionId: string | null) {
  const { status } = useAuth();
  const { state } = useWorkbench();
  const [sessions, setSessions] = useState<SessionSummary[]>([]);
  const [isLoadingSessions, setIsLoadingSessions] = useState(false);
  const [sessionsPage, setSessionsPage] = useState(1);
  const [hasMoreSessions, setHasMoreSessions] = useState(false);

  const fetchSessions = useCallback(async () => {
    if (status !== "authenticated") {
      setSessions([]);
      return;
    }
    setIsLoadingSessions(true);
    try {
      const data = await sessionsApi.listSessions(1, 20);
      setSessions(data);
      setSessionsPage(1);
      setHasMoreSessions(data.length === 20);
    } catch {
      setSessions([]);
    } finally {
      setIsLoadingSessions(false);
    }
  }, [status]);

  const loadMoreSessions = useCallback(async () => {
    const nextPage = sessionsPage + 1;
    setIsLoadingSessions(true);
    try {
      const data = await sessionsApi.listSessions(nextPage, 20);
      setSessions((prev) => [...prev, ...data]);
      setSessionsPage(nextPage);
      setHasMoreSessions(data.length === 20);
    } catch {
      // ignore
    } finally {
      setIsLoadingSessions(false);
    }
  }, [sessionsPage]);

  useEffect(() => {
    void fetchSessions();
  }, [fetchSessions, state.sessionsVersion]);

  const renameSession = async (id: string, title: string) => {
    try {
      await sessionsApi.renameSession(id, title);
      toast.success("Chat renamed");
      fetchSessions();
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Could not rename task");
    }
  };

  const deleteSession = async (id: string) => {
    try {
      await sessionsApi.deleteSession(id);
      toast.success("Chat deleted");
      fetchSessions();
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Could not delete task");
    }
  };

  return {
    sessions,
    isLoadingSessions,
    hasMoreSessions,
    loadMoreSessions,
    renameSession,
    deleteSession,
    fetchSessions
  };
}
