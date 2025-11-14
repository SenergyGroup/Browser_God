async function refreshState() {
  const state = await chrome.runtime.sendMessage({ type: "getExtensionState" });
  document.getElementById("agent-toggle").checked = state.settings.agentControlEnabled;
  document.getElementById("queue-length").textContent = state.queueLength;
  document.getElementById("processing").textContent = state.processing ? "yes" : "no";
  renderLogs(state.logs || []);
}

function createTestCommand() {
  const commandId = (() => {
    if (typeof crypto !== "undefined" && typeof crypto.randomUUID === "function") {
      return `popup-test-${crypto.randomUUID()}`;
    }
    return `popup-test-${Date.now()}-${Math.random().toString(16).slice(2)}`;
  })();

  return {
    id: commandId,
    type: "OPEN_URL",
    payload: {
      url: "https://www.etsy.com/search?q=notebook",
      actions: [
        { type: "WAIT", payload: { milliseconds: 1500 } },
        { type: "CAPTURE_JSON_FROM_DEVTOOLS", payload: { waitForMs: 2000 } }
      ]
    }
  };
}

function renderLogs(logs) {
  const list = document.getElementById("logs");
  list.innerHTML = "";
  logs.slice().reverse().forEach((log) => {
    const li = document.createElement("li");
    li.textContent = `${log.timestamp} • ${log.type} • ${log.status}${log.url ? ` • ${log.url}` : ""}`;
    list.appendChild(li);
  });
}

document.getElementById("agent-toggle").addEventListener("change", async (event) => {
  await chrome.runtime.sendMessage({ type: "toggleAgentControl", enabled: event.target.checked });
  refreshState();
});

document.getElementById("export").addEventListener("click", async () => {
  await chrome.runtime.sendMessage({ type: "exportData" });
});

document.getElementById("clear-storage").addEventListener("click", async () => {
  await chrome.storage.local.set({ results: {}, logs: [] });
  refreshState();
});

document.getElementById("trigger-test-command").addEventListener("click", async (event) => {
  const button = event.currentTarget;
  button.disabled = true;
  button.textContent = "Running…";

  try {
    const command = createTestCommand();
    const response = await chrome.runtime.sendMessage({ type: "enqueueCommand", command });
    if (!response?.ok) {
      console.error("Test command failed", response?.error);
    }
  } catch (error) {
    console.error("Failed to trigger test command", error);
  } finally {
    button.disabled = false;
    button.textContent = "Run test command";
    refreshState();
  }
});

chrome.runtime.onMessage.addListener((message) => {
  if (message?.type === "commandResult") {
    refreshState();
  }
});

refreshState();
