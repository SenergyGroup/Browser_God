export const DEFAULT_SETTINGS = {
  agentControlEnabled: false,
  allowedOrigins: ["etsy.com", "*.etsy.com"],
  maxCommandsPerMinute: 30,
  maxConcurrentTabs: 3,
  maxResponseBodyBytes: 5 * 1024 * 1024,
  agentWebSocketUrl: "ws://localhost:8000/ws/extension"
};

export const SEARCH_TASK_TEMPLATE = {
  urlTemplate: "https://www.etsy.com/search?q={searchTerm}&ref=pagination&page={pageNumber}",
  actionsPerPage: [
    { type: "WAIT", payload: {} },
    { type: "SCROLL_TO_BOTTOM", payload: {} },
    { type: "EXTRACT_SCHEMA", payload: {} }
  ]
};
