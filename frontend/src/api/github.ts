import api from "./client";
import type {
  GitHubBranch,
  GitHubConnectionStatus,
  GitHubPullRequest,
  GitHubRepositoryPage,
} from "@/types/github";

export interface ImportRepositoryRequest {
  session_id: string;
  owner: string;
  repo: string;
  branch: string;
}

export const githubApi = {
  getStatus: async (): Promise<GitHubConnectionStatus> =>
    (await api.get("/github/status")).data,

  getOAuthUrl: async (returnTo = "/chat"): Promise<{ url: string }> =>
    (await api.get("/github/oauth/url", {
      params: { intent: "connect_github", return_to: returnTo },
    })).data,

  exchangeOAuth: async (code: string, state: string): Promise<GitHubConnectionStatus> =>
    (await api.post("/github/oauth/exchange", { code, state })).data,

  connectPat: async (token: string): Promise<GitHubConnectionStatus> =>
    (await api.post("/github/connections/pat", { token })).data,

  validateConnection: async (): Promise<GitHubConnectionStatus> =>
    (await api.post("/github/connection/validate")).data,

  disconnect: async (): Promise<void> => {
    await api.delete("/github/connection");
  },

  listRepositories: async (
    params: { cursor?: string; owner?: string; query?: string } = {},
  ): Promise<GitHubRepositoryPage> =>
    (await api.get("/github/repositories", { params })).data,

  listBranches: async (owner: string, repo: string): Promise<GitHubBranch[]> =>
    (await api.get(`/github/repositories/${owner}/${repo}/branches`)).data,

  importRepository: async (data: ImportRepositoryRequest) =>
    (await api.post("/github/import", data)).data,

  createBranch: async (data: {
    workspace_id: string;
    owner: string;
    repo: string;
    source_branch: string;
    name: string;
  }) => (await api.post("/github/publish/branch", data)).data,

  commit: async (data: {
    workspace_id: string;
    owner: string;
    repo: string;
    branch: string;
    message: string;
    paths: string[];
  }) => (await api.post("/github/publish/commit", data)).data,

  openPullRequest: async (data: {
    workspace_id: string;
    owner: string;
    repo: string;
    title: string;
    body?: string;
    head: string;
    base: string;
    draft?: boolean;
  }): Promise<GitHubPullRequest> =>
    (await api.post("/github/publish/pull-request", data)).data,
};
