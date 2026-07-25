import api from "./client";

export const preferencesApi = {
  getSettings: async () => {
    const response = await api.get("/settings");
    return response.data;
  },
  updateSettings: async (data: Record<string, unknown>) => {
    const response = await api.put("/settings", data);
    return response.data;
  },
};
