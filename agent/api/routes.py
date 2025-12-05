"""HTTP and WebSocket routes exposed by the FastAPI application."""
from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Dict

from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect

from ..database import get_supabase_client
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
async def get_schema() -> Dict[str, Any]:
    return get_schema_documentation()


@router.websocket("/ws/extension")
async def extension_socket(
    websocket: WebSocket,
    bridge: ExtensionBridge = Depends(get_bridge),
) -> None:
    await bridge.register_extension(websocket)


@router.websocket("/ws/data")
async def data_stream(websocket: WebSocket) -> None:
    """Stream scraped records directly into Supabase."""

    await websocket.accept()
    supabase = get_supabase_client()

    LOGGER.info("Data stream opened for ingestion")

    try:
        while True:
            message = await websocket.receive_text()
            try:
                payload = json.loads(message)
            except json.JSONDecodeError:
                LOGGER.warning("Dropping non-JSON payload from data stream: %s", message)
                continue

            image_url = None
            image_urls = payload.get("image_urls")
            if isinstance(image_urls, list) and image_urls:
                first_image = image_urls[0]
                if isinstance(first_image, str):
                    image_url = first_image

            record = {
                "id": str(uuid.uuid4()),
                "action_id": payload.get("commandId"),
                "title": payload.get("title"),
                "price_value": payload.get("price_value"),
                "image_url": image_url,
                "item_url": payload.get("url") or payload.get("item_url"),
                "rating_value": payload.get("rating_value"),
                "review_count": payload.get("rating_count"),
                "created_at": datetime.now(timezone.utc).isoformat(),
            }

            try:
                supabase.table("scraped_items").insert(record).execute()
            except Exception:  # noqa: BLE001
                LOGGER.exception("Failed to insert scraped item", extra={"record": record})
    except WebSocketDisconnect:
        LOGGER.info("Data stream disconnected")
    except Exception:  # noqa: BLE001
        LOGGER.exception("Data stream error")
    finally:
        await websocket.close()


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
