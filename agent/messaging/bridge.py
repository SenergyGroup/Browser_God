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
        LOGGER.info("ExtensionBridge initialized")

    async def register_extension(self, websocket: WebSocket) -> None:
        """Register a WebSocket connection originating from the extension."""
        client = getattr(websocket, "client", None)
        LOGGER.info("Accepting extension WebSocket connection", extra={"client": str(client)})
        await websocket.accept()
        async with self._lock:
            self._extension_socket = websocket
        LOGGER.info("Extension bridge connected")

        try:
            while True:
                payload = await websocket.receive_text()
                LOGGER.debug("Received raw message from extension: %s", payload)
                message = json.loads(payload)
                await self._handle_extension_message(message)
        except Exception as error:  # noqa: BLE001
            LOGGER.warning("Extension connection closed", exc_info=error)
        finally:
            LOGGER.info("Cleaning up extension connection state")
            async with self._lock:
                self._extension_socket = None
            for future in self._pending_requests.values():
                if not future.done():
                    future.set_exception(ConnectionError("Extension disconnected"))
            pending_count = len(self._pending_requests)
            self._pending_requests.clear()
            LOGGER.info("Cleared pending requests after disconnect", extra={"pendingCount": pending_count})

    async def _handle_extension_message(self, message: Dict[str, Any]) -> None:
        envelope = message.get("envelope")
        if envelope == "extension-response":
            request_id = message.get("requestId")
            LOGGER.debug("Received extension response", extra={"requestId": request_id})
            future = self._pending_requests.pop(request_id, None)
            if future and not future.done():
                future.set_result(message.get("payload"))
            else:
                LOGGER.debug("No pending future for requestId %s", request_id)
            return

        msg_type = message.get("type")

        if msg_type == "commandResult":
            LOGGER.info("Received commandResult from extension")
            await self._event_broker.publish(message)
            return

        if msg_type == "extensionState":
            LOGGER.info("Received extensionState update")
            self._latest_state = message.get("payload")
            await self._event_broker.publish(message)
            return

        LOGGER.debug("Unhandled extension message: %s", message)

    async def enqueue_command(self, command: Command) -> Dict[str, Any]:
        LOGGER.info(
            "Enqueueing command for extension",
            extra={"commandId": command.id, "commandType": str(command.type)},
        )
        request = EnqueueCommandRequest(command=command)
        response = await self._send_request(request.model_dump())
        LOGGER.info(
            "Sent command to extension",
            extra={"commandId": command.id, "commandType": str(command.type)},
        )
        return response

    async def request_state(self) -> Dict[str, Any]:
        LOGGER.info("Requesting extension state")
        response = await self._send_request({"type": "getExtensionState"})
        self._latest_state = response
        LOGGER.info("Extension state updated in bridge")
        return response

    async def toggle_agent_control(self, enabled: bool) -> Dict[str, Any]:
        LOGGER.info("Toggling agent control", extra={"enabled": enabled})
        response = await self._send_request({"type": "toggleAgentControl", "enabled": enabled})
        LOGGER.info("Agent control toggled", extra={"enabled": enabled})
        return response

    async def _send_request(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        async with self._lock:
            if self._extension_socket is None:
                LOGGER.error("Attempted to send request but extension is not connected")
                raise ConnectionError("Extension bridge is not connected")
            request_id = str(uuid.uuid4())
            future: asyncio.Future = asyncio.get_running_loop().create_future()
            self._pending_requests[request_id] = future
            envelope = {
                "envelope": "agent-message",
                "requestId": request_id,
                "payload": payload,
            }
            LOGGER.debug(
                "Sending message to extension",
                extra={"requestId": request_id, "payload": payload},
            )
            await self._extension_socket.send_text(json.dumps(envelope))

        try:
            response = await asyncio.wait_for(future, timeout=10)
        except asyncio.TimeoutError as error:
            LOGGER.error("Timed out waiting for extension response", extra={"requestId": request_id})
            raise error

        if not isinstance(response, dict):
            LOGGER.error("Extension response was not a JSON object", extra={"requestId": request_id})
            raise ValueError("Extension response must be a JSON object")

        LOGGER.debug("Received response from extension", extra={"requestId": request_id})
        return response

    def latest_state(self) -> Optional[Dict[str, Any]]:
        return self._latest_state


__all__ = ["ExtensionBridge"]
