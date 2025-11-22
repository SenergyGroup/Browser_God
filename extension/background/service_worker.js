import { validateListingRecord, validateReviewRecord } from "../common/schemas.js";
import { transformEtsyListing, transformEtsyReviews } from "../common/transformers.js";
import { DEFAULT_SETTINGS, MAX_PAGES_PER_TERM, SEARCH_TASK_TEMPLATE } from "./settings.js";
import { AgentBridge } from "./agent_bridge.js";
import { DataStreamer } from "./data_streamer.js";

const COMMAND_TYPES = {
  OPEN_URL: "OPEN_URL",
  WAIT: "WAIT",
  SCROLL_TO_BOTTOM: "SCROLL_TO_BOTTOM",
  CLICK: "CLICK",
  CAPTURE_JSON_FROM_DEVTOOLS: "CAPTURE_JSON_FROM_DEVTOOLS",
  EXTRACT_SCHEMA: "EXTRACT_SCHEMA",
  EXECUTE_SEARCH_TASK: "EXECUTE_SEARCH_TASK"
};

const ERROR_CODES = {
  DOMAIN_NOT_ALLOWED: "DOMAIN_NOT_ALLOWED",
  ATTACH_FAILED: "ATTACH_FAILED",
  PARSING_ERROR: "PARSING_ERROR",
  INVALID_COMMAND: "INVALID_COMMAND",
  RATE_LIMITED: "RATE_LIMITED"
};

const TAB_SLOT_POLL_INTERVAL_MS = 500;

const commandQueue = [];
let processing = false;
const commandLogs = [];
const activeTabSessions = new Map();
const recentCommandTimestamps = [];
let bridgeStatus = "disconnected";
let agentBridge;
const dataStreamer = new DataStreamer();

chrome.runtime.onInstalled.addListener(async () => {
  await chrome.storage.local.set({
    settings: DEFAULT_SETTINGS,
    logs: [],
    commands: {},
    results: {}
  });
});

function initializeAgentBridge() {
  agentBridge = new AgentBridge({
    getSettings,
    getExtensionState,
    handleAgentRequest: handleControlMessage,
    onStatusChange: (status) => {
      bridgeStatus = status;
      broadcastExtensionState();
    }
  });

  agentBridge.start();
}

chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  const messageType = message?.type;
  console.log("Service worker received message", messageType, message);

  (async () => {
    const response = await handleControlMessage(message);
    sendResponse(response);
  })().catch((error) => {
    console.error("Failed to handle runtime message", messageType, error);
    sendResponse({ ok: false, error: error?.message || "INTERNAL_ERROR" });
  });

  return true;
});

async function handleIncomingCommand(command) {
  if (!command?.id || !command?.type) {
    throw new Error("Command must include id and type");
  }

  const settings = await getSettings();
  if (!settings.agentControlEnabled) {
    throw new Error("Agent control is disabled");
  }

  enforceRateLimit(settings);

  if (!isCommandDomainAllowed(command, settings)) {
    await logCommand(command, "rejected", ERROR_CODES.DOMAIN_NOT_ALLOWED);
    return { status: "rejected", error: ERROR_CODES.DOMAIN_NOT_ALLOWED };
  }

  commandQueue.push(command);
  processQueue();
  await broadcastExtensionState();
  return { status: "queued" };
}

async function handleControlMessage(message) {
  switch (message?.type) {
    case "enqueueCommand": {
      const result = await handleIncomingCommand(message.command);
      return { ok: true, result };
    }
    case "getExtensionState": {
      return await getExtensionState();
    }
    case "toggleAgentControl": {
      return await toggleAgentControl(message.enabled);
    }
    case "exportData": {
      try {
        return await exportCapturedData();
      } catch (error) {
        return { ok: false, error: error.message };
      }
    }
    default: {
      console.warn("Unknown message type", message?.type);
      return { ok: false, error: "UNKNOWN_MESSAGE_TYPE" };
    }
  }
}

async function getSettings() {
  const { settings } = await chrome.storage.local.get({ settings: DEFAULT_SETTINGS });
  return { ...DEFAULT_SETTINGS, ...settings };
}

async function getExtensionState() {
  const settings = await getSettings();
  const { logs } = await chrome.storage.local.get({ logs: [] });
  return {
    settings,
    queueLength: commandQueue.length,
    processing,
    logs: logs.slice(-20),
    bridgeStatus
  };
}

async function broadcastExtensionState() {
  if (!agentBridge) {
    return;
  }

  try {
    const state = await getExtensionState();
    agentBridge.emit({ type: "extensionState", payload: state });
  } catch (error) {
    console.warn("Failed to broadcast extension state", error);
  }
}

async function toggleAgentControl(enabled) {
  const settings = await getSettings();
  const next = { ...settings, agentControlEnabled: Boolean(enabled) };
  await chrome.storage.local.set({ settings: next });
  await broadcastExtensionState();
  return { ok: true, settings: next };
}

function enforceRateLimit(settings) {
  const now = Date.now();
  const cutoff = now - 60000;
  while (recentCommandTimestamps.length && recentCommandTimestamps[0] < cutoff) {
    recentCommandTimestamps.shift();
  }
  if (recentCommandTimestamps.length >= settings.maxCommandsPerMinute) {
    throw new Error(ERROR_CODES.RATE_LIMITED);
  }
  recentCommandTimestamps.push(now);
}

function isCommandDomainAllowed(command, settings) {
  if (!command?.payload?.url) {
    return true;
  }
  try {
    const url = new URL(command.payload.url);
    return settings.allowedOrigins.some((origin) => matchesOrigin(url, origin));
  } catch (error) {
    return false;
  }
}

function matchesOrigin(url, originPattern) {
  if (!originPattern) {
    return false;
  }
  const normalizedPattern = originPattern.replace(/^https?:\/\//i, "").replace(/\/$/, "").toLowerCase();
  const hostname = url.hostname.toLowerCase();
  if (normalizedPattern.startsWith("*.")) {
    const domain = normalizedPattern.slice(2);
    return hostname === domain || hostname.endsWith(`.${domain}`);
  }
  return hostname === normalizedPattern || hostname.endsWith(`.${normalizedPattern}`);
}

async function processQueue() {
  if (processing) {
    return;
  }
  processing = true;
  console.log(`[Queue] Starting to process ${commandQueue.length} commands.`);
  await broadcastExtensionState();
  while (commandQueue.length) {
    const command = commandQueue.shift();
    console.log(`[Queue] Dequeued command: ${command.type} (${command.id})`);
    const result = await executeCommand(command);
    await storeResult(command, result);
    await logCommand(command, result.status, result.errorCode);
    notifyResult(command, result);
    await broadcastExtensionState();
  }
  processing = false;
  console.log("[Queue] Finished processing. Queue is now empty.");
  await broadcastExtensionState();
}

async function executeCommand(command) {
  const settings = await getSettings();
  try {
    console.log(`[Executor] Executing command: ${command.type} (${command.id})`);
    switch (command.type) {
      case COMMAND_TYPES.OPEN_URL:
        return await handleOpenUrl(command, settings);
      case COMMAND_TYPES.WAIT:
        return await handleWait(command);
      case COMMAND_TYPES.SCROLL_TO_BOTTOM:
        return await handleDomAction(command, "SCROLL_TO_BOTTOM");
      case COMMAND_TYPES.CLICK:
        return await handleDomAction(command, "CLICK");
      case COMMAND_TYPES.CAPTURE_JSON_FROM_DEVTOOLS:
        return await handleCaptureJson(command, settings);
      case COMMAND_TYPES.EXTRACT_SCHEMA:
        return await handleExtractSchema(command);
      case COMMAND_TYPES.EXECUTE_SEARCH_TASK:
        return await handleExecuteSearchTask(command, settings);
      default:
        return { status: "failed", errorCode: ERROR_CODES.INVALID_COMMAND };
    }
  } catch (error) {
    console.error("Command execution failed", command, error);
    return { status: "failed", errorCode: error.message || "UNKNOWN_ERROR" };
  }
}

async function handleOpenUrl(command, settings) {
  const url = command?.payload?.url;
  if (!url) {
    return { status: "failed", errorCode: ERROR_CODES.INVALID_COMMAND };
  }

  await waitForTabSlot(settings.maxConcurrentTabs);

  const tab = await chrome.tabs.create({ url, active: false });
  const tabId = tab.id;

  const loadResult = await waitForTabLoad(tabId);
  if (!loadResult) {
    return { status: "failed", errorCode: "NAVIGATION_TIMEOUT" };
  }

  const attachResult = await attachDebugger(tabId, command.id);
  if (!attachResult.ok) {
    await chrome.tabs.remove(tabId);
    return { status: "failed", errorCode: ERROR_CODES.ATTACH_FAILED };
  }

  activeTabSessions.set(tabId, {
    commandId: command.id,
    capturedBodies: [],
    transformers: getTransformersForHost(new URL(url).hostname),
    settings
  });

  // IMPORTANT: accept actions from either payload.actions or command.actions
  const actions =
    Array.isArray(command.payload?.actions)
      ? command.payload.actions
      : Array.isArray(command.actions)
        ? command.actions
        : [];

  // Collect records from nested actions (especially CAPTURE_JSON_FROM_DEVTOOLS)
  const collectedRecords = [];

  if (actions.length > 0) {
    for (const [index, action] of actions.entries()) {
      const actionCommand = {
        id: `${command.id}:${index}:${action.type}`,
        type: action.type,
        payload: { ...action.payload, tabId }
      };

      // This will call executeCommand, then storeResult/log/notify/broadcast
      const actionResult = await executeActionCommand(actionCommand);

      if (Array.isArray(actionResult.records)) {
        collectedRecords.push(...actionResult.records);
      }

      if (actionResult.status !== "completed") {
        console.warn("Action failed", action, actionResult);
      }
    }
  }

  if (collectedRecords.length > 0) {
    return { status: "completed", tabId, records: collectedRecords };
  }

  return { status: "completed", tabId };
}

async function handleExecuteSearchTask(command, settings) {
  const searchTerms = Array.isArray(command?.payload?.searchTerms)
    ? command.payload.searchTerms.filter((term) => typeof term === "string" && term.trim().length > 0)
    : [];

  if (!searchTerms.length) {
    return { status: "failed", errorCode: ERROR_CODES.INVALID_COMMAND };
  }

  const maxPagesPerTerm = MAX_PAGES_PER_TERM;

  console.log(
    `[Search Task ${command.id}] Starting task with ${searchTerms.length} terms.`
  );

  for (const [index, term] of searchTerms.entries()) {
    let currentPage = 1;
    let keepGoing = true;
    let terminationReason = "";
    let lastDetectedPage = null;

    console.log(
      `[Search Task ${command.id}] Starting term ${index + 1}/${searchTerms.length}: "${term}"`
    );

    while (keepGoing && currentPage <= maxPagesPerTerm) {
      let tabId;
      let result = null;
      console.log(
        `[Search Task ${command.id}]  - Attempting to scrape page ${currentPage} for "${term}"`
      );
      const randomDelay = Math.floor(Math.random() * (3000 - 1500 + 1)) + 1500;
      const actions = (SEARCH_TASK_TEMPLATE.actionsPerPage || []).map((action) => {
        const payload = { ...(action.payload || {}) };
        if (action.type === COMMAND_TYPES.WAIT) {
          payload.milliseconds = randomDelay;
        }
        return { type: action.type, payload };
      });

      const url = SEARCH_TASK_TEMPLATE.urlTemplate
        .replace("{searchTerm}", encodeURIComponent(term))
        .replace("{pageNumber}", currentPage);

      const pageCommand = {
        id: `${command.id}:${term}:${currentPage}`,
        type: COMMAND_TYPES.OPEN_URL,
        payload: {
          url,
          actions
        }
      };

      try {
        result = await executeActionCommand(pageCommand);
        tabId = result?.tabId;
        lastDetectedPage = tabId ? await detectActivePageNumber(tabId) : null;
        console.log(
          `[Search Task ${command.id}]  - Detected active page on tab ${tabId}: ${lastDetectedPage}`
        );
      } catch (error) {
        console.error("[Search Task] Page execution failed", error);
        keepGoing = false;
        terminationReason = `[Search Task ${command.id}]  - Encountered an error: ${error.message}`;
      } finally {
        await cleanupTab(tabId);
      }

      if (result?.status !== "completed") {
        keepGoing = false;
        terminationReason = terminationReason || `[Search Task ${command.id}]  - A sub-command failed. Concluding search for "${term}".`;
      }

      if (lastDetectedPage && lastDetectedPage < currentPage) {
        keepGoing = false;
        terminationReason = `[Search Task ${command.id}]  - Detected page reset (${lastDetectedPage} < ${currentPage}). Concluding search for "${term}".`;
      }

      if (keepGoing) {
        currentPage += 1;
      }
    }

    if (!terminationReason && currentPage > maxPagesPerTerm) {
      terminationReason = `[Search Task ${command.id}]  - Reached max page limit (${maxPagesPerTerm}). Concluding search for "${term}".`;
    }

    if (terminationReason) {
      console.log(terminationReason);
    }
  }

  console.log(
    `[Search Task ${command.id}] All terms processed. Initiating final data export.`
  );
  await exportCapturedData();
  return { status: "completed" };
}



async function waitForTabLoad(tabId) {
  return new Promise((resolve) => {
    const timeout = setTimeout(() => {
      chrome.tabs.onUpdated.removeListener(listener);
      resolve(false);
    }, 30000);

    const listener = (updatedTabId, changeInfo) => {
      if (updatedTabId === tabId && changeInfo.status === "complete") {
        clearTimeout(timeout);
        chrome.tabs.onUpdated.removeListener(listener);
        resolve(true);
      }
    };
    chrome.tabs.onUpdated.addListener(listener);
  });
}

async function attachDebugger(tabId, commandId) {
  try {
    await chrome.debugger.attach({ tabId }, "1.3");
  } catch (error) {
    console.error("Failed to attach debugger", error);
    return { ok: false };
  }
  await chrome.debugger.sendCommand({ tabId }, "Network.enable", {});
  await chrome.debugger.sendCommand({ tabId }, "Page.enable", {});
  chrome.debugger.onEvent.addListener(onDebuggerEvent);
  return { ok: true };
}

function getTransformersForHost(hostname) {
  if (hostname.endsWith("etsy.com")) {
    return {
      listings: transformEtsyListing,
      reviews: transformEtsyReviews
    };
  }
  return {};
}

async function handleWait(command) {
  const ms = command?.payload?.milliseconds ?? 1000;
  await new Promise((resolve) => setTimeout(resolve, ms));
  return { status: "completed" };
}

async function detectActivePageNumber(tabId) {
  try {
    const response = await chrome.tabs.sendMessage(tabId, { type: "GET_ACTIVE_PAGE" });
    if (response?.ok && typeof response.data?.activePage === "number") {
      return response.data.activePage;
    }
  } catch (error) {
    console.warn("Failed to detect active page", error);
  }
  return null;
}

async function waitForTabSlot(maxConcurrentTabs) {
  while (activeTabSessions.size >= maxConcurrentTabs) {
    await new Promise((resolve) => setTimeout(resolve, TAB_SLOT_POLL_INTERVAL_MS));
  }
}

async function cleanupTab(tabId) {
  if (!tabId) {
    return;
  }
  if (activeTabSessions.has(tabId)) {
    await chrome.debugger.detach({ tabId }).catch((error) =>
      console.warn("Failed to detach debugger", error)
    );
    activeTabSessions.delete(tabId);
  }
  await chrome.tabs.remove(tabId).catch((error) =>
    console.warn("Failed to close tab", error)
  );
}

async function executeActionCommand(command) {
  const actionResult = await executeCommand(command);
  await storeResult(command, actionResult);
  await logCommand(command, actionResult.status, actionResult.errorCode);
  notifyResult(command, actionResult);
  await broadcastExtensionState();
  return actionResult;
}

async function handleDomAction(command, actionType) {
  const tabId = command?.payload?.tabId ?? command?.payload?.targetTabId;
  if (!tabId) {
    return { status: "failed", errorCode: ERROR_CODES.INVALID_COMMAND };
  }

  const payload = { type: actionType, payload: command.payload };
  try {
    const response = await chrome.tabs.sendMessage(tabId, payload);
    return response?.ok ? { status: "completed", data: response.data } : { status: "failed", errorCode: response?.error || "CONTENT_SCRIPT_ERROR" };
  } catch (error) {
    console.error("DOM action failed", error);
    return { status: "failed", errorCode: error.message };
  }
}

async function handleCaptureJson(command, settings) {
  const tabId = command?.payload?.tabId;
  if (!tabId || !activeTabSessions.has(tabId)) {
    return { status: "failed", errorCode: ERROR_CODES.INVALID_COMMAND };
  }

  const session = activeTabSessions.get(tabId);

  // Set capture mode, but DO NOT wipe the bodies we already collected
  const captureType =
    command.payload?.captureType || session.captureMode || "listings";
  session.captureMode = captureType;

  // IMPORTANT: remove this line so we keep responses from navigation + scroll
  // session.capturedBodies = [];

  const waitMs = command.payload?.waitForMs ?? 5000;
  await new Promise((resolve) => setTimeout(resolve, waitMs));

  // Optional debug, can help sanity-check:
  console.log(
    "handleCaptureJson: capturedBodies length",
    session.capturedBodies.length
  );

  const parsedRecords = [];
  for (const body of session.capturedBodies) {
    if (body.raw.length > settings.maxResponseBodyBytes) {
      continue;
    }

    try {
      const json = JSON.parse(body.raw);

      // TEMP: store raw captures instead of strict Etsy listing/review objects
      parsedRecords.push({
        source: "raw",
        url: body.url,
        captureType: session.captureMode || "listings",
        json
      });
    } catch (error) {
      console.warn("Failed to parse response", error);
    }
  }


  await chrome.debugger.detach({ tabId }).catch((error) =>
    console.warn("Failed to detach", error)
  );
  activeTabSessions.delete(tabId);

  if (command.payload?.closeTab !== false) {
    await chrome.tabs.remove(tabId).catch((error) =>
      console.warn("Failed to close tab", error)
    );
  }

  return { status: "completed", records: parsedRecords };
}


function applyTransformers(session, json, url) {
  const results = [];
  if (session.captureMode === "listings" && session.transformers.listings) {
    const transformed = session.transformers.listings(json, url);
    if (Array.isArray(transformed)) {
      results.push(...transformed);
    } else if (transformed) {
      results.push(transformed);
    }
  }
  if (session.captureMode === "reviews" && session.transformers.reviews) {
    const transformed = session.transformers.reviews(json, url);
    if (Array.isArray(transformed)) {
      results.push(...transformed);
    } else if (transformed) {
      results.push(transformed);
    }
  }
  return results;
}

async function handleExtractSchema(command) {
  const tabId = command?.payload?.tabId;
  if (!tabId) {
    return { status: "failed", errorCode: ERROR_CODES.INVALID_COMMAND };
  }
  try {
    const response = await chrome.tabs.sendMessage(tabId, { type: "EXTRACT_SCHEMA", payload: command.payload });
    if (!response?.ok) {
      return { status: "failed", errorCode: response?.error || "EXTRACTION_FAILED" };
    }

    const listings = Array.isArray(response.data?.listings) ? response.data.listings : [];
    const schemas = Array.isArray(response.data?.schemas) ? response.data.schemas : [];
    const validatedListings = [];
    const rejectedListings = [];

    listings.forEach((item) => {
      const isValid = validateListingRecord(item);
      if (!isValid) {
        rejectedListings.push(item);
        console.warn("Invalid listing record rejected", item);
      } else {
        validatedListings.push(item);
      }
    });

    validatedListings.forEach((record) => {
      dataStreamer.sendRecord({ commandId: command.id, tabId, ...record });
    });

    return {
      status: "completed",
      itemsStreamed: validatedListings.length,
      totalListingsFound: listings.length,
      rejectedCount: rejectedListings.length,
      schemaCount: schemas.length
    };
  } catch (error) {
    console.error("Schema extraction failed", error);
    return { status: "failed", errorCode: error.message };
  }
}

function onDebuggerEvent(source, method, params) {
  if (!source.tabId || !activeTabSessions.has(source.tabId)) {
    return;
  }
  if (method === "Network.responseReceived") {
    handleResponseReceived(source.tabId, params);
  }
}

async function handleResponseReceived(tabId, params) {
  const session = activeTabSessions.get(tabId);
  if (!session) {
    return;
  }
  const { response, requestId } = params;
  if (!response || !response.mimeType?.includes("json")) {
    return;
  }
  const url = response.url || "";
  if (!isUrlRelevant(url)) {
    return;
  }
  try {
    const { body, base64Encoded } = await chrome.debugger.sendCommand(
      { tabId },
      "Network.getResponseBody",
      { requestId }
    );
    const raw = base64Encoded ? atob(body) : body;
    session.capturedBodies.push({ url, raw });

    // DEBUG: how many JSON responses have we collected so far?
    console.log(
      "handleResponseReceived capturedBodies length",
      tabId,
      session.capturedBodies.length,
      url
    );
  } catch (error) {
    console.warn("Failed to read response body", error);
  }
}


function isUrlRelevant(url) {
  return /etsy\.com/.test(url);
}

function summarizeResult(command, result) {
  const summary = {
    status: result?.status || "unknown",
    errorCode: result?.errorCode || null,
    commandType: command?.type
  };

  ["itemsStreamed", "totalListingsFound", "rejectedCount", "schemaCount"].forEach((key) => {
    if (result && Object.prototype.hasOwnProperty.call(result, key)) {
      summary[key] = result[key];
    }
  });

  return summary;
}

async function storeResult(command, result) {
  const { results } = await chrome.storage.local.get({ results: {} });
  results[command.id] = summarizeResult(command, result);
  await chrome.storage.local.set({ results });
}

async function logCommand(command, status, errorCode) {
  const logEntry = {
    id: command.id,
    type: command.type,
    status,
    errorCode: errorCode || null,
    timestamp: new Date().toISOString(),
    url: command.payload?.url || command.payload?.tabId || null
  };
  commandLogs.push(logEntry);
  if (commandLogs.length > 100) {
    commandLogs.shift();
  }
  const { logs } = await chrome.storage.local.get({ logs: [] });
  logs.push(logEntry);
  if (logs.length > 200) {
    logs.splice(0, logs.length - 200);
  }
  await chrome.storage.local.set({ logs });
}

function notifyResult(command, result) {
  chrome.runtime.sendMessage({ type: "commandResult", commandId: command.id, result }).catch(() => {});
  if (agentBridge) {
    agentBridge.emit({ type: "commandResult", commandId: command.id, result });
  }
}

async function exportCapturedData() {
  return {
    ok: true,
    message: "Data is streamed to the agent in real time; no local export is necessary."
  };
}

chrome.runtime.onSuspend.addListener(() => {
  for (const tabId of activeTabSessions.keys()) {
    chrome.debugger.detach({ tabId }).catch(() => {});
  }
  activeTabSessions.clear();
});

dataStreamer.start();
initializeAgentBridge();
