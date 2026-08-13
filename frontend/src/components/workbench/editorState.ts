export interface EditorEntry {
  content: string;
  savedContent: string;
  invalidated: boolean;
}

export interface EditorState {
  entries: Record<string, EditorEntry>;
  activeLoad: { workspaceId: string; path: string; generation: number } | null;
}

export const editorKey = (workspaceId: string, path: string) => `${workspaceId}\u0000${path}`;
export const emptyEditorState = (): EditorState => ({ entries: {}, activeLoad: null });

export function beginLoad(state: EditorState, workspaceId: string, path: string, generation: number): EditorState {
  return { ...state, activeLoad: { workspaceId, path, generation } };
}

export function storeLoadedFile(state: EditorState, load: { workspaceId: string; path: string; content: string; generation: number }): EditorState {
  const active = state.activeLoad;
  if (!active || active.workspaceId !== load.workspaceId || active.path !== load.path || active.generation !== load.generation) return state;
  return {
    activeLoad: null,
    entries: { ...state.entries, [editorKey(load.workspaceId, load.path)]: { content: load.content, savedContent: load.content, invalidated: false } },
  };
}

export const selectEntry = (state: EditorState, workspaceId: string, path: string) => state.entries[editorKey(workspaceId, path)];

export function editFile(state: EditorState, workspaceId: string, path: string, content: string): EditorState {
  const key = editorKey(workspaceId, path);
  const entry = state.entries[key];
  if (!entry) return state;
  return { ...state, entries: { ...state.entries, [key]: { ...entry, content } } };
}

export function markSaved(state: EditorState, workspaceId: string, path: string, savedContent: string): EditorState {
  const key = editorKey(workspaceId, path);
  const entry = state.entries[key];
  if (!entry) return state;
  return { ...state, entries: { ...state.entries, [key]: { ...entry, savedContent, invalidated: false } } };
}

export const isDirty = (state: EditorState, workspaceId: string, path: string) => {
  const entry = selectEntry(state, workspaceId, path);
  return Boolean(entry && entry.content !== entry.savedContent);
};

export function invalidateWorkspace(state: EditorState, workspaceId: string): EditorState {
  const entries = Object.fromEntries(Object.entries(state.entries).map(([key, entry]) => [
    key,
    key.startsWith(`${workspaceId}\u0000`) ? { ...entry, invalidated: true } : entry,
  ]));
  return { ...state, entries };
}

export function workspaceChangeNeedsConfirmation(dirtyWorkspaceIds: string[], currentWorkspaceId: string | null, nextWorkspaceId: string | null): boolean {
  return Boolean(currentWorkspaceId && currentWorkspaceId !== nextWorkspaceId && dirtyWorkspaceIds.includes(currentWorkspaceId));
}

export const shouldReloadEntry = (state: EditorState, workspaceId: string, path: string) => {
  if (state.activeLoad?.workspaceId === workspaceId && state.activeLoad.path === path) return false;
  const entry = selectEntry(state, workspaceId, path);
  return !entry || (entry.invalidated && !isDirty(state, workspaceId, path));
};
