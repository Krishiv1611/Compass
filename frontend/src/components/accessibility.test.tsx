// @vitest-environment jsdom
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import ChatInput from "./chat/ChatInput";
import FileExplorer from "./sandbox/FileExplorer";
import TopBar from "./layout/TopBar";
import ProjectRail from "./layout/ProjectRail";
import AppLayout from "./layout/AppLayout";
import { MemoryRouter } from "react-router-dom";

const { searchFiles, navigate, deleteSession, sessionHook, setMode } = vi.hoisted(() => ({
  searchFiles: vi.fn(),
  navigate: vi.fn(),
  deleteSession: vi.fn(),
  sessionHook: vi.fn(),
  setMode: vi.fn(),
}));

vi.mock("@/api", () => ({
  workspaceApi: { searchFiles },
  sessionsApi: { forkSession: vi.fn() },
}));

vi.mock("@/contexts/WorkbenchContext", () => ({
  useWorkbench: () => ({
    state: { mode: "ask", selectedContextFiles: [], settingsRequest: { version: 0 }, activeWorkspaceId: null },
    setMode,
    dispatch: vi.fn(),
    startNewTask: vi.fn(),
  }),
}));

vi.mock("@/hooks/useSessions", () => ({
  useSessions: (...args: unknown[]) => sessionHook(...args),
}));

vi.mock("@/contexts/AuthContext", () => ({ useAuth: () => ({ user: null }) }));
vi.mock("./layout/StatusBar", () => ({ default: () => null }));

function sessionState() {
  return {
    sessions: [{ id: "session-1", title: "Task one", updated_at: "2026-01-01", message_count: 1 }],
    isLoadingSessions: false,
    hasMoreSessions: false,
    loadMoreSessions: vi.fn(),
    renameSession: vi.fn(),
    deleteSession,
    fetchSessions: vi.fn(),
  };
}

vi.mock("react-router-dom", async (importOriginal) => ({
  ...(await importOriginal<typeof import("react-router-dom")>()),
  useNavigate: () => navigate,
  useSearchParams: () => [new URLSearchParams("session=session-1")],
}));

afterEach(cleanup);

describe("web accessibility", () => {
  beforeEach(() => {
    searchFiles.mockReset();
    navigate.mockReset();
    deleteSession.mockReset();
    sessionHook.mockImplementation(sessionState);
    setMode.mockReset();
  });

  it("names the mobile menu, settings, and session action controls", () => {
    render(
      <TopBar
        title="Task one"
        isMobileOpen={false}
        setIsMobileOpen={vi.fn()}
        isDesktopSidebarOpen
        setIsDesktopSidebarOpen={vi.fn()}
        SidebarContent={<div>Sidebar</div>}
        user={null}
        onOpenSettings={vi.fn()}
      />,
    );

    expect(screen.getByRole("button", { name: "Open navigation" })).toBeTruthy();
    expect(screen.getByRole("button", { name: "Settings" })).toBeTruthy();
  });

  it("names attachment and context removal controls", () => {
    render(<ChatInput onSend={vi.fn()} initialContextPaths={["src/app.ts"]} />);

    expect(screen.getByRole("button", { name: "Remove app.ts from context" })).toBeTruthy();
  });

  it("navigates mention options with the keyboard and escapes the listbox", async () => {
    searchFiles.mockResolvedValue(["src/app.ts", "src/main.ts"]);
    const user = userEvent.setup();
    render(<ChatInput onSend={vi.fn()} workspaceId="workspace-1" />);

    const input = screen.getByPlaceholderText("Describe the task or ask about this project");
    await user.type(input, "@src");
    await screen.findByRole("listbox", { name: "Project files" });
    expect(screen.getAllByRole("option")).toHaveLength(2);

    await user.keyboard("{ArrowDown}{Enter}");
    expect(screen.getByText("main.ts")).toBeTruthy();
    expect(screen.queryByRole("listbox")).toBeNull();

    await user.type(input, " @src");
    await screen.findByRole("listbox", { name: "Project files" });
    await user.keyboard("{Escape}");
    expect(screen.queryByRole("listbox")).toBeNull();
  });

  it("uses one roving file-tree tab stop and supports all tree navigation keys", () => {
    render(
      <FileExplorer
        files={[
          { name: "one.ts", path: "one.ts", type: "file" },
          { name: "two.ts", path: "two.ts", type: "file" },
          { name: "three.ts", path: "three.ts", type: "file" },
        ]}
        onFileSelect={vi.fn()}
      />,
    );

    const items = screen.getAllByRole("treeitem");
    expect(items.filter((item) => item.getAttribute("tabindex") === "0")).toHaveLength(1);
    fireEvent.keyDown(items[0], { key: "ArrowDown" });
    expect(document.activeElement).toBe(items[1]);
    fireEvent.keyDown(items[1], { key: "End" });
    expect(document.activeElement).toBe(items[2]);
    fireEvent.keyDown(items[2], { key: "Home" });
    expect(document.activeElement).toBe(items[0]);
    fireEvent.keyDown(items[0], { key: "ArrowUp" });
    expect(document.activeElement).toBe(items[2]);
  });

  it("moves right into the first child of an expanded folder", () => {
    render(
      <FileExplorer
        files={[
          { name: "src", path: "src", type: "folder", children: [{ name: "app.ts", path: "src/app.ts", type: "file" }] },
          { name: "readme.md", path: "readme.md", type: "file" },
        ]}
        onFileSelect={vi.fn()}
      />,
    );

    const folder = screen.getByRole("treeitem", { name: "src" });
    fireEvent.keyDown(folder, { key: "ArrowRight" });
    expect(document.activeElement).toBe(screen.getByRole("treeitem", { name: "app.ts" }));
  });

  it("uses one roving tab stop and directional keys to select conversation modes", () => {
    render(<ChatInput onSend={vi.fn()} />);

    const radios = screen.getAllByRole("radio");
    expect(radios.filter((radio) => radio.getAttribute("tabindex") === "0")).toHaveLength(1);
    fireEvent.keyDown(screen.getByRole("radio", { name: "Ask" }), { key: "ArrowRight" });
    expect(document.activeElement).toBe(screen.getByRole("radio", { name: "Edit" }));
    expect(setMode).toHaveBeenCalledWith("edit");
  });

  it("keeps the delete dialog open and does not navigate when deletion fails", async () => {
    deleteSession.mockRejectedValueOnce(new Error("Delete denied"));
    const user = userEvent.setup();
    render(<ProjectRail sessionState={sessionState()} onOpenSettings={vi.fn()} />);

    await user.click(screen.getByRole("button", { name: "Task actions for Task one" }));
    await user.click(await screen.findByRole("menuitem", { name: "Delete" }));
    await user.click(screen.getByRole("button", { name: "Delete" }));

    expect(await screen.findByRole("dialog", { name: "Delete chat" })).toBeTruthy();
    expect(navigate).not.toHaveBeenCalled();
  });

  it("uses one session source for the desktop and mobile rails", () => {
    render(<MemoryRouter><AppLayout><div>Chat</div></AppLayout></MemoryRouter>);

    expect(sessionHook).toHaveBeenCalledTimes(1);
  });
});
