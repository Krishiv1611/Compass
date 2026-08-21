// @vitest-environment jsdom
import { afterEach, expect, it, vi } from "vitest";
import { cleanup, renderHook, waitFor } from "@testing-library/react";
import { useSessions } from "./useSessions";

const { listSessions, deleteSession, toastError } = vi.hoisted(() => ({
  listSessions: vi.fn(),
  deleteSession: vi.fn(),
  toastError: vi.fn(),
}));

vi.mock("@/api", () => ({ sessionsApi: { listSessions, deleteSession, renameSession: vi.fn() } }));
vi.mock("@/contexts/AuthContext", () => ({ useAuth: () => ({ status: "authenticated" }) }));
vi.mock("@/contexts/WorkbenchContext", () => ({ useWorkbench: () => ({ state: { sessionsVersion: 0 } }) }));
vi.mock("react-toastify", () => ({ toast: { success: vi.fn(), error: toastError } }));

afterEach(cleanup);

it("rejects a failed session deletion so callers can keep their UI open", async () => {
  listSessions.mockResolvedValue([]);
  deleteSession.mockRejectedValueOnce(new Error("Delete denied"));
  const { result } = renderHook(() => useSessions(null));
  await waitFor(() => expect(listSessions).toHaveBeenCalled());

  await expect(result.current.deleteSession("session-1")).rejects.toThrow("Delete denied");
  expect(toastError).toHaveBeenCalledWith("Delete denied");
});
