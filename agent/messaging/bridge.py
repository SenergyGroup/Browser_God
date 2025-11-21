"""Bidirectional bridge between the FastAPI agent and the extension."""
from __future__ import annotations

import asyncio
import json
import logging
import uuid
from typing import Any, Dict, Optional

from fastapi import WebSocket

from ..schemas.command import Command, EnqueueCommandRequest
from .events import EventBroker

LOGGER = logging.getLogger(__name__)


class ExtensionBridge:
    """Maintains a persistent connection with the Browser God extension."""

    def __init__(self, event_broker: EventBroker) -> None:
        self._event_broker = event_broker
        self._extension_socket: Optional[WebSocket] = None
        self._pending_requests: Dict[str, asyncio.Future] = {}
        self._lock = asyncio.Lock()
        self._latest_state: Optional[Dict[str, Any]] = None

    async def register_extension(self, websocket: WebSocket) -> None:
        """Register a WebSocket connection originating from the extension."""
        await websocket.accept()
        async with self._lock:
            self._extension_socket = websocket
        LOGGER.info("Extension bridge connected")

        try:
            while True:
                payload = await websocket.receive_text()
                message = json.loads(payload)
                await self._handle_extension_message(message)
        except Exception as error:  # noqa: BLE001
            LOGGER.warning("Extension connection closed", exc_info=error)
        finally:
            async with self._lock:
                self._extension_socket = None
            for future in self._pending_requests.values():
                if not future.done():
                    future.set_exception(ConnectionError("Extension disconnected"))
            self._pending_requests.clear()
            LOGGER.info("[Agent Bridge] Extension connection terminated.")

    async def _handle_extension_message(self, message: Dict[str, Any]) -> None:
        LOGGER.info(
            "[Agent Bridge] Received message from extension",
            extra={
                "envelope": message.get("envelope") or message.get("type"),
                "requestId": message.get("requestId"),
            },
        )
        envelope = message.get("envelope")
        if envelope == "extension-response":
            request_id = message.get("requestId")
            future = self._pending_requests.pop(request_id, None)
            if future and not future.done():
                future.set_result(message.get("payload"))
            return

        if message.get("type") == "commandResult":
            await self._event_broker.publish(message)
            return

        if message.get("type") == "extensionState":
            self._latest_state = message.get("payload")
            await self._event_broker.publish(message)
            return

        LOGGER.debug("Unhandled extension message: %s", message)

    async def enqueue_command(self, command: Command) -> Dict[str, Any]:
        request = EnqueueCommandRequest(command=command)
        payload = request.model_dump(mode="json")
        response = await self._send_request(payload)
        LOGGER.info("Sent command %s", command.id, extra={"commandType": str(command.type)})
        return response

    async def request_state(self) -> Dict[str, Any]:
        response = await self._send_request({"type": "getExtensionState"})
        self._latest_state = response
        return response

    async def toggle_agent_control(self, enabled: bool) -> Dict[str, Any]:
        response = await self._send_request({"type": "toggleAgentControl", "enabled": enabled})
        return response

    async def _send_request(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        async with self._lock:
            if self._extension_socket is None:
                raise ConnectionError("Extension bridge is not connected")
            request_id = str(uuid.uuid4())
            future: asyncio.Future = asyncio.get_running_loop().create_future()
            self._pending_requests[request_id] = future
            envelope = {
                "envelope": "agent-message",
                "requestId": request_id,
                "payload": payload,
            }
            await self._extension_socket.send_text(json.dumps(envelope))
        LOGGER.info(
            "[Agent Bridge] Sending message to extension",
            extra={
                "requestId": request_id,
                "payload": payload,
                "type": payload.get("type"),
            },
        )
        response = await asyncio.wait_for(future, timeout=10)
        if not isinstance(response, dict):
            raise ValueError("Extension response must be a JSON object")
        return response

    def latest_state(self) -> Optional[Dict[str, Any]]:
        return self._latest_state


__all__ = ["ExtensionBridge"]
