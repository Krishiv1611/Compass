import axios from "axios";

export const API_BASE_URL = import.meta.env.VITE_API_URL || "http://localhost:8000";
export const WS_BASE_URL = import.meta.env.VITE_WS_URL || API_BASE_URL.replace(/^http/, "ws");

const api = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    "Content-Type": "application/json",
  },
});

api.interceptors.request.use(
  (config) => {
    const token = sessionStorage.getItem("compass_access_token");
    if (token && config.headers) {
      config.headers.Authorization = `Bearer ${token}`;
    }
    return config;
  },
  (error) => Promise.reject(error)
);

api.interceptors.response.use(
  (response) => response,
  async (error) => {
    const originalRequest = error.config;
    if (
      error.response?.status === 401 &&
      !originalRequest._retry &&
      originalRequest.url !== "/auth/login"
    ) {
      originalRequest._retry = true;
      const refreshToken = sessionStorage.getItem("compass_refresh_token");
      if (refreshToken) {
        try {
          // Send refresh token in JSON body (BUG-9 security fix)
          const res = await axios.post(`${API_BASE_URL}/auth/refresh`, {
            token: refreshToken,
          });
          if (res.data && res.data.access_token) {
            sessionStorage.setItem("compass_access_token", res.data.access_token);
            if (res.data.refresh_token) {
              sessionStorage.setItem("compass_refresh_token", res.data.refresh_token);
            }
            originalRequest.headers.Authorization = `Bearer ${res.data.access_token}`;
            return api(originalRequest);
          }
        } catch {
          sessionStorage.removeItem("compass_access_token");
          sessionStorage.removeItem("compass_refresh_token");
          window.dispatchEvent(new Event("auth-changed"));
        }
      } else {
        sessionStorage.removeItem("compass_access_token");
        window.dispatchEvent(new Event("auth-changed"));
      }
    }
    return Promise.reject(error);
  }
);

// --- Auth API ---
export const authApi = {
  login: async (data: any) => {
    const response = await api.post("/auth/login", data);
    return response.data;
  },
  register: async (data: any) => {
    const response = await api.post("/auth/register", data);
    return response.data;
  },
  getMe: async () => {
    const response = await api.get("/auth/me");
    return response.data;
  },
  logout: async () => {
    try {
      await api.post("/auth/logout");
    } catch {
      // ignore errors — we always clear tokens
    }
    sessionStorage.removeItem("compass_access_token");
    sessionStorage.removeItem("compass_refresh_token");
    window.dispatchEvent(new Event("auth-changed"));
  },
  getGoogleAuthUrl: async (redirectUri: string) => {
    const response = await api.get("/auth/oauth/google/url", {
      params: { redirect_uri: redirectUri },
    });
    return response.data;
  },
  getGithubAuthUrl: async () => {
    const response = await api.get("/auth/oauth/github/url");
    return response.data;
  },
  loginGoogle: async (code: string, redirectUri: string) => {
    const response = await api.post("/auth/oauth/google", null, {
      params: { code, redirect_uri: redirectUri },
    });
    return response.data;
  },
  loginGithub: async (code: string) => {
    const response = await api.post("/auth/oauth/github", null, {
      params: { code },
    });
    return response.data;
  },
};

// --- Sessions API ---
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
};

// --- Chat API ---
export const chatApi = {
  sendMessage: async (
    sessionId: string,
    content: string,
    mode: "normal" | "plan" | "fast" = "normal"
  ) => {
    const response = await api.post("/chat/send", {
      session_id: sessionId,
      content,
      mode,
    });
    return response.data;
  },
  createWebSocket: (sessionId: string) => {
    const token = sessionStorage.getItem("compass_access_token") || "";
    return new WebSocket(
      `${WS_BASE_URL}/chat/ws/${sessionId}?token=${encodeURIComponent(token)}`
    );
  },
};

// --- Settings API ---
export const settingsApi = {
  getSettings: async () => {
    const response = await api.get("/settings");
    return response.data;
  },
  updateSettings: async (data: Record<string, unknown>) => {
    const response = await api.put("/settings", data);
    return response.data;
  },
  getMcpServers: async () => {
    const response = await api.get("/settings/mcp-servers");
    return response.data;
  },
  updateMcpServers: async (data: any) => {
    const response = await api.post("/settings/mcp-servers", data);
    return response.data;
  },
  testMcpServer: async (name: string, config: any) => {
    const response = await api.post("/settings/mcp-servers/test", { name, config });
    return response.data;
  },
};

// --- Tools API ---
export const toolsApi = {
  listTools: async () => {
    const response = await api.get("/tools");
    return response.data;
  },
};

// --- Uploads API ---
export const uploadsApi = {
  getCapabilities: async (sessionId: string) => {
    const response = await api.get(
      `/sessions/${sessionId}/uploads/capabilities`
    );
    return response.data;
  },
  listUploads: async (sessionId: string) => {
    const response = await api.get(`/sessions/${sessionId}/uploads`);
    return response.data;
  },
  uploadFile: async (sessionId: string, file: File) => {
    const form = new FormData();
    form.append("file", file);
    const response = await api.post(`/sessions/${sessionId}/uploads`, form, {
      headers: { "Content-Type": "multipart/form-data" },
    });
    return response.data;
  },
  deleteUpload: async (sessionId: string, uploadId: string) => {
    const response = await api.delete(
      `/sessions/${sessionId}/uploads/${uploadId}`
    );
    return response.data;
  },
};

// --- Runs API ---
export const runsApi = {
  getSessionRuns: async (sessionId: string) => {
    const response = await api.get(`/sessions/${sessionId}/runs`);
    return response.data;
  },
  cancelRun: async (sessionId: string, runId: string) => {
    const response = await api.post(
      `/sessions/${sessionId}/runs/${runId}/cancel`
    );
    return response.data;
  },
};

// --- Workspaces API ---
export const workspaceApi = {
  listWorkspaces: async (sessionId?: string) => {
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
  uploadFolder: async (sessionId: string, files: FileList | File[]) => {
    const form = new FormData();
    for (let i = 0; i < files.length; i++) {
      const file = files[i];
      const relativePath =
        (file as any).webkitRelativePath || file.name;
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
  getTree: async (workspaceId: string) => {
    const response = await api.get(`/workspaces/${workspaceId}/tree`);
    return response.data;
  },
  getFile: async (workspaceId: string, filePath: string) => {
    const response = await api.get(`/workspaces/${workspaceId}/file`, {
      params: { file_path: filePath },
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
  getPatches: async (workspaceId: string) => {
    const response = await api.get(`/workspaces/${workspaceId}/patches`);
    return response.data;
  },
  applyPatch: async (workspaceId: string, patchId: string) => {
    const response = await api.post(
      `/workspaces/${workspaceId}/patches/${patchId}/apply`
    );
    return response.data;
  },
  rejectPatch: async (workspaceId: string, patchId: string) => {
    const response = await api.post(
      `/workspaces/${workspaceId}/patches/${patchId}/reject`
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

export default api;
