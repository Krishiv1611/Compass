import api from "./client";
import type { WorkspacePatch } from "@/types/patch";

export const patchesApi = {
  getPatches: async (workspaceId: string): Promise<WorkspacePatch[]> => {
    const response = await api.get(`/workspaces/${workspaceId}/patches`);
    return response.data;
  },
  applyPatch: async (workspaceId: string, patchId: string) => {
    const response = await api.post(
      `/workspaces/${workspaceId}/patches/${patchId}/apply`
    );
    return response.data;
  },
  resolvePatchFile: async (
    workspaceId: string,
    patchId: string,
    path: string,
    action: "apply" | "reject" | "undo",
  ) => {
    const response = await api.post(
      `/workspaces/${workspaceId}/patches/${patchId}/files/${action}`,
      { path },
    );
    return response.data;
  },
  rejectPatch: async (workspaceId: string, patchId: string) => {
    const response = await api.post(
      `/workspaces/${workspaceId}/patches/${patchId}/reject`
    );
    return response.data;
  },
  undoPatch: async (workspaceId: string, patchId: string) => {
    const response = await api.post(
      `/workspaces/${workspaceId}/patches/${patchId}/undo`
    );
    return response.data;
  },
  acceptAllPatches: async (workspaceId: string) => {
    const response = await api.post(
      `/workspaces/${workspaceId}/patches/accept-all`
    );
    return response.data;
  },
  rejectAllPatches: async (workspaceId: string) => {
    const response = await api.post(
      `/workspaces/${workspaceId}/patches/reject-all`
    );
    return response.data;
  },
};
