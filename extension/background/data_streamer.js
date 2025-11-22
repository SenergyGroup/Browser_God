const DEFAULT_DATA_SOCKET_URL = "ws://localhost:8000/ws/data";
const MAX_BACKOFF_MS = 15000;
const BASE_BACKOFF_MS = 1000;
const RECONNECT_INTERVAL_MS = 2000;

function calculateBackoff(attempt) {
  const capped = Math.min(attempt, 5);
  return Math.min(MAX_BACKOFF_MS, BASE_BACKOFF_MS * capped * capped);
}

export class DataStreamer {
  constructor({ url = DEFAULT_DATA_SOCKET_URL } = {}) {
    this.url = url;
    this.socket = null;
    this.outbox = [];
    this.reconnectAttempts = 0;
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

  connect() {
    if (!this.shouldRun) {
      return;
    }

    try {
      this.socket = new WebSocket(this.url);
      this.socket.onopen = () => {
        this.reconnectAttempts = 0;
        this.flushOutbox();
      };

      this.socket.onclose = () => {
        if (this.shouldRun) {
          this.scheduleReconnect();
        }
      };

      this.socket.onerror = () => {
        this.socket?.close();
      };

      this.socket.onmessage = () => {
        // The data channel is write-mostly; no-op for responses today.
      };
    } catch (error) {
      console.warn("[DataStreamer] Failed to connect", error);
      this.scheduleReconnect();
    }
  }

  scheduleReconnect() {
    this.reconnectAttempts += 1;
    const delay = calculateBackoff(this.reconnectAttempts);
    setTimeout(() => this.connect(), Math.max(RECONNECT_INTERVAL_MS, delay));
  }

  sendRecord(record) {
    if (!this.shouldRun) {
      this.start();
    }

    try {
      const serialized = JSON.stringify(record);
      if (this.socket && this.socket.readyState === WebSocket.OPEN) {
        this.socket.send(serialized);
      } else {
        this.outbox.push(serialized);
      }
    } catch (error) {
      console.warn("[DataStreamer] Failed to serialize record", error, record);
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
}
