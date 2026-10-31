// @vitest-environment jsdom

import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import McpServerManager from "./McpServerManager";
import { mcpApi, toolsApi } from "@/api";

vi.mock("@/api", () => ({
  mcpApi: {
    getMcpServers: vi.fn(),
  },
  toolsApi: {
    listTools: vi.fn(),
  },
}));

describe("McpServerManager Capability & Tool Inspector", () => {
  const sampleTools = [
    {
      name: "read_file",
      description: "Read the complete contents of a file at the specified workspace path.",
      environment: "web",
    },
    {
      name: "write_to_file",
      description: "Create or overwrite a file with the given content.",
      environment: "web",
    },
    {
      name: "shell_execute",
      description: "Execute bash or terminal commands in the workspace environment.",
      environment: "tui",
    },
    {
      name: "grep_search",
      description: "Perform fast ripgrep regex queries across the workspace codebase.",
      environment: "web",
    },
    {
      name: "todo",
      description: "Manage autonomous sub-goal checklists and step status.",
      environment: "web",
    },
  ];

  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(mcpApi.getMcpServers).mockResolvedValue({
      mcpServers: { "memory-indexer": {} },
      managed: true,
      message: "Hosted MCP capabilities are server-managed. Configure command MCP servers in the local TUI.",
    });
    vi.mocked(toolsApi.listTools).mockResolvedValue(sampleTools);
  });

  afterEach(() => {
    cleanup();
  });

  it("fetches and renders the active agent tool catalog and remote MCP capabilities", async () => {
    render(<McpServerManager />);

    await waitFor(() => {
      expect(toolsApi.listTools).toHaveBeenCalled();
      expect(mcpApi.getMcpServers).toHaveBeenCalled();
    });

    // Heading and telemetry HUD
    expect(screen.getByText("Agent Capabilities & Tools")).toBeTruthy();
    expect(screen.getByText(/5 Registered Tools/i)).toBeTruthy();

    // Check individual tool cards
    expect(screen.getByText("read_file")).toBeTruthy();
    expect(screen.getByText("write_to_file")).toBeTruthy();
    expect(screen.getByText("shell_execute")).toBeTruthy();
    expect(screen.getByText("grep_search")).toBeTruthy();
    expect(screen.getByText("todo")).toBeTruthy();

    // Check environment badges
    expect(screen.getAllByText("Web & Studio").length).toBe(4);
    expect(screen.getByText("Host / TUI Gated")).toBeTruthy();

    // Check remote MCP status
    expect(screen.getByText(/1 approved remote capability/i)).toBeTruthy();
  });

  it("filters tools dynamically using the search bar", async () => {
    render(<McpServerManager />);

    await waitFor(() => {
      expect(toolsApi.listTools).toHaveBeenCalled();
    });

    const searchInput = screen.getByPlaceholderText(/Filter capabilities by name or description/i);
    fireEvent.change(searchInput, { target: { value: "shell" } });

    // shell_execute should be visible
    expect(screen.getByText("shell_execute")).toBeTruthy();

    // Other tools should be filtered out
    expect(screen.queryByText("read_file")).toBeNull();
    expect(screen.queryByText("grep_search")).toBeNull();
  });

  it("displays security policy indicators for gated tools vs safe tools", async () => {
    render(<McpServerManager />);

    await waitFor(() => {
      expect(toolsApi.listTools).toHaveBeenCalled();
    });

    // shell_execute should show approval required or gated badge
    expect(screen.getByText("Approval Required")).toBeTruthy();

    // safe tools should show auto-approved badges
    expect(screen.getAllByText("Auto-Approved").length).toBeGreaterThan(0);
  });

  it("renders graceful fallback message when tools list fails to load", async () => {
    vi.mocked(toolsApi.listTools).mockRejectedValue(new Error("Failed to load catalog"));

    render(<McpServerManager />);

    await waitFor(() => {
      expect(screen.getByText(/Capability catalog is temporarily unavailable/i)).toBeTruthy();
    });
  });
});
