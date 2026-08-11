import api from "./client";

export type MemoryScope = "global" | "project";

export interface MemoryItem {
  key: string;
  content: string;
  category: string;
  scope: MemoryScope;
  project_id?: string | null;
  enabled: boolean;
  created_at?: string;
  updated_at?: string;
}

export interface MemoryWrite {
  content: string;
  key?: string;
  scope: MemoryScope;
  project_id?: string | null;
  category: string;
  enabled: boolean;
}

const paramsFor = (scope: MemoryScope, projectId?: string | null) => ({
  scope,
  ...(scope === "project" && projectId ? { project_id: projectId } : {}),
});

export const memoryApi = {
  list: async (scope: MemoryScope = "global", projectId?: string | null) => {
    const response = await api.get("/memory", { params: paramsFor(scope, projectId) });
    return response.data as { memories: MemoryItem[]; enabled: boolean; error?: string | null };
  },
  create: async (body: MemoryWrite) => {
    const response = await api.post("/memory", body);
    return response.data as MemoryItem;
  },
  update: async (key: string, body: MemoryWrite) => {
    const response = await api.put(`/memory/${encodeURIComponent(key)}`, body);
    return response.data as MemoryItem;
  },
  remove: async (key: string, scope: MemoryScope, projectId?: string | null) => {
    await api.delete(`/memory/${encodeURIComponent(key)}`, { params: paramsFor(scope, projectId) });
  },
};
