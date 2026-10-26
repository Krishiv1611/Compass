import { useCallback, useEffect, useRef, useState } from "react";
import type { WebContainer as WebContainerInstance, WebContainerProcess } from "@webcontainer/api";

export type WebContainerStatus = "idle" | "booting" | "ready" | "error";

export interface WebContainerCommandResult {
  exitCode: number;
  output: string;
}

export interface UseWebContainerReturn {
  status: WebContainerStatus;
  instance: WebContainerInstance | null;
  error: Error | null;
  isSupported: boolean;
  boot: () => Promise<WebContainerInstance | null>;
  teardown: () => Promise<void>;
  runCommand: (command: string, args?: string[]) => Promise<WebContainerCommandResult>;
}

let sharedContainer: WebContainerInstance | null = null;
let sharedBootPromise: Promise<WebContainerInstance> | null = null;

export function useWebContainer(): UseWebContainerReturn {
  const [status, setStatus] = useState<WebContainerStatus>("idle");
  const [error, setError] = useState<Error | null>(null);
  const containerRef = useRef<WebContainerInstance | null>(sharedContainer);

  const isSupported = typeof window !== "undefined" && Boolean(window.crossOriginIsolated);

  const boot = useCallback(async (): Promise<WebContainerInstance | null> => {
    if (sharedContainer) {
      containerRef.current = sharedContainer;
      setStatus("ready");
      return sharedContainer;
    }

    setStatus("booting");
    setError(null);

    try {
      if (!sharedBootPromise) {
        sharedBootPromise = import("@webcontainer/api").then(({ WebContainer }) =>
          WebContainer.boot()
        );
      }
      const instance = await sharedBootPromise;
      sharedContainer = instance;
      containerRef.current = instance;
      setStatus("ready");
      return instance;
    } catch (err) {
      sharedBootPromise = null;
      const errorObj = err instanceof Error ? err : new Error(String(err));
      setError(errorObj);
      setStatus("error");
      return null;
    }
  }, []);

  const teardown = useCallback(async (): Promise<void> => {
    if (sharedContainer) {
      try {
        await sharedContainer.teardown();
      } catch {
        // ignore teardown errors
      }
      sharedContainer = null;
      sharedBootPromise = null;
      containerRef.current = null;
    }
    setStatus("idle");
    setError(null);
  }, []);

  const runCommand = useCallback(
    async (command: string, args: string[] = []): Promise<WebContainerCommandResult> => {
      const container = containerRef.current || (await boot());
      if (!container) {
        throw new Error("WebContainer is not available");
      }

      const process: WebContainerProcess = await container.spawn(command, args);
      let output = "";

      process.output.pipeTo(
        new WritableStream({
          write(data) {
            output += data;
          },
        })
      );

      const exitCode = await process.exit;
      return { exitCode, output };
    },
    [boot]
  );

  useEffect(() => {
    if (sharedContainer) {
      containerRef.current = sharedContainer;
      setStatus("ready");
    }
  }, []);

  return {
    status,
    instance: containerRef.current,
    error,
    isSupported,
    boot,
    teardown,
    runCommand,
  };
}
