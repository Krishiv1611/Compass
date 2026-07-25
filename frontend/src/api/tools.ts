import api from "./client";

export const toolsApi = {
  listTools: async () => {
    const response = await api.get("/tools");
    return response.data;
  },
  getTasks: async () => {
    const response = await api.get('/tools/tasks');
    return response.data.tasks;
  },
  getMemories: async () => {
    const response = await api.get('/tools/memory');
    return response.data;
  },
};
