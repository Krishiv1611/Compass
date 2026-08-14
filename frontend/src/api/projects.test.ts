import { beforeEach, describe, expect, it, vi } from "vitest";

const mocks = vi.hoisted(() => ({
  post: vi.fn(),
}));

vi.mock("./client", () => ({
  default: {
    get: vi.fn(),
    post: mocks.post,
    patch: vi.fn(),
    delete: vi.fn(),
    put: vi.fn(),
  },
  API_BASE_URL: "/api",
}));

import { sessionsApi } from "./projects";


describe("sessionsApi fork", () => {
  beforeEach(() => mocks.post.mockReset());

  it("posts the selected checkpoint and returns the forked session", async () => {
    mocks.post.mockResolvedValue({ data: { id: "forked-session" } });

    const result = await sessionsApi.forkSession("source-session", "checkpoint-1");

    expect(mocks.post).toHaveBeenCalledWith("/sessions/source-session/fork", {
      checkpoint_id: "checkpoint-1",
    });
    expect(result.id).toBe("forked-session");
  });
});
