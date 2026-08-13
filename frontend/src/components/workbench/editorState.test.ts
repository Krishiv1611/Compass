import { describe, expect, it } from "vitest";
import {
  beginLoad,
  editFile,
  emptyEditorState,
  invalidateWorkspace,
  isDirty,
  markSaved,
  selectEntry,
  storeLoadedFile,
  workspaceChangeNeedsConfirmation,
  shouldReloadEntry,
} from "./editorState";

describe("workspace-scoped editor state", () => {
  it("does not share same-path content between projects", () => {
    let state = beginLoad(emptyEditorState(), "A", "src/app.ts", 1);
    state = storeLoadedFile(state, { workspaceId: "A", path: "src/app.ts", content: "A", generation: 1 });
    state = beginLoad(state, "B", "src/app.ts", 2);
    state = storeLoadedFile(state, { workspaceId: "B", path: "src/app.ts", content: "B", generation: 2 });

    expect(selectEntry(state, "A", "src/app.ts")?.content).toBe("A");
    expect(selectEntry(state, "B", "src/app.ts")?.content).toBe("B");
  });

  it("ignores late file loads", () => {
    const state = storeLoadedFile(
      beginLoad(emptyEditorState(), "B", "b.ts", 2),
      { workspaceId: "A", path: "a.ts", content: "late", generation: 1 },
    );

    expect(selectEntry(state, "A", "a.ts")).toBeUndefined();
  });

  it("clears dirty state only for the content that actually saved", () => {
    let state = beginLoad(emptyEditorState(), "A", "a.ts", 1);
    state = storeLoadedFile(state, { workspaceId: "A", path: "a.ts", content: "old", generation: 1 });
    state = editFile(state, "A", "a.ts", "saving");
    state = editFile(state, "A", "a.ts", "typed while saving");
    state = markSaved(state, "A", "a.ts", "saving");

    expect(selectEntry(state, "A", "a.ts")?.content).toBe("typed while saving");
    expect(isDirty(state, "A", "a.ts")).toBe(true);
  });

  it("marks dirty files as conflicted after project changes", () => {
    let state = beginLoad(emptyEditorState(), "A", "a.ts", 1);
    state = storeLoadedFile(state, { workspaceId: "A", path: "a.ts", content: "old", generation: 1 });
    state = editFile(state, "A", "a.ts", "local");
    state = invalidateWorkspace(state, "A");

    expect(selectEntry(state, "A", "a.ts")?.invalidated).toBe(true);
    expect(workspaceChangeNeedsConfirmation(["A"], "A", "B")).toBe(true);
    expect(workspaceChangeNeedsConfirmation(["A"], "A", "A")).toBe(false);
  });

  it("reloads an invalidated clean file but preserves an invalidated dirty file", () => {
    let state = beginLoad(emptyEditorState(), "A", "a.ts", 1);
    state = storeLoadedFile(state, { workspaceId: "A", path: "a.ts", content: "old", generation: 1 });
    state = invalidateWorkspace(state, "A");
    expect(shouldReloadEntry(state, "A", "a.ts")).toBe(true);

    state = editFile(state, "A", "a.ts", "local");
    expect(shouldReloadEntry(state, "A", "a.ts")).toBe(false);
  });

  it("does not restart a load that is already in flight", () => {
    const state = beginLoad(emptyEditorState(), "A", "a.ts", 1);
    expect(shouldReloadEntry(state, "A", "a.ts")).toBe(false);
  });
});
