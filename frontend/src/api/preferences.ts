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
  testProvider: async (data: {
    provider: string;
    model: string;
    api_key?: string;
  }) => {
    const response = await api.post("/settings/provider-test", data);
    return response.data;
  },
  removeCredential: async (provider: string) => {
    const response = await api.delete(
      `/settings/credentials/${encodeURIComponent(provider)}`,
    );
    return response.data;
  },
};
