import type { RunEvent } from "@/types/run";

type SessionMessage = {
  id: string;
  role: string;
  content?: string | null;
  created_at?: string;
  tool_calls?: Record<string, unknown> | null;
};


export function projectSessionFork(messages: SessionMessage[]): {
  messages: SessionMessage[];
  event: RunEvent | null;
} {
  const forkMessage = messages.find(
    (message) =>
      message.role === "system" &&
      message.tool_calls?.event === "session_forked",
  );
  if (!forkMessage) return { messages, event: null };

  const sourceSessionId = forkMessage.tool_calls?.source_session_id;
  const checkpointId = forkMessage.tool_calls?.checkpoint_id;
  return {
    messages: messages.filter((message) => message.id !== forkMessage.id),
    event: {
      id: forkMessage.id,
      type: "session_forked",
      content: "Forked task",
      created_at: forkMessage.created_at,
      data: {
        source_session_id:
          typeof sourceSessionId === "string" ? sourceSessionId : "unknown",
        checkpoint_id: typeof checkpointId === "string" ? checkpointId : null,
      },
    },
  };
}


export function mergeSessionTimelineEvents(
  durableEvents: RunEvent[],
  incomingEvents: RunEvent[],
): RunEvent[] {
  const merged = [
    ...durableEvents.filter((event) => event.type === "session_forked"),
    ...incomingEvents,
  ];
  const seen = new Set<string>();
  return merged.filter((event) => {
    const key = event.id || `${event.type}:${event.created_at || ""}`;
    if (seen.has(key)) return false;
    seen.add(key);
    return true;
  });
}
