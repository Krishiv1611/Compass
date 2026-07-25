import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";
import {
  authApi,
  clearAuthTokens,
  storeAuthTokens,
  subscribeAuthInvalidated,
} from "@/api";
import type {
  AuthTokens,
  AuthUser,
  EmailCredentials,
  RegistrationDetails,
} from "@/types/auth";

type AuthStatus = "loading" | "authenticated" | "anonymous";

interface AuthContextValue {
  status: AuthStatus;
  user: AuthUser | null;
  refresh: () => Promise<void>;
  finishAuthentication: (tokens: AuthTokens) => Promise<void>;
  signIn: (credentials: EmailCredentials) => Promise<void>;
  signUp: (details: RegistrationDetails) => Promise<void>;
  signOut: () => Promise<void>;
}

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [status, setStatus] = useState<AuthStatus>("loading");
  const [user, setUser] = useState<AuthUser | null>(null);

  const refresh = useCallback(async () => {
    try {
      setUser(await authApi.getMe());
      setStatus("authenticated");
    } catch {
      clearAuthTokens();
      setUser(null);
      setStatus("anonymous");
    }
  }, []);

  useEffect(() => {
    void refresh();
    return subscribeAuthInvalidated(() => {
      setUser(null);
      setStatus("anonymous");
    });
  }, [refresh]);

  const finishAuthentication = useCallback(async (tokens: AuthTokens) => {
    storeAuthTokens(tokens);
    const nextUser = await authApi.getMe();
    setUser(nextUser);
    setStatus("authenticated");
  }, []);

  const signIn = useCallback(async (credentials: EmailCredentials) => {
    await finishAuthentication(await authApi.login(credentials));
  }, [finishAuthentication]);

  const signUp = useCallback(async (details: RegistrationDetails) => {
    await finishAuthentication(await authApi.register(details));
  }, [finishAuthentication]);

  const signOut = useCallback(async () => {
    await authApi.logout();
    setUser(null);
    setStatus("anonymous");
  }, []);

  const value = useMemo<AuthContextValue>(() => ({
    status,
    user,
    refresh,
    finishAuthentication,
    signIn,
    signUp,
    signOut,
  }), [finishAuthentication, refresh, signIn, signOut, signUp, status, user]);

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) throw new Error("useAuth must be used within AuthProvider");
  return context;
}
