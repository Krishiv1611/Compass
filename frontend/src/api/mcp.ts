import api from "./client";

export const mcpApi = {
  getMcpServers: async () => (await api.get("/settings/mcp-servers")).data,
};