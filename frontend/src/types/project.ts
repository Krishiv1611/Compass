export interface Workspace {
  id: string;
  name: string;
  created_at?: string;
  session_id?: string;
  source_type?: "upload" | "github" | "empty" | null;
  git_branch?: string | null;
  git_head?: string | null;
}

export interface WorkspaceContext {
  workspace_id?: string;
  git_remote?: string | null;
  git_branch?: string | null;
  git_head?: string | null;
  context_version?: string | null;
  indexed_at?: string | null;
  indexed_file_count?: number;
  indexed_chunk_count?: number;
  context_tokens?: number | null;
  selected_tokens?: number | null;
  metadata?: Record<string, unknown>;
}

export interface WorkspaceTreeResponse {
  tree?: FileItem[];
  children?: FileItem[];
}

export interface WorkspaceFileResponse {
  content: string;
}

export interface FileItem {
  path: string;
  name: string;
  type: "file" | "folder";
  children?: FileItem[];
}
