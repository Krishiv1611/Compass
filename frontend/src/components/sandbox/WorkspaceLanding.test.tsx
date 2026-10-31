// @vitest-environment jsdom

import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import WorkspaceLanding from "./WorkspaceLanding";
import { workspaceApi } from "@/api";

vi.mock("@/api", () => ({
  workspaceApi: {
    listWorkspaces: vi.fn(),
    createWorkspace: vi.fn(),
    attachWorkspace: vi.fn(),
    uploadFolder: vi.fn(),
  },
}));

describe("WorkspaceLanding Mission Control", () => {
  it("renders fast action bar, telemetry HUD, and lists real workspaces", async () => {
    vi.mocked(workspaceApi.listWorkspaces).mockResolvedValueOnce([
      {
        id: "ws-12345678",
        name: "compass-core",
        git_branch: "main",
        source_type: "github",
        created_at: "2026-10-31T10:00:00Z",
      },
    ]);

    const onWorkspaceReady = vi.fn();
    render(
      <WorkspaceLanding
        sessionId="test-session"
        ensureSession={vi.fn().mockResolvedValue("test-session")}
        onWorkspaceReady={onWorkspaceReady}
      />
    );

    expect(screen.getByText(/Mission Control/i)).toBeTruthy();
    expect(screen.getByText(/Autonomous Workspaces Hub/i)).toBeTruthy();
    expect(screen.getByText(/LLM Engine: Ready/i)).toBeTruthy();
    expect(screen.getByText(/Runner: Local Subprocess & E2B/i)).toBeTruthy();

    // Fast actions
    expect(screen.getByText(/New Task/i)).toBeTruthy();
    expect(screen.getByText(/Clone Git Repo/i)).toBeTruthy();
    expect(screen.getByText(/Open Folder/i)).toBeTruthy();

    // Workspace listed
    expect(await screen.findByText("compass-core")).toBeTruthy();
    expect(screen.getByText("main")).toBeTruthy();

    // Select workspace
    fireEvent.click(screen.getByText("compass-core"));
    await waitFor(() => {
      expect(workspaceApi.attachWorkspace).toHaveBeenCalledWith("test-session", "ws-12345678");
      expect(onWorkspaceReady).toHaveBeenCalledWith("ws-12345678", "compass-core");
    });
  });
});
