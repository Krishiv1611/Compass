import api from "./client";

export interface CheckpointFile {
  path: string;
  existed: boolean;
  sha256?: string | null;
  size: number;
}

export interface CheckpointSummary {
  id: string;
  workspace_id: string;
  thread_id: string;
  created_at: string;
  label: string;
  files: CheckpointFile[];
}

export interface RestorePreview {
  checkpoint_id: string;
  changes: string[];
  conflicts: string[];
}

export const checkpointsApi = {
  listCheckpoints: async (workspaceId: string): Promise<CheckpointSummary[]> => {
    const response = await api.get(`/workspaces/${workspaceId}/checkpoints`);
    return response.data;
  },
  previewRestore: async (workspaceId: string, checkpointId: string): Promise<RestorePreview> => {
    const response = await api.get(`/workspaces/${workspaceId}/checkpoints/${checkpointId}/preview`);
    return response.data;
  },
  restoreCheckpoint: async (
    workspaceId: string,
    checkpointId: string,
    force = false,
  ): Promise<{ checkpoint_id: string; affected_files: string[] }> => {
    const response = await api.post(`/workspaces/${workspaceId}/checkpoints/${checkpointId}/restore`, {
      force,
    });
    return response.data;
  },
};
