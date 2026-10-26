import api, { clearAuthTokens, notifyAuthInvalidated } from "./client";
import type { AuthTokens, AuthUser, EmailCredentials, RegistrationDetails } from "@/types/auth";

export const authApi = {
  login: async (data: EmailCredentials): Promise<AuthTokens> => {
    const response = await api.post("/auth/login", data);
    return response.data;
  },
  register: async (data: RegistrationDetails): Promise<AuthTokens> => {
    const response = await api.post("/auth/register", data);
    return response.data;
  },
  getMe: async (): Promise<AuthUser> => {
    const response = await api.get("/auth/me");
    return response.data;
  },
  logout: async () => {
    try {
      await api.post("/auth/logout");
    } catch {
      // Ignore errors — local authentication state is always cleared.
    }
    clearAuthTokens();
    notifyAuthInvalidated();
  },
  getGoogleAuthUrl: async (redirectUri: string, intent = "login", returnTo = "/chat") => {
    const response = await api.get("/auth/oauth/google/url", {
      params: { redirect_uri: redirectUri, intent, return_to: returnTo },
    });
    return response.data;
  },
  getGithubAuthUrl: async (intent = "login", returnTo = "/chat") => {
    const response = await api.get("/auth/oauth/github/url", {
      params: { intent, return_to: returnTo },
    });
    return response.data;
  },
  loginGoogle: async (code: string, redirectUri: string, state: string): Promise<AuthTokens> => {
    const response = await api.post("/auth/oauth/google", null, {
      params: { code, redirect_uri: redirectUri, state },
    });
    return response.data;
  },
  loginGithub: async (code: string, state: string): Promise<AuthTokens> => {
    const response = await api.post("/auth/oauth/github", null, {
      params: { code, state },
    });
    return response.data;
  },
};
