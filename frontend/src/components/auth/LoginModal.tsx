import { useState } from "react";
import { Mail, Loader2, Eye, EyeOff } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { authApi } from "@/api";

interface LoginModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSuccess?: () => void;
  hideCloseButton?: boolean;
}

export default function LoginModal({
  isOpen,
  onClose,
  onSuccess,
  hideCloseButton,
}: LoginModalProps) {
  const [isEmailMode, setIsEmailMode] = useState(false);
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState("");

  if (!isOpen) return null;

  const handleEmailAuth = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsLoading(true);
    setError("");

    if (!email || !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) {
      setError("Please enter a valid email address");
      setIsLoading(false);
      return;
    }

    if (!password || password.length < 8) {
      setError("Password must be at least 8 characters");
      setIsLoading(false);
      return;
    }

    try {
      try {
        const res = await authApi.login({ email, password });
        sessionStorage.setItem("compass_access_token", res.access_token);
        if (res.refresh_token)
          sessionStorage.setItem("compass_refresh_token", res.refresh_token);
        if (onSuccess) onSuccess();
        onClose();
      } catch (err: any) {
        if (
          err.response?.status === 401 ||
          err.response?.status === 404
        ) {
          // Try registering if login fails
          const res = await authApi.register({
            email,
            password,
            display_name: email.split("@")[0],
          });
          sessionStorage.setItem("compass_access_token", res.access_token);
          if (res.refresh_token)
            sessionStorage.setItem("compass_refresh_token", res.refresh_token);
          if (onSuccess) onSuccess();
          onClose();
        } else {
          throw err;
        }
      }
    } catch (err: any) {
      setError(err.response?.data?.detail || "Authentication failed");
    } finally {
      setIsLoading(false);
    }
  };

  const handleGoogleLogin = async () => {
    setIsLoading(true);
    setError("");
    try {
      const redirectUri = `${window.location.origin}/auth/callback`;
      const res = await authApi.getGoogleAuthUrl(redirectUri);
      window.location.href = res.url;
    } catch (err: any) {
      setError(
        err.response?.data?.detail ||
          "Failed to initialize Google Login. Verify GOOGLE_CLIENT_ID is configured in backend/.env."
      );
    } finally {
      setIsLoading(false);
    }
  };



  return (
    <div className="relative w-full max-w-md bg-card border border-border rounded-none shadow-none p-6 flex flex-col items-center">
      {!hideCloseButton && (
        <button
          onClick={onClose}
          aria-label="Close"
          className="absolute top-4 right-4 flex items-center justify-center rounded-md p-1 text-muted-foreground hover:bg-muted hover:text-foreground transition-colors duration-150 focus-visible:ring-2 focus-visible:ring-primary/40"
        >
          <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
          </svg>
        </button>
      )}

      <div className="mb-8 text-center mt-4">
        <div className="mx-auto mb-4 flex size-12 items-center justify-center rounded-none bg-accent/10 text-accent border border-accent">
          <svg className="h-6 w-6" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z" />
          </svg>
        </div>
        <h2 className="text-2xl font-bold tracking-tight mb-2">Welcome to Compass</h2>
        <p className="text-sm text-muted-foreground">
          Sign in to save your projects and access them anywhere.
        </p>
      </div>

      <div className="flex flex-col gap-3 w-full max-w-sm">
        {error && (
          <div className="rounded-lg border border-destructive/30 bg-destructive/10 px-3 py-2 text-sm text-destructive text-center">
            {error}
          </div>
        )}

        {isEmailMode ? (
          <form onSubmit={handleEmailAuth} className="flex flex-col gap-3">
            <Input
              type="email"
              placeholder="Email address"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              className="h-11 focus-visible:ring-2 focus-visible:ring-primary/40"
              required
            />
            <div className="relative">
              <Input
                type={showPassword ? "text" : "password"}
                placeholder="Password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                className="h-11 pr-10 focus-visible:ring-2 focus-visible:ring-primary/40"
                required
              />
              <button
                type="button"
                className="absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground"
                onClick={() => setShowPassword(!showPassword)}
                tabIndex={-1}
              >
                {showPassword ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
              </button>
            </div>
            <Button type="submit" className="w-full h-11" disabled={isLoading}>
              {isLoading && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
              Sign In / Register
            </Button>
            <Button
              type="button"
              variant="ghost"
              className="w-full text-xs"
              onClick={() => setIsEmailMode(false)}
            >
              Back to all options
            </Button>
          </form>
        ) : (
          <>
            <Button
              variant="outline"
              className="h-11 w-full justify-start px-4 font-normal transition-colors duration-150 focus-visible:ring-2 focus-visible:ring-primary/40"
              onClick={handleGoogleLogin}
              disabled={isLoading}
            >
              <svg className="w-5 h-5 mr-3" viewBox="0 0 24 24" fill="none">
                <path d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z" fill="#4285F4"/>
                <path d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z" fill="#34A853"/>
                <path d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z" fill="#FBBC05"/>
                <path d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z" fill="#EA4335"/>
              </svg>
              Continue with Google
            </Button>

            <div className="relative my-2">
              <div className="absolute inset-0 flex items-center">
                <span className="w-full border-t border-border" />
              </div>
              <div className="relative flex justify-center text-xs uppercase">
                <span className="bg-card px-2 text-muted-foreground">Or</span>
              </div>
            </div>

            <Button
              variant="outline"
              className="h-11 w-full justify-start px-4 font-normal transition-colors duration-150 focus-visible:ring-2 focus-visible:ring-primary/40"
              onClick={() => setIsEmailMode(true)}
            >
              <Mail className="w-5 h-5 mr-3" />
              Continue with Email
            </Button>
          </>
        )}
      </div>

      <p className="mt-8 text-xs text-center text-muted-foreground">
        By continuing, you agree to our Terms of Service and Privacy Policy.
      </p>
    </div>
  );
}
