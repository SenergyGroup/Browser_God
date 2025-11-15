"""HTTP and WebSocket routes exposed by the FastAPI application."""
from __future__ import annotations

import logging
from typing import Any, Dict

from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect

from ..documentation import get_schema_documentation
from ..messaging.bridge import ExtensionBridge
from ..messaging.events import EventBroker
from ..schemas.command import RunCommandRequest, ToggleAgentControlRequest

LOGGER = logging.getLogger(__name__)

router = APIRouter()


def get_bridge() -> ExtensionBridge:
    from ..main import extension_bridge  # Lazy import to avoid circular deps

    return extension_bridge


def get_event_broker() -> EventBroker:
    from ..main import event_broker

    return event_broker


@router.post("/run-command")
async def run_command(
    request: RunCommandRequest,
    bridge: ExtensionBridge = Depends(get_bridge),
) -> Dict[str, Any]:
    LOGGER.info(
        "Received /run-command",
        extra={"commandType": str(request.type), "requestId": request.id},
    )
    try:
        command = request.to_command()
        LOGGER.debug(
            "Converted RunCommandRequest to Command",
            extra={"commandId": command.id, "commandType": str(command.type)},
        )
        response = await bridge.enqueue_command(command)
        LOGGER.info(
            "Command processed successfully",
            extra={"commandId": command.id, "commandType": str(command.type)},
        )
        return {"ok": True, "result": response, "commandId": command.id}
    except Exception as error:  # noqa: BLE001
        LOGGER.exception("Failed to run command")
        raise HTTPException(status_code=500, detail=str(error))


@router.get("/state")
async def get_state(bridge: ExtensionBridge = Depends(get_bridge)) -> Dict[str, Any]:
    LOGGER.info("Received /state request")
    try:
        state = await bridge.request_state()
        LOGGER.debug("Extension state fetched")
        return state
    except Exception as error:  # noqa: BLE001
        LOGGER.exception("Failed to fetch extension state")
        raise HTTPException(status_code=503, detail=str(error))


@router.post("/toggle-agent-control")
async def toggle_agent_control(
    request: ToggleAgentControlRequest,
    bridge: ExtensionBridge = Depends(get_bridge),
) -> Dict[str, Any]:
    LOGGER.info(
        "Received /toggle-agent-control",
        extra={"enabled": request.enabled},
    )
    try:
        result = await bridge.toggle_agent_control(request.enabled)
        LOGGER.info(
            "Toggled agent control",
            extra={"enabled": request.enabled},
        )
        return result
    except Exception as error:  # noqa: BLE001
        LOGGER.exception("Failed to toggle agent control")
        raise HTTPException(status_code=503, detail=str(error))


@router.get("/schema")
async def get_schema() -> Dict[str, Any]:
    LOGGER.info("Received /schema request")
    schema = get_schema_documentation()
    LOGGER.debug("Schema documentation returned")
    return schema


@router.websocket("/ws/extension")
async def extension_socket(
    websocket: WebSocket,
    bridge: ExtensionBridge = Depends(get_bridge),
) -> None:
    LOGGER.info("Incoming WebSocket connection on /ws/extension")
    await bridge.register_extension(websocket)
    LOGGER.info("Extension WebSocket handler completed")


@router.websocket("/events")
async def event_stream(
    websocket: WebSocket,
    broker: EventBroker = Depends(get_event_broker),
) -> None:
    LOGGER.info("Incoming WebSocket connection on /events")
    await websocket.accept()
    try:
        async with broker.subscriber() as queue:
            LOGGER.info("Client subscribed to event stream")
            while True:
                event = await queue.get()
                LOGGER.debug("Sending event to client", extra={"eventType": event.get("type")})
                await websocket.send_json(event)
    except WebSocketDisconnect:
        LOGGER.info("Event stream disconnected")
    except Exception:  # noqa: BLE001
        LOGGER.exception("Event stream error")
    finally:
        await websocket.close()
        LOGGER.info("Event stream WebSocket closed")
