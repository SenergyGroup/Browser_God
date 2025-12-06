# Manual Agent Command Console & Extension Bridge

This guide explains how to validate the full Browser God agent ↔ extension flow using the new WebSocket bridge and manual console.

## Prerequisites

- Python environment with dependencies installed (`pip install -r requirements.txt`).
- FastAPI agent running locally (default: `http://localhost:8000`).
- Browser extension loaded in developer mode.
- Chrome debugging permissions enabled for the extension (Manifest V3 background service worker).

## Start the Agent

1. From the repository root, run the FastAPI app:

```bash
uvicorn agent.main:app --reload --port 8000
streamlit run .\dashboard\app.py
```

2. Confirm health:

```bash
curl http://localhost:8000/healthz
```

3. Keep the server running while testing. The `/ws/extension` endpoint will accept the extension bridge connection automatically.

## Load the Extension

1. Build/prepare the extension assets (no bundling required for the provided scripts).
2. In Chrome, open **chrome://extensions**.
3. Enable **Developer mode** and choose **Load unpacked**.
4. Select the `extension/` directory from this repository.
5. In the options page, verify the **Agent WebSocket URL** points to `ws://localhost:8000/ws/extension` (update it if the agent is running elsewhere) and save.
6. Use the popup toggle to enable **Agent control** when ready to run commands.

The service worker now auto-connects to the agent with incremental backoff and streams state/command events.

## Manual Command Console

A lightweight interactive console is available at `agent/manual_console.py`.

### Launch the console

```bash
python -m agent.manual_console --agent-url http://localhost:8000
```

The console immediately attaches to the `/events` stream so you can watch bridge status, command results, and extension state updates in real time.

### Available console commands

- `state` — fetch the current extension state (queue length, processing flag, bridge status, and recent logs).
- `toggle <on|off>` — enable or disable agent control via the extension.
- `open <url>` — queue a simple `OPEN_URL` command.
- `run <TYPE> {json}` — queue any command defined in the schema with a JSON payload (including nested `actions`).
- `help`, `exit`, `quit` — usage info or exit the console.

Examples:

```bash
run OPEN_URL {
  "url": "https://www.etsy.com/search?q=lamp",
  "actions": [
    { "type": "WAIT", "payload": { "milliseconds": 2000 } },
    { "type": "SCROLL_TO_BOTTOM", "payload": {} },
    { "type": "EXTRACT_SCHEMA", "payload": {} }
  ]
}
```

## Observing Events & Diagnostics

- The event stream (`/events`) emits `commandResult` and `extensionState` updates whenever commands queue, complete, or the bridge reconnects.
- The popup shows recent log entries; the same data is emitted to the agent for external observers.
- The service worker logs bridge transitions (`connecting`, `connected`, `disconnected`) to the console for quick debugging.

## Handling Errors & Reconnects

- The WebSocket bridge automatically retries with incremental backoff up to 15 seconds between attempts.
- If the agent is unreachable, the console will print reconnect attempts while the service worker continues retrying in the background.
- Disallowed domains, rate limits, or debugger attach failures are surfaced in `commandResult` events and in the popup logs.

## Suggested Manual Test Flow

1. **Connect everything**: start the agent, load the extension, open the console, and toggle agent control on.
2. **Basic navigation**: `open https://www.etsy.com/` and watch for a completed `commandResult` event.
3. **Action chaining**: use a `run OPEN_URL {...actions...}` payload with `WAIT`, `SCROLL_TO_BOTTOM`, and `CLICK` actions to confirm DOM actions flow through.
4. **Capture**: queue a `CAPTURE_JSON_FROM_DEVTOOLS` command and confirm records arrive in the result payload; export NDJSON from the popup if desired.
5. **Resilience**: stop and restart the agent to verify the bridge reconnects and state updates resume automatically.

Following these steps validates the end-to-end agent ↔ extension ↔ browser pipeline without autonomous control.
