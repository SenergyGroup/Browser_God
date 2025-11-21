import { BlackHoleRenderer } from "./blackhole_renderer.js";

// Initialize the Black Hole
// Ensure 'deepfield.png' exists in the popup folder!
const renderer = new BlackHoleRenderer("blackhole", "deepfield.png");
renderer.init();

async function refreshState() {
  const state = await chrome.runtime.sendMessage({ type: "getExtensionState" });
  
  document.getElementById("agent-toggle").checked = state.settings.agentControlEnabled;
  document.getElementById("queue-length").textContent = state.queueLength;
  
  const procEl = document.getElementById("processing");
  if (state.processing) {
    procEl.textContent = "CONSUMING";
    procEl.style.color = "#ff8c00"; // Orange
    procEl.style.textShadow = "0 0 8px #ff8c00";
  } else {
    procEl.textContent = "DORMANT";
    procEl.style.color = "#8b949e"; // Dim
    procEl.style.textShadow = "none";
  }
  
  renderLogs(state.logs || []);
}

function createTestCommand() {
  const commandId = `probe-${Date.now().toString(36)}`;
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
  
  if (logs.length === 0) {
    const li = document.createElement("li");
    li.textContent = ">> NO SIGNAL DETECTED";
    li.style.color = "#444";
    li.style.textAlign = "center";
    list.appendChild(li);
    return;
  }

  logs.slice().reverse().forEach((log) => {
    const li = document.createElement("li");
    const time = new Date(log.timestamp).toLocaleTimeString([], { hour12: false });
    
    // Color code based on status
    let color = "#8b949e";
    if (log.status === "completed") color = "#ffd700"; // Gold
    if (log.status === "failed") color = "#ff4444"; // Red
    
    li.style.color = color;
    li.innerHTML = `<span style="opacity:0.5">[${time}]</span> ${log.type} :: ${log.status.toUpperCase()}`;
    
    list.appendChild(li);
  });
}

// --- Event Listeners ---

document.getElementById("open-settings").addEventListener("click", () => {
  if (chrome.runtime.openOptionsPage) {
    chrome.runtime.openOptionsPage();
  } else {
    window.open(chrome.runtime.getURL('options/options.html'));
  }
});

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
  const originalText = button.innerText;
  button.disabled = true;
  button.innerText = "LAUNCHING...";
  button.style.borderColor = "#ffd700";

  try {
    const command = createTestCommand();
    await chrome.runtime.sendMessage({ type: "enqueueCommand", command });
  } catch (error) {
    console.error("Probe launch failed", error);
  } finally {
    setTimeout(() => {
      button.disabled = false;
      button.innerText = originalText;
      button.style.borderColor = "";
      refreshState();
    }, 800);
  }
});

chrome.runtime.onMessage.addListener((message) => {
  if (message?.type === "commandResult" || message?.type === "extensionState") {
    refreshState();
  }
});

refreshState();