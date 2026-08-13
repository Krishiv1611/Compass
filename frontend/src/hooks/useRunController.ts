import { useEffect, useRef } from "react";
import { RunController, type RunControllerOptions } from "@/runtime/RunController";

export function useRunController(options: RunControllerOptions): RunController {
  const optionsRef = useRef(options);
  optionsRef.current = options;
  const controllerRef = useRef<RunController | null>(null);

  if (!controllerRef.current) {
    controllerRef.current = new RunController({
      createSocket: sessionId => optionsRef.current.createSocket(sessionId),
      cancelRun: (sessionId, runId) => optionsRef.current.cancelRun(sessionId, runId),
      onEvent: (event, handle) => optionsRef.current.onEvent(event, handle),
      onText: (content, handle) => optionsRef.current.onText?.(content, handle),
      onOpen: handle => optionsRef.current.onOpen?.(handle),
      onError: handle => optionsRef.current.onError?.(handle),
      onClose: handle => optionsRef.current.onClose?.(handle),
      flushDelayMs: options.flushDelayMs,
    });
  }

  useEffect(() => {
    const controller = controllerRef.current;
    return () => controller?.dispose();
  }, []);

  return controllerRef.current;
}
