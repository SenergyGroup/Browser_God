async function refreshState() {
  const state = await chrome.runtime.sendMessage({ type: "getExtensionState" });
  document.getElementById("agent-toggle").checked = state.settings.agentControlEnabled;
  document.getElementById("queue-length").textContent = state.queueLength;
  document.getElementById("processing").textContent = state.processing ? "yes" : "no";
  renderLogs(state.logs || []);
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

chrome.runtime.onMessage.addListener((message) => {
  if (message?.type === "commandResult") {
    refreshState();
  }
});

refreshState();
