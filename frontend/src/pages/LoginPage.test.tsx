// @vitest-environment jsdom

import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import LoginPage from "./LoginPage";
import { authApi } from "@/api";
import { useAuth } from "@/contexts/AuthContext";

const { mockNavigate } = vi.hoisted(() => ({
  mockNavigate: vi.fn(),
}));

vi.mock("react-router-dom", async () => {
  const actual = await vi.importActual("react-router-dom");
  return {
    ...actual,
    useNavigate: () => mockNavigate,
  };
});

vi.mock("@/contexts/AuthContext", () => ({
  useAuth: vi.fn(),
}));

vi.mock("@/api", () => ({
  authApi: {
    login: vi.fn(),
    register: vi.fn(),
    getGoogleAuthUrl: vi.fn(),
    getGithubAuthUrl: vi.fn(),
  },
}));

describe("LoginPage Luxury Split-Screen Showcase", () => {
  const mockSignIn = vi.fn();
  const mockSignUp = vi.fn();

  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(useAuth).mockReturnValue({
      status: "anonymous",
      user: null,
      refresh: vi.fn(),
      finishAuthentication: vi.fn(),
      signIn: mockSignIn,
      signUp: mockSignUp,
      signOut: vi.fn(),
    });
  });

  afterEach(() => {
    cleanup();
  });

  it("renders architecture telemetry showcase on the left panel", () => {
    render(<LoginPage />);

    // Brand and headline
    expect(screen.getByText("Compass Studio")).toBeTruthy();
    expect(screen.getByRole("heading", { name: /autonomous software engineering studio/i })).toBeTruthy();

    // Live architecture telemetry ticker
    expect(screen.getByText("Agent State Machine")).toBeTruthy();
    expect(screen.getByText(/Graph Workflow: Active/i)).toBeTruthy();

    expect(screen.getByText("Execution Sandboxes")).toBeTruthy();
    expect(screen.getByText(/Subprocess Local Runner \+ Cloud E2B Firecracker/i)).toBeTruthy();

    expect(screen.getByText("Hybrid Safety Gate")).toBeTruthy();
    expect(screen.getByText(/Auto-approves safe tests, gates destructive changes/i)).toBeTruthy();

    expect(screen.getByText("Dual-Telemetry Studio")).toBeTruthy();
    expect(screen.getByText(/Canvas visual inspector \+ terminal cockpit/i)).toBeTruthy();

    // Integrated stack capability tags
    expect(screen.getByText("Vite / React")).toBeTruthy();
    expect(screen.getByText("FastAPI")).toBeTruthy();
    expect(screen.getByText("CodeMirror")).toBeTruthy();
    expect(screen.getByText("WebContainers")).toBeTruthy();
    expect(screen.getByText("Git Staging")).toBeTruthy();
  });

  it("renders OAuth provider button for GitHub and initiates oauth flow", async () => {
    const originalAssign = window.location.assign;
    const assignMock = vi.fn();
    Object.defineProperty(window, "location", {
      writable: true,
      value: { ...window.location, assign: assignMock, origin: "http://localhost:3000", pathname: "/login", search: "" },
    });

    vi.mocked(authApi.getGithubAuthUrl).mockResolvedValueOnce({
      url: "https://github.com/login/oauth/authorize?client_id=123",
    });

    render(<LoginPage />);

    const githubBtn = screen.getByRole("button", { name: /continue with github/i });
    expect(githubBtn).toBeTruthy();

    fireEvent.click(githubBtn);
    await waitFor(() => {
      expect(authApi.getGithubAuthUrl).toHaveBeenCalledWith("login", "/login");
      expect(assignMock).toHaveBeenCalledWith("https://github.com/login/oauth/authorize?client_id=123");
    });

    window.location.assign = originalAssign;
  });

  it("renders OAuth provider button for Google and initiates oauth flow", async () => {
    const originalAssign = window.location.assign;
    const assignMock = vi.fn();
    Object.defineProperty(window, "location", {
      writable: true,
      value: { ...window.location, assign: assignMock, origin: "http://localhost:3000", pathname: "/login", search: "" },
    });

    vi.mocked(authApi.getGoogleAuthUrl).mockResolvedValueOnce({
      url: "https://accounts.google.com/o/oauth2/v2/auth?client_id=456",
    });

    render(<LoginPage />);

    const googleBtn = screen.getByRole("button", { name: /google/i });
    expect(googleBtn).toBeTruthy();

    fireEvent.click(googleBtn);
    await waitFor(() => {
      expect(authApi.getGoogleAuthUrl).toHaveBeenCalledWith("http://localhost:3000/auth/callback", "login", "/login");
      expect(assignMock).toHaveBeenCalledWith("https://accounts.google.com/o/oauth2/v2/auth?client_id=456");
    });

    window.location.assign = originalAssign;
  });

  it("renders Sign in and Sign up tabs and toggles between them", () => {
    render(<LoginPage />);

    // Initially in sign-in mode
    expect(screen.getByRole("tab", { name: /sign in/i })).toBeTruthy();
    expect(screen.getByRole("tab", { name: /sign up/i })).toBeTruthy();
    expect(screen.getByRole("button", { name: /sign in with email/i })).toBeTruthy();
    expect(screen.queryByPlaceholderText("Display Name")).toBeNull();

    // Switch to sign-up mode
    fireEvent.click(screen.getByRole("tab", { name: /sign up/i }));
    expect(screen.getByPlaceholderText("Display Name")).toBeTruthy();
    expect(screen.getByRole("button", { name: /sign up with email/i })).toBeTruthy();

    // Switch back to sign-in mode
    fireEvent.click(screen.getByRole("tab", { name: /sign in/i }));
    expect(screen.queryByPlaceholderText("Display Name")).toBeNull();
    expect(screen.getByRole("button", { name: /sign in with email/i })).toBeTruthy();
  });

  it("redirects to /chat when user is already authenticated", () => {
    vi.mocked(useAuth).mockReturnValue({
      status: "authenticated",
      user: { id: "u-1", email: "dev@compass.local", display_name: "Lead Dev" },
      refresh: vi.fn(),
      finishAuthentication: vi.fn(),
      signIn: mockSignIn,
      signUp: mockSignUp,
      signOut: vi.fn(),
    });

    render(<LoginPage />);
    expect(mockNavigate).toHaveBeenCalledWith("/chat", { replace: true });
  });

  it("displays error message on invalid email submission", async () => {
    render(<LoginPage />);

    const emailInput = screen.getByLabelText(/email address/i);
    const passwordInput = screen.getByLabelText(/password/i);
    const submitButton = screen.getByRole("button", { name: /sign in with email/i });

    fireEvent.change(emailInput, { target: { value: "invalid-email" } });
    fireEvent.change(passwordInput, { target: { value: "secret123" } });
    fireEvent.submit(submitButton.closest("form")!);

    expect(await screen.findByRole("alert")).toBeTruthy();
    expect(screen.getByText("Enter a valid email address.")).toBeTruthy();
  });

  it("submits sign in form successfully and navigates", async () => {
    mockSignIn.mockResolvedValueOnce(undefined);

    render(<LoginPage />);

    const emailInput = screen.getByLabelText(/email address/i);
    const passwordInput = screen.getByLabelText(/password/i);
    const submitButton = screen.getByRole("button", { name: /sign in with email/i });

    fireEvent.change(emailInput, { target: { value: "engineer@company.com" } });
    fireEvent.change(passwordInput, { target: { value: "password123" } });
    fireEvent.submit(submitButton.closest("form")!);

    await waitFor(() => {
      expect(mockSignIn).toHaveBeenCalledWith({
        email: "engineer@company.com",
        password: "password123",
      });
      expect(mockNavigate).toHaveBeenCalledWith("/chat", { replace: true });
    });
  });

  it("submits sign up form successfully and navigates", async () => {
    mockSignUp.mockResolvedValueOnce(undefined);

    render(<LoginPage />);

    // Switch to sign-up
    fireEvent.click(screen.getByRole("tab", { name: /sign up/i }));

    const emailInput = screen.getByLabelText(/email address/i);
    const displayNameInput = screen.getByLabelText(/display name/i);
    const passwordInput = screen.getByLabelText(/password/i);
    const submitButton = screen.getByRole("button", { name: /sign up with email/i });

    fireEvent.change(emailInput, { target: { value: "newdev@company.com" } });
    fireEvent.change(displayNameInput, { target: { value: "Alex Dev" } });
    fireEvent.change(passwordInput, { target: { value: "password123" } });
    fireEvent.submit(submitButton.closest("form")!);

    await waitFor(() => {
      expect(mockSignUp).toHaveBeenCalledWith({
        email: "newdev@company.com",
        password: "password123",
        display_name: "Alex Dev",
      });
      expect(mockNavigate).toHaveBeenCalledWith("/chat", { replace: true });
    });
  });
});
