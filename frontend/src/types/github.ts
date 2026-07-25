export interface GitHubRepository {
  id: number;
  full_name: string;
  default_branch: string;
  private: boolean;
  archived?: boolean;
  html_url?: string;
  updated_at?: string;
  owner?: { login: string };
  permissions?: { pull?: boolean; push?: boolean; admin?: boolean };
}

export interface GitHubBranch {
  name: string;
  sha?: string;
  protected?: boolean;
  commit?: { sha: string; url?: string };
}

export interface GitHubCapabilities {
  listRepositories: boolean;
  readContents: boolean;
  writeContents: boolean;
  createPullRequests: boolean;
}

export interface GitHubConnectionStatus {
  connected: boolean;
  method?: "github_app" | "oauth" | "pat";
  login?: string;
  avatarUrl?: string;
  repositoryCount?: number;
  expiresAt?: string;
  lastValidatedAt?: string;
  maskedCredential?: string;
  capabilities: GitHubCapabilities;
}

export interface GitHubRepositoryPage {
  repositories: GitHubRepository[];
  nextCursor?: string | null;
  owners?: string[];
}

export interface GitHubPullRequest {
  number: number;
  state: "open" | "closed" | "merged" | string;
  url: string;
}
