"""HTTP and WebSocket routes exposed by the FastAPI application."""
from __future__ import annotations

import logging
from typing import Any, Dict

from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect

from ..README_handler import ReadmeSchemaParser
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


def get_readme_parser() -> ReadmeSchemaParser:
    from ..main import readme_parser

    return readme_parser


@router.post("/run-command")
async def run_command(
    request: RunCommandRequest,
    bridge: ExtensionBridge = Depends(get_bridge),
) -> Dict[str, Any]:
    try:
        command = request.to_command()
        response = await bridge.enqueue_command(command)
        return {"ok": True, "result": response, "commandId": command.id}
    except Exception as error:  # noqa: BLE001
        LOGGER.exception("Failed to run command")
        raise HTTPException(status_code=500, detail=str(error))


@router.get("/state")
async def get_state(bridge: ExtensionBridge = Depends(get_bridge)) -> Dict[str, Any]:
    try:
        state = await bridge.request_state()
        return state
    except Exception as error:  # noqa: BLE001
        LOGGER.exception("Failed to fetch extension state")
        raise HTTPException(status_code=503, detail=str(error))


@router.post("/toggle-agent-control")
async def toggle_agent_control(
    request: ToggleAgentControlRequest,
    bridge: ExtensionBridge = Depends(get_bridge),
) -> Dict[str, Any]:
    try:
        return await bridge.toggle_agent_control(request.enabled)
    except Exception as error:  # noqa: BLE001
        LOGGER.exception("Failed to toggle agent control")
        raise HTTPException(status_code=503, detail=str(error))


@router.get("/schema")
async def get_schema(readme: ReadmeSchemaParser = Depends(get_readme_parser)) -> Dict[str, Any]:
    try:
        return readme.to_dict()
    except Exception as error:  # noqa: BLE001
        LOGGER.exception("Failed to load README schema")
        raise HTTPException(status_code=500, detail=str(error))


@router.websocket("/ws/extension")
async def extension_socket(
    websocket: WebSocket,
    bridge: ExtensionBridge = Depends(get_bridge),
) -> None:
    await bridge.register_extension(websocket)


@router.websocket("/events")
async def event_stream(
    websocket: WebSocket,
    broker: EventBroker = Depends(get_event_broker),
) -> None:
    await websocket.accept()
    try:
        async with broker.subscriber() as queue:
            while True:
                event = await queue.get()
                await websocket.send_json(event)
    except WebSocketDisconnect:
        LOGGER.info("Event stream disconnected")
    except Exception:  # noqa: BLE001
        LOGGER.exception("Event stream error")
    finally:
        await websocket.close()
