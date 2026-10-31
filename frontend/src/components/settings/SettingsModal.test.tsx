// @vitest-environment jsdom

import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import SettingsModal from "./SettingsModal";
import { preferencesApi } from "@/api";
import { useAuth } from "@/contexts/AuthContext";
import { useWorkbench } from "@/contexts/WorkbenchContext";
import { useTheme } from "@/components/ThemeProvider";

vi.mock("@/contexts/AuthContext", () => ({
  useAuth: vi.fn(),
}));

vi.mock("@/contexts/WorkbenchContext", () => ({
  useWorkbench: vi.fn(),
}));

vi.mock("@/components/ThemeProvider", () => ({
  useTheme: vi.fn(),
}));

vi.mock("@/api", () => ({
  preferencesApi: {
    getSettings: vi.fn(),
    updateSettings: vi.fn(),
    testProvider: vi.fn(),
    removeCredential: vi.fn(),
  },
  mcpApi: {
    getMcpServers: vi.fn().mockResolvedValue({ mcpServers: {}, managed: true }),
  },
  skillsApi: {
    listSkills: vi.fn().mockResolvedValue([]),
  },
  memoryApi: {
    listMemories: vi.fn().mockResolvedValue([]),
  },
}));

vi.mock("@/components/github/GitHubConnectionPanel", () => ({
  default: () => <div data-testid="github-panel">GitHub Panel</div>,
}));

vi.mock("./McpServerManager", () => ({
  default: () => <div data-testid="mcp-manager">MCP Manager</div>,
}));

vi.mock("./SkillsManager", () => ({
  default: () => <div data-testid="skills-manager">Skills Manager</div>,
}));

vi.mock("./MemoryManager", () => ({
  default: () => <div data-testid="memory-manager">Memory Manager</div>,
}));

describe("SettingsModal Enterprise Model Control Plane", () => {
  const mockUser = {
    id: "user-1",
    email: "dev@compass.local",
    display_name: "Lead Architect",
    avatar_url: null,
  };

  const mockDispatch = vi.fn();
  const mockSetTheme = vi.fn();
  const mockSignOut = vi.fn();
  const mockOnOpenChange = vi.fn();

  beforeEach(() => {
    vi.clearAllMocks();

    vi.mocked(useAuth).mockReturnValue({
      user: mockUser,
      status: "authenticated",
      refresh: vi.fn(),
      finishAuthentication: vi.fn(),
      signIn: vi.fn(),
      signUp: vi.fn(),
      signOut: mockSignOut,
    });

    vi.mocked(useWorkbench).mockReturnValue({
      state: { activeSkill: null } as any,
      dispatch: mockDispatch,
    } as any);

    vi.mocked(useTheme).mockReturnValue({
      theme: "dark",
      resolvedTheme: "dark",
      setTheme: mockSetTheme,
    });

    vi.mocked(preferencesApi.getSettings).mockResolvedValue({
      theme: "dark",
      model: "deepseek/deepseek-r1:free",
      llm_provider: "openrouter",
      language: "en",
      safe_mode: false,
      fast_mode: false,
      has_llm_api_key: false,
    });
  });

  afterEach(() => {
    cleanup();
  });

  it("renders model defaults tab and displays model capability badges", async () => {
    render(
      <SettingsModal
        open={true}
        onOpenChange={mockOnOpenChange}
        user={mockUser}
        initialTab="model"
      />
    );

    await waitFor(() => {
      expect(preferencesApi.getSettings).toHaveBeenCalled();
    });

    // Expect to see Model tab heading and presets
    expect(screen.getByText("Model defaults")).toBeTruthy();
    expect(screen.getByText("Free Models")).toBeTruthy();

    // Verify capability badges exist
    expect(screen.getAllByText("Reasoning").length).toBeGreaterThan(0);
    expect(screen.getAllByText("Coder").length).toBeGreaterThan(0);
    expect(screen.getAllByText("Vision").length).toBeGreaterThan(0);
  });

  it("selects a preset model and updates provider", async () => {
    render(
      <SettingsModal
        open={true}
        onOpenChange={mockOnOpenChange}
        user={mockUser}
        initialTab="model"
      />
    );

    await waitFor(() => {
      expect(preferencesApi.getSettings).toHaveBeenCalled();
    });

    // Click on Gemini 3.8 Flash preset
    const geminiButton = screen.getByRole("button", { name: /Gemini 3\.8 Flash/i });
    fireEvent.click(geminiButton);

    const modelInput = screen.getByPlaceholderText(/Provider model identifier/i) as HTMLInputElement;
    expect(modelInput.value).toBe("gemini/gemini-3.8-flash");

    // Provider select should now reflect google
    const providerSelect = screen.getByRole("combobox") as HTMLSelectElement;
    expect(providerSelect.value).toBe("google");
  });

  it("executes real provider latency ping and renders operational telemetry badge", async () => {
    vi.mocked(preferencesApi.testProvider).mockResolvedValue({
      provider: "openrouter",
      model: "deepseek/deepseek-r1:free",
      success: true,
      latency_ms: 128.4,
      error: null,
    });

    render(
      <SettingsModal
        open={true}
        onOpenChange={mockOnOpenChange}
        user={mockUser}
        initialTab="model"
      />
    );

    await waitFor(() => {
      expect(preferencesApi.getSettings).toHaveBeenCalled();
    });

    const testButton = screen.getByRole("button", { name: /Test provider/i });
    fireEvent.click(testButton);

    await waitFor(() => {
      expect(preferencesApi.testProvider).toHaveBeenCalledWith({
        provider: "openrouter",
        model: "deepseek/deepseek-r1:free",
      });
    });

    // Verify live latency ping badge appears
    await waitFor(() => {
      expect(screen.getByText(/128\.4ms · Operational/i)).toBeTruthy();
    });
  });

  it("displays transparent failure badge when provider test returns success: false", async () => {
    vi.mocked(preferencesApi.testProvider).mockResolvedValue({
      provider: "openrouter",
      model: "deepseek/deepseek-r1:free",
      success: false,
      latency_ms: 85.2,
      error: "Provider quota exceeded or rate limit hit",
    });

    render(
      <SettingsModal
        open={true}
        onOpenChange={mockOnOpenChange}
        user={mockUser}
        initialTab="model"
      />
    );

    await waitFor(() => {
      expect(preferencesApi.getSettings).toHaveBeenCalled();
    });

    const testButton = screen.getByRole("button", { name: /Test provider/i });
    fireEvent.click(testButton);

    await waitFor(() => {
      expect(screen.getByText(/Provider quota exceeded or rate limit hit/i)).toBeTruthy();
    });
  });

  it("handles test provider network exceptions gracefully", async () => {
    vi.mocked(preferencesApi.testProvider).mockRejectedValue(new Error("Connection timeout to gateway"));

    render(
      <SettingsModal
        open={true}
        onOpenChange={mockOnOpenChange}
        user={mockUser}
        initialTab="model"
      />
    );

    await waitFor(() => {
      expect(preferencesApi.getSettings).toHaveBeenCalled();
    });

    const testButton = screen.getByRole("button", { name: /Test provider/i });
    fireEvent.click(testButton);

    await waitFor(() => {
      expect(screen.getByRole("alert").textContent).toContain("Connection timeout to gateway");
    });
  });

  it("saves updated model settings", async () => {
    vi.mocked(preferencesApi.updateSettings).mockResolvedValue({
      theme: "dark",
      model: "qwen/qwen-2.5-coder-32b-instruct:free",
      llm_provider: "openrouter",
      language: "en",
      safe_mode: true,
      fast_mode: false,
      has_llm_api_key: false,
    });

    render(
      <SettingsModal
        open={true}
        onOpenChange={mockOnOpenChange}
        user={mockUser}
        initialTab="model"
      />
    );

    await waitFor(() => {
      expect(preferencesApi.getSettings).toHaveBeenCalled();
    });

    // Select Qwen Coder Free
    const qwenButton = screen.getByRole("button", { name: /Qwen 2\.5 Coder :free/i });
    fireEvent.click(qwenButton);

    const saveButton = screen.getByRole("button", { name: /Save changes/i });
    fireEvent.click(saveButton);

    await waitFor(() => {
      expect(preferencesApi.updateSettings).toHaveBeenCalledWith(
        expect.objectContaining({
          model: "qwen/qwen-2.5-coder-32b-instruct:free",
          llm_provider: "openrouter",
        })
      );
    });
  });
});
