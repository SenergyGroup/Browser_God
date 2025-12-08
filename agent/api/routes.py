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
    # Initialize Supabase client
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

            # 1. Clean the Command ID
            # The extension sends "UUID:Step:Action". We only want the UUID.
            raw_id = payload.get("commandId")
            clean_action_id = raw_id.split(":")[0] if raw_id else None

            if not clean_action_id:
                continue

            # ==========================================================
            # NEW: BRANCHING LOGIC
            # ==========================================================
            record_type = payload.get("recordType", "LISTING") # Default to LISTING if missing

            # --- BRANCH A: METADATA (Total Results Count) ---
            if record_type == "SEARCH_METADATA":
                total_count = payload.get("total_results_count")
                if total_count is not None:
                    try:
                        LOGGER.info(f"📉 Updating Metadata: Action {clean_action_id} has {total_count} results")
                        supabase.table("search_actions").update({
                            "total_results_count": total_count,
                            # Optional: Set status to PROCESSING to indicate we found data
                            "status": "PROCESSING"
                        }).eq("id", clean_action_id).execute()
                    except Exception: # noqa: BLE001
                        LOGGER.exception(f"Failed to update metadata for action {clean_action_id}")
                continue # Skip the rest of the loop for metadata

            # --- BRANCH B: LISTING ITEMS (Your Existing Logic) ---
            # Check source only for listings
            if payload.get("source") != "etsy":
                continue

            # 2. Extract first image safely
            image_url = None
            image_urls = payload.get("image_urls")
            if isinstance(image_urls, list) and image_urls:
                first_image = image_urls[0]
                if isinstance(first_image, str):
                    image_url = first_image

            # 3. Extract Nested Seller Data
            seller_data = payload.get("seller") or {}

            # 4. Map JSON fields to Database Columns
            record = {
                "id": str(uuid.uuid4()),
                "action_id": clean_action_id,
                
                # Metadata
                "page_number": payload.get("page_number"),
                "search_query": payload.get("search_query"),
                "logging_key": payload.get("logging_key"),
                "appears_event_data": payload.get("appears_event_data"),
                
                # Identity
                "listing_id": payload.get("listing_id"),
                "title": payload.get("title"),
                "description": payload.get("description"),
                "item_url": payload.get("url"),
                
                # Images: Store BOTH the single one and the array
                "image_url": image_url,                  
                "image_urls": payload.get("image_urls"), 
                "image_alt_texts": payload.get("image_alt_texts"),
                
                # Pricing
                "price_value": payload.get("price_value"),
                "price_currency": payload.get("price_currency"),
                "price_text": payload.get("price_text"),          
                "currency_symbol": payload.get("currency_symbol"),
                "original_price_value": payload.get("original_price_value"),
                "original_price_text": payload.get("original_price_text"), 
                "discount_percent": payload.get("discount_percent"),
                "is_on_sale": payload.get("is_on_sale"),
                
                # Social / Stats
                "rating_value": payload.get("rating_value"),
                "review_count": payload.get("rating_count"), 
                "favorites": payload.get("favorites"),
                "position": payload.get("position"),
                
                # Arrays / Metadata
                "tags": payload.get("tags") or [],
                "badges": payload.get("badges") or [],
                "category": payload.get("category"),
                
                # Seller
                "seller_id": seller_data.get("id"),
                "seller_name": seller_data.get("name"),

                # Timestamp
                "created_at": datetime.now(timezone.utc).isoformat(),
            }

            try:
                supabase.table("scraped_items").insert(record).execute()
                # Debug logging - reduce noise in production
                # LOGGER.info(f"Inserted item {record['listing_id']} for action {clean_action_id}")
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