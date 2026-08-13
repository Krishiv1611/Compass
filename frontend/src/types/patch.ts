export type PatchStatus = "pending" | "applied" | "rejected" | "reverted";

export interface PatchChange {
  path: string;
  type?: "create" | "edit" | "delete" | string;
  before?: string;
  after?: string;
  content?: string;
  diff?: string;
  status?: PatchStatus;
  additions?: number;
  deletions?: number;
}

export interface WorkspacePatch {
  id: string;
  version: number;
  workspace_id?: string;
  status: PatchStatus;
  changes: PatchChange[];
  summary?: string;
  created_at?: string;
}
