// @vitest-environment jsdom

import { act, cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import WebPreview from "./WebPreview";

type Listener = (...args: never[]) => void;

const runtime = vi.hoisted(() => {
  const listeners = new Map<string, Set<Listener>>();
  const unsubscribe = vi.fn();
  const serverProcess = {
    exit: Promise.resolve(1),
    kill: vi.fn(),
    output: new ReadableStream<string>({ start(controller) { controller.close(); } }),
  };
  const installProcess = {
    exit: Promise.resolve(0),
    kill: vi.fn(),
    output: new ReadableStream<string>({ start(controller) { controller.close(); } }),
  };
  const container = {
    mount: vi.fn().mockResolvedValue(undefined),
    spawn: vi.fn()
      .mockResolvedValueOnce(installProcess)
      .mockResolvedValue(serverProcess),
    on: vi.fn((event: string, listener: Listener) => {
      const values = listeners.get(event) ?? new Set<Listener>();
      values.add(listener);
      listeners.set(event, values);
      return () => { values.delete(listener); unsubscribe(); };
    }),
    teardown: vi.fn(),
  };
  return { boot: vi.fn().mockResolvedValue(container), container, installProcess, listeners, serverProcess, unsubscribe };
});

vi.mock("@webcontainer/api", () => ({ WebContainer: { boot: runtime.boot } }));

const file = (contents: string) => ({ file: { contents } });
const validFiles = {
  "package.json": file(JSON.stringify({ scripts: { dev: "vite" } })),
  "index.html": file("<main>Hello</main>"),
};

describe("WebPreview lifecycle", () => {
  beforeEach(() => {
    runtime.boot.mockClear();
    runtime.container.mount.mockClear();
    runtime.container.spawn.mockReset()
      .mockResolvedValueOnce(runtime.installProcess)
      .mockResolvedValue(runtime.serverProcess);
    runtime.container.on.mockClear();
    runtime.container.teardown.mockClear();
    runtime.serverProcess.kill.mockClear();
    runtime.unsubscribe.mockClear();
    runtime.listeners.clear();
  });

  afterEach(() => {
    cleanup();
    vi.useRealTimers();
  });

  it("explains unsupported projects without booting a container", async () => {
    render(<WebPreview visible files={{ "index.html": file("hello") }} onClose={vi.fn()} />);
    fireEvent.click(screen.getByRole("button", { name: /start preview/i }));

    expect(await screen.findByText(/package\.json/i)).toBeTruthy();
    expect(runtime.boot).not.toHaveBeenCalled();
  });

  it("rejects a package without a runnable script before spawning", async () => {
    render(<WebPreview visible files={{ "package.json": file(JSON.stringify({ scripts: { test: "vitest" } })) }} onClose={vi.fn()} />);
    fireEvent.click(screen.getByRole("button", { name: /start preview/i }));

    expect(await screen.findByText(/dev, start, or preview script/i)).toBeTruthy();
    expect(runtime.boot).not.toHaveBeenCalled();
    expect(runtime.container.spawn).not.toHaveBeenCalled();
  });

  it("reports a server process that exits before becoming ready", async () => {
    render(<WebPreview visible files={validFiles} onClose={vi.fn()} />);
    fireEvent.click(screen.getByRole("button", { name: /start preview/i }));

    expect(await screen.findByText(/exited with code 1/i)).toBeTruthy();
    expect(screen.getByText("Preview could not start")).toBeTruthy();
  });

  it("removes old listeners and terminates the previous process before retry", async () => {
    render(<WebPreview visible files={validFiles} onClose={vi.fn()} />);
    fireEvent.click(screen.getByRole("button", { name: /start preview/i }));
    const retry = await screen.findByRole("button", { name: /retry/i });

    await act(async () => { fireEvent.click(retry); });
    await waitFor(() => expect(runtime.serverProcess.kill).toHaveBeenCalled());
    expect(runtime.unsubscribe).toHaveBeenCalledTimes(2);
  });
});
