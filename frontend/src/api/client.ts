import axios, { AxiosError, type InternalAxiosRequestConfig } from "axios";

export const API_BASE_URL = import.meta.env.VITE_API_URL || "http://localhost:8000/api";
export const WS_BASE_URL = import.meta.env.VITE_WS_URL || API_BASE_URL.replace(/^http/, "ws");

const api = axios.create({
  baseURL: API_BASE_URL,
  withCredentials: true,
  headers: {
    "Content-Type": "application/json",
  },
});

const authInvalidatedListeners = new Set<() => void>();
let accessToken: string | null = null;

export class ApiError extends Error {
  status: number;
  code?: string;
  details?: unknown;

  constructor(message: string, status = 0, code?: string, details?: unknown) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.code = code;
    this.details = details;
  }
}

type RetryableRequest = InternalAxiosRequestConfig & { _retry?: boolean };

export const subscribeAuthInvalidated = (listener: () => void) => {
  authInvalidatedListeners.add(listener);
  return () => {
    authInvalidatedListeners.delete(listener);
  };
};

export const notifyAuthInvalidated = () => {
  authInvalidatedListeners.forEach((listener) => listener());
};

export const storeAuthTokens = (tokens: { access_token: string }) => {
  accessToken = tokens.access_token;
};

export const clearAuthTokens = () => {
  accessToken = null;
};

export const getAccessToken = () => accessToken;

api.interceptors.request.use(
  (config) => {
    const token = accessToken;
    if (token && config.headers) {
      config.headers.Authorization = `Bearer ${token}`;
    }
    return config;
  },
  (error) => Promise.reject(error)
);

api.interceptors.response.use(
  (response) => response,
  async (error: AxiosError<{ detail?: string; code?: string }>) => {
    const originalRequest = error.config as RetryableRequest | undefined;
    if (
      error.response?.status === 401 &&
      originalRequest &&
      !originalRequest._retry &&
      !originalRequest.url?.includes("/auth/login")
    ) {
      originalRequest._retry = true;
      try {
          const res = await axios.post(`${API_BASE_URL}/auth/refresh`, undefined, { withCredentials: true });
          if (res.data && res.data.access_token) {
            accessToken = res.data.access_token;
            originalRequest.headers.set("Authorization", `Bearer ${res.data.access_token}`);
            return api(originalRequest);
          }
        } catch {
          clearAuthTokens();
          notifyAuthInvalidated();
        }
    }
    const detail = error.response?.data?.detail;
    return Promise.reject(new ApiError(
      typeof detail === "string" ? detail : error.message || "Request failed",
      error.response?.status || 0,
      error.response?.data?.code,
      error.response?.data,
    ));
  }
);

export default api;
