export class SocketClient {
  private ws: WebSocket | null = null;
  private url: string;
  private onMessage: (msg: any) => void;
  private onConnect: () => void;
  private onDisconnect: () => void;

  constructor(
    sessionId: string, 
    token: string,
    callbacks: {
      onMessage: (msg: any) => void,
      onConnect: () => void,
      onDisconnect: () => void
    }
  ) {
    this.url = `ws://localhost:8000/chat/ws/${sessionId}?token=${token}`;
    this.onMessage = callbacks.onMessage;
    this.onConnect = callbacks.onConnect;
    this.onDisconnect = callbacks.onDisconnect;
  }

  connect() {
    this.ws = new WebSocket(this.url);

    this.ws.onopen = () => {
      console.log("WebSocket connected");
      this.onConnect();
    };

    this.ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        this.onMessage(data);
      } catch (err) {
        console.error("Failed to parse websocket message", err);
      }
    };

    this.ws.onclose = () => {
      console.log("WebSocket disconnected");
      this.onDisconnect();
      // Auto-reconnect after 3 seconds
      setTimeout(() => this.connect(), 3000);
    };

    this.ws.onerror = (error) => {
      console.error("WebSocket error", error);
    };
  }

  sendMessage(message: string, mode: "normal" | "plan", context?: any) {
    if (this.ws && this.ws.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify({
        content: message,
        mode: mode,
        context: context
      }));
    } else {
      console.error("Cannot send message, WebSocket not open");
    }
  }

  disconnect() {
    if (this.ws) {
      this.ws.close();
      this.ws = null;
    }
  }
}
