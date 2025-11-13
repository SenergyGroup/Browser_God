import { DEFAULT_SETTINGS } from "../background/settings.js";

async function loadSettings() {
  const { settings } = await chrome.storage.local.get({ settings: DEFAULT_SETTINGS });
  document.getElementById("allowed-origins").value = (settings.allowedOrigins || []).join("\n");
  document.getElementById("max-commands").value = settings.maxCommandsPerMinute || DEFAULT_SETTINGS.maxCommandsPerMinute;
  document.getElementById("max-tabs").value = settings.maxConcurrentTabs || DEFAULT_SETTINGS.maxConcurrentTabs;
  document.getElementById("max-bytes").value = settings.maxResponseBodyBytes || DEFAULT_SETTINGS.maxResponseBodyBytes;
}

async function saveSettings() {
  const origins = document
    .getElementById("allowed-origins")
    .value.split(/\n+/)
    .map((line) => line.trim())
    .filter(Boolean);
  const next = {
    allowedOrigins: origins,
    maxCommandsPerMinute: Number(document.getElementById("max-commands").value) || DEFAULT_SETTINGS.maxCommandsPerMinute,
    maxConcurrentTabs: Number(document.getElementById("max-tabs").value) || DEFAULT_SETTINGS.maxConcurrentTabs,
    maxResponseBodyBytes: Number(document.getElementById("max-bytes").value) || DEFAULT_SETTINGS.maxResponseBodyBytes
  };
  const { settings } = await chrome.storage.local.get({ settings: DEFAULT_SETTINGS });
  await chrome.storage.local.set({ settings: { ...settings, ...next } });
  const status = document.getElementById("status");
  status.textContent = "Settings saved.";
  setTimeout(() => {
    status.textContent = "";
  }, 2000);
}

document.getElementById("save").addEventListener("click", saveSettings);

loadSettings();
