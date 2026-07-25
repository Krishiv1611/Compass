import { useEffect, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { AlertTriangle, Loader2 } from "lucide-react";
import { authApi, githubApi } from "@/api";
import { useAuth } from "@/contexts/AuthContext";
import { Button } from "@/components/ui/button";

export default function AuthCallback() {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const [error, setError] = useState<string | null>(null);
  const { finishAuthentication } = useAuth();

  useEffect(() => {
    let cancelled = false;
    const complete = async () => {
      const providerError = searchParams.get("error");
      const errorDescription = searchParams.get("error_description");
      const code = searchParams.get("code");
      const state = searchParams.get("state");
      const provider = sessionStorage.getItem("compass_oauth_provider");
      const intent = sessionStorage.getItem("compass_oauth_intent") || "login";
      const storedReturnTo = sessionStorage.getItem("compass_oauth_return_to") || "/chat";
      const returnTo = storedReturnTo.startsWith("/") && !storedReturnTo.startsWith("//") ? storedReturnTo : "/chat";

      if (providerError) {
        setError(providerError === "access_denied" ? "Authorization was cancelled or denied." : errorDescription || "The provider could not authorize this request.");
        return;
      }
      if (!code || !state || (provider !== "google" && provider !== "github")) {
        setError("This authorization link is incomplete or expired. Start again from Compass.");
        return;
      }
      try {
        if (intent === "connect_github") {
          if (provider !== "github") throw new Error("Repository connection requires GitHub.");
          await githubApi.exchangeOAuth(code, state);
        } else {
          const tokens = provider === "google"
            ? await authApi.loginGoogle(code, `${window.location.origin}/auth/callback`, state)
            : await authApi.loginGithub(code, state);
          await finishAuthentication(tokens);
        }
        if (cancelled) return;
        sessionStorage.removeItem("compass_oauth_provider");
        sessionStorage.removeItem("compass_oauth_intent");
        sessionStorage.removeItem("compass_oauth_return_to");
        navigate(returnTo, { replace: true });
      } catch (requestError) {
        if (!cancelled) setError(requestError instanceof Error ? requestError.message : "Could not complete authorization.");
      }
    };
    void complete();
    return () => { cancelled = true; };
  }, [finishAuthentication, navigate, searchParams]);

  return (
    <main className="flex min-h-screen items-center justify-center bg-background p-5 text-center">
      {error ? (
        <section className="w-full max-w-md rounded-lg border border-destructive/30 bg-card p-6">
          <AlertTriangle className="mx-auto h-6 w-6 text-destructive" />
          <h1 className="mt-3 text-lg font-semibold">Authorization did not complete</h1>
          <p className="mt-2 text-sm leading-6 text-muted-foreground">{error}</p>
          <Button className="mt-5" onClick={() => navigate("/login", { replace: true })}>Return to sign in</Button>
        </section>
      ) : (
        <section>
          <Loader2 className="mx-auto h-7 w-7 animate-spin text-primary" />
          <h1 className="mt-4 text-lg font-semibold">Completing authorization</h1>
          <p className="mt-1 text-sm text-muted-foreground">Compass is validating the signed provider response.</p>
        </section>
      )}
    </main>
  );
}
