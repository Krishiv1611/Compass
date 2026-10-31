import { useState } from "react";
import { motion } from "framer-motion";
import { AlertCircle, Compass, GitBranch, Loader2, Mail } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { authApi } from "@/api";
import { useAuth } from "@/contexts/AuthContext";
import { cn } from "@/lib/utils";

interface AuthSurfaceProps {
  onSuccess?: () => void;
  className?: string;
}

export default function AuthSurface({ onSuccess, className = "" }: AuthSurfaceProps) {
  const { signIn, signUp } = useAuth();
  const [mode, setMode] = useState<"sign-in" | "sign-up">("sign-in");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [displayName, setDisplayName] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const submit = async (event: React.FormEvent) => {
    event.preventDefault();
    setError("");
    if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) {
      setError("Enter a valid email address.");
      return;
    }
    if (password.length < 8) {
      setError("Password must contain at least 8 characters.");
      return;
    }
    if (mode === "sign-up" && !displayName.trim()) {
      setError("Display name is required for sign up.");
      return;
    }

    setLoading(true);
    try {
      if (mode === "sign-in") {
        await signIn({ email, password });
      } else {
        await signUp({ email, password, display_name: displayName.trim() });
      }
      onSuccess?.();
    } catch (requestError) {
      setError(
        requestError instanceof Error
          ? requestError.message
          : mode === "sign-in"
          ? "Sign-in failed."
          : "Account creation failed."
      );
    } finally {
      setLoading(false);
    }
  };

  const beginOAuth = async (provider: "google" | "github") => {
    setLoading(true);
    setError("");
    try {
      const returnTo = `${window.location.pathname}${window.location.search}` || "/chat";
      sessionStorage.setItem("compass_oauth_provider", provider);
      sessionStorage.setItem("compass_oauth_intent", "login");
      sessionStorage.setItem("compass_oauth_return_to", returnTo);
      const redirectUri = `${window.location.origin}/auth/callback`;
      const response =
        provider === "google"
          ? await authApi.getGoogleAuthUrl(redirectUri, "login", returnTo)
          : await authApi.getGithubAuthUrl("login", returnTo);
      window.location.assign(response.url);
    } catch (requestError) {
      setError(
        requestError instanceof Error ? requestError.message : `Could not start ${provider} authentication.`
      );
      setLoading(false);
    }
  };

  return (
    <section
      className={cn(
        "w-full max-w-md rounded-2xl border border-border/80 bg-[#0D1117]/90 backdrop-blur-xl p-7 shadow-2xl relative",
        className
      )}
      aria-labelledby="auth-title"
    >
      <div className="mb-6 text-center">
        <div className="mx-auto mb-3 flex size-11 items-center justify-center rounded-xl bg-primary/10 text-primary border border-primary/20 studio-glow-cyan">
          <Compass className="h-5 w-5" />
        </div>
        <h1 id="auth-title" className="text-xl font-bold tracking-tight text-foreground">
          {mode === "sign-in" ? "Welcome back" : "Create your Compass account"}
        </h1>
        <p className="mt-1 text-xs text-muted-foreground">
          Your sessions and workspaces stay available across devices.
        </p>
      </div>

      <div
        className="relative mb-5 grid grid-cols-2 rounded-xl bg-[#080A0E] p-1 border border-border/80"
        role="tablist"
        aria-label="Authentication mode"
      >
        {(["sign-in", "sign-up"] as const).map((value) => {
          const isSelected = mode === value;
          return (
            <button
              key={value}
              type="button"
              role="tab"
              aria-selected={isSelected}
              onClick={() => {
                setMode(value);
                setError("");
              }}
              className={cn(
                "relative z-10 rounded-lg px-3 py-1.5 text-xs font-medium transition-colors select-none outline-none focus-visible:ring-1 focus-visible:ring-primary",
                isSelected ? "text-foreground font-semibold" : "text-muted-foreground hover:text-foreground"
              )}
            >
              {isSelected && (
                <motion.div
                  layoutId="authModePill"
                  className="absolute inset-0 rounded-lg bg-[#161B22] border border-border/80 shadow-sm"
                  transition={{ type: "spring", stiffness: 450, damping: 32 }}
                />
              )}
              <span className="relative z-10">{value === "sign-in" ? "Sign in" : "Sign up"}</span>
            </button>
          );
        })}
      </div>

      {error && (
        <p
          role="alert"
          className="mb-4 rounded-xl border border-destructive/40 bg-destructive/10 px-3.5 py-2.5 text-xs text-destructive font-mono flex items-center gap-2"
        >
          <AlertCircle className="h-4 w-4 shrink-0" />
          <span>{error}</span>
        </p>
      )}

      <form className="space-y-3.5" onSubmit={submit}>
        <Input
          type="email"
          autoComplete="email"
          value={email}
          onChange={(event) => setEmail(event.target.value)}
          placeholder="developer@company.com"
          aria-label="Email address"
          disabled={loading}
          className="h-10 bg-[#080A0E]/80 border-border/80 text-foreground placeholder:text-muted-foreground/60 focus-visible:ring-primary focus-visible:border-primary/50 text-xs font-mono"
          required
        />

        {mode === "sign-up" && (
          <Input
            type="text"
            autoComplete="name"
            value={displayName}
            onChange={(event) => setDisplayName(event.target.value)}
            placeholder="Display Name"
            aria-label="Display Name"
            disabled={loading}
            className="h-10 bg-[#080A0E]/80 border-border/80 text-foreground placeholder:text-muted-foreground/60 focus-visible:ring-primary focus-visible:border-primary/50 text-xs"
            required
          />
        )}

        <Input
          type="password"
          autoComplete={mode === "sign-in" ? "current-password" : "new-password"}
          value={password}
          onChange={(event) => setPassword(event.target.value)}
          placeholder="••••••••"
          aria-label="Password"
          disabled={loading}
          className="h-10 bg-[#080A0E]/80 border-border/80 text-foreground placeholder:text-muted-foreground/60 focus-visible:ring-primary focus-visible:border-primary/50 text-xs font-mono"
          required
        />

        <motion.div whileHover={{ scale: 1.01 }} whileTap={{ scale: 0.98 }}>
          <Button
            type="submit"
            className="w-full h-10 bg-primary hover:bg-primary-hover text-primary-foreground font-medium text-xs shadow-md transition-all cursor-pointer"
            disabled={loading}
          >
            {loading ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <Mail className="mr-2 h-4 w-4" />}
            {mode === "sign-in" ? "Sign in with Email" : "Sign up with Email"}
          </Button>
        </motion.div>
      </form>

      <div className="relative my-5">
        <div className="absolute inset-0 flex items-center">
          <span className="w-full border-t border-border/70" />
        </div>
        <div className="relative flex justify-center text-[10px]">
          <span className="bg-[#0D1117] px-2.5 text-muted-foreground/80 font-mono tracking-wider">
            OR CONTINUE WITH
          </span>
        </div>
      </div>

      <div className="grid grid-cols-2 gap-3">
        <motion.div whileHover={{ y: -1, scale: 1.01 }} whileTap={{ scale: 0.98 }}>
          <Button
            type="button"
            variant="outline"
            onClick={() => beginOAuth("google")}
            disabled={loading}
            className="w-full h-10 border-border/80 bg-[#080A0E]/80 hover:bg-[#131822] text-foreground text-xs font-medium transition-all cursor-pointer"
          >
            <svg className="mr-2 h-4 w-4 shrink-0" aria-hidden="true" viewBox="0 0 24 24">
              <path
                d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z"
                fill="#4285F4"
              />
              <path
                d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"
                fill="#34A853"
              />
              <path
                d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z"
                fill="#FBBC05"
              />
              <path
                d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z"
                fill="#EA4335"
              />
              <path d="M1 1h22v22H1z" fill="none" />
            </svg>
            Google
          </Button>
        </motion.div>
        <motion.div whileHover={{ y: -1, scale: 1.01 }} whileTap={{ scale: 0.98 }}>
          <Button
            type="button"
            variant="outline"
            onClick={() => beginOAuth("github")}
            disabled={loading}
            className="w-full h-10 border-border/80 bg-[#080A0E]/80 hover:bg-[#131822] text-foreground text-xs font-medium transition-all cursor-pointer"
          >
            <GitBranch className="mr-2 h-4 w-4 shrink-0 text-cyan-400" />
            Continue with GitHub
          </Button>
        </motion.div>
      </div>
    </section>
  );
}
