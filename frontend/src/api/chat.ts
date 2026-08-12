import api, { buildWebSocketProtocols, buildWebSocketUrl } from "./client";
import type { ChatMode } from "@/types/chat";

export const chatApi = {
  sendMessage: async (
    sessionId: string,
    content: string,
    mode: ChatMode = "edit",
    contextFiles: string[] = [],
  ) => {
    const response = await api.post("/chat/send", {
      session_id: sessionId,
      content,
      mode,
      context_files: contextFiles,
    });
    return response.data;
  },
  createWebSocket: (sessionId: string) => {
    return new WebSocket(
      buildWebSocketUrl(sessionId),
      buildWebSocketProtocols(),
    );
  },
};
