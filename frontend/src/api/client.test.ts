import { describe, expect, it } from "vitest";

import { buildWebSocketProtocols, buildWebSocketUrl } from "./client";


describe("API URL contract", () => {
  it("uses the same-origin API path and subprotocol credentials", () => {
    expect(buildWebSocketUrl("abc", "https://compass.test")).toBe(
      "wss://compass.test/api/chat/ws/abc",
    );
    expect(buildWebSocketProtocols("token")).toEqual([
      "compass.v1",
      "compass.jwt.token",
    ]);
  });
});
