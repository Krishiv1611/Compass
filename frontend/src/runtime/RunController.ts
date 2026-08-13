import type { ChatMode } from "@/types/chat";
import type { ResumePayload } from "@/types/protocol";
import type { RunEvent } from "@/types/run";

export interface RunSocket {
  readonly readyState: number;
  onopen: ((event?: unknown) => void) | null;
  onmessage: ((event: { data: string }) => void) | null;
  onerror: ((event?: unknown) => void) | null;
  onclose: ((event?: unknown) => void) | null;
  send(value: string): void;
  close(): void;
}

export interface RunHandle {
  sessionId: string;
  runId: string;
  generation: number;
}

export interface StartRunInput {
  sessionId: string;
  content: string;
  mode: ChatMode;
  contextFiles: string[];
  activeSkill?: string | null;
}

export interface RunControllerOptions {
  createSocket(sessionId: string): RunSocket;
  cancelRun(sessionId: string, runId: string): Promise<unknown>;
  onEvent(event: RunEvent, handle: RunHandle): void;
  onText?(content: string, handle: RunHandle): void;
  onOpen?(handle: RunHandle): void;
  onError?(handle: RunHandle): void;
  onClose?(handle: RunHandle): void;
  flushDelayMs?: number;
}

export class RunController {
  private generation = 0;
  private active: { handle: RunHandle; socket: RunSocket } | null = null;
  private tokenBuffer = "";
  private tokenTimer: ReturnType<typeof setTimeout> | null = null;
  private readonly options: RunControllerOptions;

  constructor(options: RunControllerOptions) {
    this.options = options;
  }

  start(input: StartRunInput): RunHandle {
    const generation = ++this.generation;
    this.clearTokenBuffer();
    this.active?.socket.close();

    const handle: RunHandle = {
      sessionId: input.sessionId,
      runId: crypto.randomUUID(),
      generation,
    };
    const socket = this.options.createSocket(input.sessionId);
    this.active = { handle, socket };

    socket.onopen = () => {
      if (!this.isCurrent(handle)) return;
      socket.send(JSON.stringify({
        type: "message",
        run_id: handle.runId,
        content: input.content,
        mode: input.mode,
        context_files: input.contextFiles,
        ...(input.activeSkill ? { active_skill: input.activeSkill } : {}),
      }));
      this.options.onOpen?.(handle);
    };
    socket.onmessage = event => {
      if (!this.isCurrent(handle)) return;
      let parsed: RunEvent;
      try {
        parsed = JSON.parse(event.data) as RunEvent;
      } catch {
        return;
      }
      if (parsed.type === "token" || parsed.type === "assistant_delta") {
        this.bufferText(String(parsed.content ?? ""), handle);
        return;
      }
      const terminal = parsed.type === "done" || parsed.type === "error";
      if (terminal) this.flushText(handle);
      this.options.onEvent(parsed, handle);
      if (terminal && this.isCurrent(handle)) socket.close();
    };
    socket.onerror = () => {
      if (this.isCurrent(handle)) this.options.onError?.(handle);
    };
    socket.onclose = () => {
      if (!this.isCurrent(handle)) return;
      this.flushText(handle);
      this.active = null;
      this.options.onClose?.(handle);
    };

    return handle;
  }

  resume(payload: ResumePayload): boolean {
    const current = this.active;
    if (!current || current.socket.readyState !== 1) return false;
    current.socket.send(JSON.stringify({
      type: "resume",
      run_id: current.handle.runId,
      action: payload.action,
      feedback: payload.feedback,
    }));
    return true;
  }

  async cancel(): Promise<void> {
    const current = this.active;
    if (!current) return;
    try {
      await this.options.cancelRun(current.handle.sessionId, current.handle.runId);
    } finally {
      if (this.isCurrent(current.handle)) {
        this.flushText(current.handle);
        current.socket.close();
      }
    }
  }

  dispose(): void {
    ++this.generation;
    this.clearTokenBuffer();
    const current = this.active;
    this.active = null;
    current?.socket.close();
  }

  get handle(): RunHandle | null {
    return this.active?.handle ?? null;
  }

  get socket(): RunSocket | null {
    return this.active?.socket ?? null;
  }

  private isCurrent(handle: RunHandle): boolean {
    return this.active?.handle === handle && this.generation === handle.generation;
  }

  private bufferText(content: string, handle: RunHandle): void {
    this.tokenBuffer += content;
    if (this.tokenTimer) return;
    this.tokenTimer = setTimeout(
      () => this.flushText(handle),
      this.options.flushDelayMs ?? 32,
    );
  }

  private flushText(handle: RunHandle): void {
    if (this.tokenTimer) clearTimeout(this.tokenTimer);
    this.tokenTimer = null;
    if (!this.isCurrent(handle)) {
      this.tokenBuffer = "";
      return;
    }
    const content = this.tokenBuffer;
    this.tokenBuffer = "";
    if (content) this.options.onText?.(content, handle);
  }

  private clearTokenBuffer(): void {
    if (this.tokenTimer) clearTimeout(this.tokenTimer);
    this.tokenTimer = null;
    this.tokenBuffer = "";
  }
}
