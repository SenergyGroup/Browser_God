export const DEFAULT_SETTINGS = {
  agentControlEnabled: false,
  allowedOrigins: ["etsy.com", "*.etsy.com"],
  maxCommandsPerMinute: 30,
  maxConcurrentTabs: 3,
  maxResponseBodyBytes: 5 * 1024 * 1024,
  agentWebSocketUrl: "ws://localhost:8000/ws/extension"
};
