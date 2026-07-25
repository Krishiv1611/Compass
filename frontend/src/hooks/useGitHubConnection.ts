import { useCallback, useEffect, useState } from "react";
import { githubApi } from "@/api";
import type { GitHubConnectionStatus } from "@/types/github";

export function useGitHubConnection(enabled = true) {
  const [status, setStatus] = useState<GitHubConnectionStatus | null>(null);
  const [loading, setLoading] = useState(enabled);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async (validate = false) => {
    if (!enabled) return;
    setLoading(true);
    setError(null);
    try {
      setStatus(validate ? await githubApi.validateConnection() : await githubApi.getStatus());
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "Could not check GitHub connection");
      setStatus(null);
    } finally {
      setLoading(false);
    }
  }, [enabled]);

  useEffect(() => { void refresh(); }, [refresh]);
  return { status, loading, error, refresh, setStatus };
}
