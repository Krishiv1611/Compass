import { afterEach, describe, expect, it, vi } from "vitest";
import { createFakeSocketFactory } from "../test/fakeSocket";
import { RunController } from "./RunController";

const startInput = (sessionId: string, content = "hello") => ({
  sessionId,
  content,
  mode: "edit" as const,
  contextFiles: [] as string[],
});

describe("RunController", () => {
  afterEach(() => vi.useRealTimers());

  it("ignores events and close callbacks from a replaced session", () => {
    const received: string[] = [];
    const closed: string[] = [];
    const sockets = createFakeSocketFactory();
    const controller = new RunController({
      createSocket: sockets.create,
      cancelRun: vi.fn().mockResolvedValue(undefined),
      onEvent: event => received.push(String(event.content ?? "")),
      onClose: handle => closed.push(handle.sessionId),
    });

    controller.start(startInput("A", "first"));
    controller.start(startInput("B", "second"));
    sockets.forSession("A").message({ type: "status", content: "old" });
    sockets.forSession("A").close();
    sockets.forSession("B").message({ type: "status", content: "new" });

    expect(received).toEqual(["new"]);
    expect(closed).toEqual([]);
  });

  it("knows and sends the run id before the first server event", () => {
    const sockets = createFakeSocketFactory();
    const controller = new RunController({
      createSocket: sockets.create,
      cancelRun: vi.fn().mockResolvedValue(undefined),
      onEvent: vi.fn(),
    });

    const handle = controller.start(startInput("A", "x"));
    const socket = sockets.forSession("A");
    socket.open();

    expect(handle.runId).toMatch(/^[0-9a-f-]{36}$/);
    expect(JSON.parse(socket.sent[0])).toMatchObject({
      type: "message",
      run_id: handle.runId,
      content: "x",
    });
  });

  it("cancels by the known run id before closing the socket", async () => {
    const order: string[] = [];
    const sockets = createFakeSocketFactory();
    const cancelRun = vi.fn(async () => { order.push("cancel"); });
    const controller = new RunController({
      createSocket: sockets.create,
      cancelRun,
      onEvent: vi.fn(),
    });
    const handle = controller.start(startInput("A"));
    const socket = sockets.forSession("A");
    const originalClose = socket.close.bind(socket);
    socket.close = () => { order.push("close"); originalClose(); };

    await controller.cancel();

    expect(cancelRun).toHaveBeenCalledWith(handle.sessionId, handle.runId);
    expect(order).toEqual(["cancel", "close"]);
  });

  it("buffers token chunks and flushes them once", () => {
    vi.useFakeTimers();
    const chunks: string[] = [];
    const sockets = createFakeSocketFactory();
    const controller = new RunController({
      createSocket: sockets.create,
      cancelRun: vi.fn().mockResolvedValue(undefined),
      onEvent: vi.fn(),
      onText: text => chunks.push(text),
    });
    controller.start(startInput("A"));

    sockets.forSession("A").message({ type: "token", content: "hel" });
    sockets.forSession("A").message({ type: "assistant_delta", content: "lo" });
    expect(chunks).toEqual([]);
    vi.advanceTimersByTime(32);

    expect(chunks).toEqual(["hello"]);
  });
});
