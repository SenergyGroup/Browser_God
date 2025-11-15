# Browser God Local Agent

<<<<<<< HEAD
This directory contains a FastAPI application that bridges the Browser God Chrome extension with a locally running automation agent. The service exposes HTTP endpoints for issuing commands, querying extension state, toggling agent control, and surfacing the extension messaging contract. It also hosts WebSocket endpoints that allow the extension to establish a transport bridge and for other clients to listen for `commandResult` events.
=======
This directory contains a FastAPI application that bridges the Browser God Chrome extension with a locally running automation
agent. The service exposes HTTP endpoints for issuing commands, querying extension state, and toggling agent control. It also
hosts WebSocket endpoints that allow the extension to establish a transport bridge and for other clients to listen for
`commandResult` events.
>>>>>>> main

## Project layout

```
agent/
├── README.md
<<<<<<< HEAD
├── api/
│   └── routes.py
├── documentation.py
=======
├── README_handler.py
├── api/
│   └── routes.py
>>>>>>> main
├── main.py
├── messaging/
│   ├── bridge.py
│   └── events.py
└── schemas/
    └── command.py
```

## Prerequisites

* Python 3.11+
* `pip install -r requirements.txt` (see below for suggested dependencies)

A minimal `requirements.txt` can include:

```
fastapi
uvicorn[standard]
pydantic
```

## Running the service

From the project root:

```
uvicorn agent.main:app --reload --port 8001
```

This starts the FastAPI server on `http://localhost:8001`.

### HTTP API

* `POST /run-command` – Accepts a simplified payload and forwards it to the extension as an `enqueueCommand` message.
* `GET /state` – Requests the latest extension state (`getExtensionState`).
* `POST /toggle-agent-control` – Enables or disables agent control mode in the extension.
<<<<<<< HEAD
* `GET /schema` – Returns reference documentation for the extension messaging contract derived from `docs/external-agent/ReadMe.md`.
=======
* `GET /schema` – Returns the schema parsed from `docs/external-agent/ReadMe.md`.
>>>>>>> main
* `GET /healthz` – Basic health probe.

### WebSockets

* `GET /ws/extension` – Endpoint the extension connects to. It relays messages between the agent and the service worker.
* `GET /events` – Clients can subscribe to command results and state change broadcasts.

## Transport design

<<<<<<< HEAD
The agent adopts the **WebSocket bridge** approach. A lightweight content script (not included in this ticket) should connect to `ws://localhost:8001/ws/extension` and relay messages using the following envelopes:
=======
The agent adopts the **WebSocket bridge** approach. A lightweight content script (not included in this ticket) should connect to
`ws://localhost:8001/ws/extension` and relay messages using the following envelopes:
>>>>>>> main

* Agent → Extension messages are wrapped as `{ "envelope": "agent-message", "requestId": "<uuid>", "payload": { ... } }`.
* Extension → Agent responses must reply with `{ "envelope": "extension-response", "requestId": "<uuid>", "payload": { ... } }`.
* Extension → Agent events (e.g., `commandResult`) are forwarded as raw event objects (`{ "type": "commandResult", ... }`).

This keeps the transport minimal while matching the contract defined in `docs/external-agent/ReadMe.md`.

<<<<<<< HEAD
## Schema reference

The module `documentation.py` exposes the schema data the agent relies on when constructing commands. The contents are derived from reviewing `docs/external-agent/ReadMe.md` and are intentionally static to avoid runtime parsing.

## Observability

The service logs structured events whenever commands are sent or when the extension disconnects. Downstream systems can also subscribe to `/events` to observe live traffic.
=======
## Schema ingestion

The module `README_handler.py` parses the canonical README to extract:

* `enqueueCommand` JSON example
* `commandResult` JSON example
* Supported command types

These details are cached and exposed via `GET /schema`. Other modules use this information to validate commands before sending
them to the extension.

## Observability

The service logs structured events whenever commands are sent or when the extension disconnects. Downstream systems can also
subscribe to `/events` to observe live traffic.
>>>>>>> main
