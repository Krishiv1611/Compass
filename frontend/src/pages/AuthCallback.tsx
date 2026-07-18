import { useEffect, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { Loader2 } from "lucide-react";
import { authApi } from "@/api";

export default function AuthCallback() {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const handleCallback = async () => {
      const code = searchParams.get("code");
      const state = searchParams.get("state"); // Determine if google or github

      if (!code) {
        setError("Authorization code is missing.");
        return;
      }

      try {
        let tokenResponse;
        if (state === "google") {
          const redirectUri = `${window.location.origin}/auth/callback`;
          tokenResponse = await authApi.loginGoogle(code, redirectUri);
        } else if (state === "github") {
          tokenResponse = await authApi.loginGithub(code);
        } else {
          setError("Invalid OAuth provider state.");
          return;
        }

        // Store JWT token
        sessionStorage.setItem("compass_access_token", tokenResponse.access_token);
        if (tokenResponse.refresh_token) {
          sessionStorage.setItem("compass_refresh_token", tokenResponse.refresh_token);
        }
        
        window.dispatchEvent(new Event("auth-changed"));
        
        // Redirect to chat
        navigate("/chat", { replace: true });
      } catch (err: any) {
        console.error("OAuth exchange error", err);
        setError(err.response?.data?.detail || "Failed to complete authentication with the server.");
      }
    };

    handleCallback();
  }, [searchParams, navigate]);

  return (
    <div className="flex flex-col items-center justify-center min-h-[60vh] p-4 text-center">
      {error ? (
        <div className="max-w-md p-6 bg-destructive/10 border border-destructive/20 rounded-xl">
          <h2 className="text-xl font-semibold text-destructive mb-2">Authentication Failed</h2>
          <p className="text-sm text-muted-foreground mb-6">{error}</p>
          <button
            onClick={() => navigate("/chat")}
            className="px-4 py-2 bg-primary text-primary-foreground rounded-lg hover:bg-primary/90 text-sm font-medium transition-colors"
          >
            Go back to Chat
          </button>
        </div>
      ) : (
        <div className="flex flex-col items-center gap-4">
          <Loader2 className="w-8 h-8 animate-spin text-primary" />
          <h2 className="text-lg font-medium">Completing Sign-In</h2>
          <p className="text-sm text-muted-foreground max-w-xs">
            Exchanging authorization tokens with the backend. Please hold on...
          </p>
        </div>
      )}
    </div>
  );
}



