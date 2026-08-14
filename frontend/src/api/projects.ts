import api, { API_BASE_URL } from "./client";
import type { Workspace, WorkspaceContext, WorkspaceFileResponse, WorkspaceTreeResponse } from "@/types/project";

// Combines sessionsApi and non-patch workspaceApi
export const sessionsApi = {
  listSessions: async (page = 1, pageSize = 20) => {
    const response = await api.get("/sessions", {
      params: { page, page_size: pageSize },
    });
    return response.data;
  },
  createSession: async (title = "New Chat") => {
    const response = await api.post("/sessions", { title });
    return response.data;
  },
  getSession: async (sessionId: string) => {
    const response = await api.get(`/sessions/${sessionId}`);
    return response.data;
  },
  renameSession: async (sessionId: string, title: string) => {
    const response = await api.patch(`/sessions/${sessionId}`, { title });
    return response.data;
  },
  deleteSession: async (sessionId: string) => {
    const response = await api.delete(`/sessions/${sessionId}`);
    return response.data;
  },
  forkSession: async (sessionId: string, checkpointId?: string) => {
    const response = await api.post(`/sessions/${sessionId}/fork`, {
      checkpoint_id: checkpointId ?? null,
    });
    return response.data;
  },
};

export const workspaceApi = {
  listWorkspaces: async (sessionId?: string): Promise<Workspace[]> => {
    const params = sessionId ? { session_id: sessionId } : {};
    const response = await api.get(`/workspaces/`, { params });
    return response.data;
  },
  createWorkspace: async (sessionId: string, name: string) => {
    const response = await api.post(`/workspaces/create`, {
      session_id: sessionId,
      name,
    });
    return response.data;
  },
  attachWorkspace: async (sessionId: string, workspaceId: string) => {
    const response = await api.post(`/workspaces/${workspaceId}/attach`, { session_id: sessionId });
    return response.data;
  },
  uploadFolder: async (sessionId: string, files: FileList | File[]) => {
    const form = new FormData();
    for (let i = 0; i < files.length; i++) {
      const file = files[i];
      const relativePath =
        (file as File & { webkitRelativePath?: string }).webkitRelativePath || file.name;
      form.append("files", file, relativePath);
    }
    const response = await api.post(
      `/workspaces/${sessionId}/upload`,
      form,
      {
        headers: { "Content-Type": "multipart/form-data" },
      }
    );
    return response.data;
  },
  getTree: async (workspaceId: string, signal?: AbortSignal): Promise<WorkspaceTreeResponse> => {
    const response = await api.get(`/workspaces/${workspaceId}/tree`, { signal });
    return response.data;
  },
  searchFiles: async (workspaceId: string, query: string, limit = 50) => {
    const response = await api.get(`/workspaces/${workspaceId}/search`, {
      params: { q: query, limit },
    });
    return (response.data.files || []).map((item: string | { path: string }) =>
      typeof item === "string" ? item : item.path
    );
  },
  getContext: async (workspaceId: string): Promise<WorkspaceContext> => {
    const response = await api.get(`/workspaces/${workspaceId}/context`);
    return response.data;
  },
  refreshContext: async (workspaceId: string) => {
    const response = await api.post(`/workspaces/${workspaceId}/context/refresh`);
    return response.data;
  },
  exportWorkspaceJson: async (workspaceId: string) => {
    const response = await api.get(`/workspaces/${workspaceId}/export-json`);
    return response.data;
  },
  getFile: async (workspaceId: string, filePath: string, signal?: AbortSignal): Promise<WorkspaceFileResponse> => {
    const response = await api.get(`/workspaces/${workspaceId}/file`, {
      params: { file_path: filePath },
      signal,
    });
    return response.data;
  },
  createFile: async (
    workspaceId: string,
    path: string,
    type: "file" | "folder",
    content: string = ""
  ) => {
    const response = await api.post(`/workspaces/${workspaceId}/file`, {
      path,
      type,
      content,
    });
    return response.data;
  },
  updateFile: async (workspaceId: string, path: string, content: string) => {
    const response = await api.put(`/workspaces/${workspaceId}/file`, {
      path,
      content,
    });
    return response.data;
  },
  deleteFile: async (workspaceId: string, path: string) => {
    const response = await api.delete(`/workspaces/${workspaceId}/file`, {
      params: { path },
    });
    return response.data;
  },
  renameFile: async (
    workspaceId: string,
    oldPath: string,
    newPath: string
  ) => {
    const response = await api.post(`/workspaces/${workspaceId}/rename`, {
      old_path: oldPath,
      new_path: newPath,
    });
    return response.data;
  },
  getDownloadUrl: (workspaceId: string) => {
    return `${API_BASE_URL}/workspaces/${workspaceId}/download`;
  },
  downloadWorkspace: async (workspaceId: string) => {
    const response = await api.get(`/workspaces/${workspaceId}/download`, {
      responseType: 'blob',
    });
    let filename = `workspace.zip`;
    const disposition = response.headers['content-disposition'];
    if (disposition && disposition.indexOf('filename=') !== -1) {
      const matches = /filename[^;=\n]*=((['"]).*?\2|[^;\n]*)/.exec(disposition);
      if (matches != null && matches[1]) {
        filename = matches[1].replace(/['"]/g, '');
      }
    }
    const url = window.URL.createObjectURL(new Blob([response.data]));
    const link = document.createElement('a');
    link.href = url;
    link.setAttribute('download', filename);
    document.body.appendChild(link);
    link.click();
    link.remove();
    window.URL.revokeObjectURL(url);
  },
};
