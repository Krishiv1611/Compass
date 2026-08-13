export type FakeSocketEvent = { data: string };

export class FakeSocket {
  static readonly CONNECTING = 0;
  static readonly OPEN = 1;
  static readonly CLOSED = 3;

  readonly sent: string[] = [];
  readyState = FakeSocket.CONNECTING;
  onopen: (() => void) | null = null;
  onmessage: ((event: FakeSocketEvent) => void) | null = null;
  onerror: (() => void) | null = null;
  onclose: (() => void) | null = null;
  readonly sessionId: string;

  constructor(sessionId: string) {
    this.sessionId = sessionId;
  }

  open() {
    this.readyState = FakeSocket.OPEN;
    this.onopen?.();
  }

  message(value: unknown) {
    this.onmessage?.({ data: JSON.stringify(value) });
  }

  error() {
    this.onerror?.();
  }

  close() {
    this.readyState = FakeSocket.CLOSED;
    this.onclose?.();
  }

  send(value: string) {
    this.sent.push(value);
  }
}

export function createFakeSocketFactory() {
  const sockets = new Map<string, FakeSocket[]>();

  return {
    create(sessionId: string) {
      const socket = new FakeSocket(sessionId);
      const existing = sockets.get(sessionId) ?? [];
      existing.push(socket);
      sockets.set(sessionId, existing);
      return socket;
    },
    forSession(sessionId: string) {
      const created = sockets.get(sessionId);
      if (!created?.length) throw new Error(`No socket created for session ${sessionId}`);
      return created[created.length - 1];
    },
  };
}
