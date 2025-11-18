const MAX_BACKOFF_MS = 15000;
const BASE_BACKOFF_MS = 1000;

function calculateBackoff(attempt) {
  const capped = Math.min(attempt, 5);
  return Math.min(MAX_BACKOFF_MS, BASE_BACKOFF_MS * capped * capped);
}

export class AgentBridge {
  constructor({
    getSettings,
    handleAgentRequest,
    onStatusChange = () => {},
    getExtensionState,
  }) {
    this.getSettings = getSettings;
    this.handleAgentRequest = handleAgentRequest;
    this.onStatusChange = onStatusChange;
    this.getExtensionState = getExtensionState;
    this.socket = null;
    this.reconnectAttempts = 0;
    this.outbox = [];
    this.shouldRun = false;
  }

  start() {
    if (this.shouldRun) {
      return;
    }
    this.shouldRun = true;
    this.connect();
  }

  stop() {
    this.shouldRun = false;
    if (this.socket) {
      this.socket.close();
    }
  }

  async connect() {
    if (!this.shouldRun) {
      return;
    }

    const settings = await this.getSettings();
    const url = settings.agentWebSocketUrl || "ws://localhost:8000/ws/extension";

    try {
      this.socket = new WebSocket(url);
      this.onStatusChange("connecting");

      this.socket.onopen = async () => {
        console.log("[Agent Bridge] WebSocket connection established.");
        this.reconnectAttempts = 0;
        this.onStatusChange("connected");
        await this.sendExtensionState();
        this.flushOutbox();
      };

      this.socket.onmessage = async (event) => {
        try {
          const message = JSON.parse(event.data);
          await this.handleIncomingMessage(message);
        } catch (error) {
          console.warn("Failed to handle agent message", error);
        }
      };

      this.socket.onclose = () => {
        console.log("[Agent Bridge] WebSocket connection closed.");
        this.onStatusChange("disconnected");
        if (this.shouldRun) {
          this.scheduleReconnect();
        }
      };

      this.socket.onerror = (error) => {
        console.error("[Agent Bridge] WebSocket error occurred.");
        console.error("Agent bridge websocket error", error);
        this.socket?.close();
      };
    } catch (error) {
      console.error("Failed to connect to agent", error);
      this.scheduleReconnect();
    }
  }

  async sendExtensionState() {
    try {
      const payload = await this.getExtensionState();
      this.emit({ type: "extensionState", payload });
    } catch (error) {
      console.warn("Unable to read extension state for broadcast", error);
    }
  }

  emit(message) {
    if (!message) {
      return;
    }
    const serialized = JSON.stringify(message);
    if (this.socket && this.socket.readyState === WebSocket.OPEN) {
      this.socket.send(serialized);
    } else {
      this.outbox.push(serialized);
    }
  }

  flushOutbox() {
    if (!this.socket || this.socket.readyState !== WebSocket.OPEN) {
      return;
    }
    while (this.outbox.length) {
      const next = this.outbox.shift();
      this.socket.send(next);
    }
  }

  scheduleReconnect() {
    this.reconnectAttempts += 1;
    const delay = calculateBackoff(this.reconnectAttempts);
    console.log(
      `[Agent Bridge] Scheduling reconnect attempt ${this.reconnectAttempts} in ${delay}ms.`
    );
    setTimeout(() => this.connect(), delay);
  }

  async handleIncomingMessage(message) {
    console.log("[Agent Bridge] Received message from agent:", message);
    if (message?.envelope === "agent-message") {
      const { requestId, payload } = message;
      const response = await this.safeHandleRequest(payload);
      const envelope = { envelope: "extension-response", requestId, payload: response };
      this.emit(envelope);
      return;
    }

    console.debug("Received unhandled agent event", message);
  }

  async safeHandleRequest(payload) {
    try {
      const response = await this.handleAgentRequest(payload);
      return response;
    } catch (error) {
      console.error("Agent request failed", payload, error);
      return { ok: false, error: error?.message || "UNKNOWN_ERROR" };
    }
  }
}

