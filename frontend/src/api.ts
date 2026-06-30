import axios from "axios";

export const API_BASE_URL = "http://localhost:8000";
export const WS_BASE_URL = API_BASE_URL.replace(/^http/, "ws");

const api = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    "Content-Type": "application/json",
  },
});

api.interceptors.request.use(
  (config) => {
    const token = localStorage.getItem("compass_access_token");
    if (token && config.headers) {
      config.headers.set("Authorization", `Bearer ${token}`);
    }
    return config;
  },
  (error) => Promise.reject(error)
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
    const response = await api.get("/sessions", { params: { page, page_size: pageSize } });
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
  sendMessage: async (sessionId: string, content: string, mode: "normal" | "plan" = "normal") => {
    const response = await api.post("/chat/send", { session_id: sessionId, content, mode });
    return response.data;
  },
  createWebSocket: (sessionId: string) => {
    const token = localStorage.getItem("compass_access_token") || "";
    return new WebSocket(`${WS_BASE_URL}/chat/ws/${sessionId}?token=${encodeURIComponent(token)}`);
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
    const response = await api.get(`/sessions/${sessionId}/uploads/capabilities`);
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
    const response = await api.delete(`/sessions/${sessionId}/uploads/${uploadId}`);
    return response.data;
  },
};

export default api;
