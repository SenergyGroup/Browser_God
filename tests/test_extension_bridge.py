from __future__ import annotations

import asyncio
import json

import pytest

from agent.messaging.bridge import ExtensionBridge
from agent.messaging.events import EventBroker


class FakeWebSocket:
    def __init__(self) -> None:
        self.sent_messages: list[str] = []

    async def send_text(self, text: str) -> None:
        self.sent_messages.append(text)


def test_send_request_flow():
    async def runner():
        broker = EventBroker()
        bridge = ExtensionBridge(broker)
        fake_socket = FakeWebSocket()
        bridge._extension_socket = fake_socket  # type: ignore[attr-defined]

        async def run_request():
            return await bridge._send_request({"type": "getExtensionState"})

        request_task = asyncio.create_task(run_request())
        await asyncio.sleep(0)
        assert len(fake_socket.sent_messages) == 1
        envelope = json.loads(fake_socket.sent_messages[0])
        assert envelope["envelope"] == "agent-message"
        request_id = envelope["requestId"]

        response_message = {
            "envelope": "extension-response",
            "requestId": request_id,
            "payload": {"ok": True},
        }
        await bridge._handle_extension_message(response_message)
        result = await request_task
        assert result == {"ok": True}
        assert request_id not in bridge._pending_requests  # type: ignore[attr-defined]

    asyncio.run(runner())


def test_send_request_requires_connection():
    async def runner():
        bridge = ExtensionBridge(EventBroker())
        with pytest.raises(ConnectionError, match="not connected"):
            await bridge._send_request({"type": "noop"})

    asyncio.run(runner())


def test_send_request_timeout(monkeypatch):
    async def runner():
        broker = EventBroker()
        bridge = ExtensionBridge(broker)
        fake_socket = FakeWebSocket()
        bridge._extension_socket = fake_socket  # type: ignore[attr-defined]

        async def fake_wait_for(future, timeout):
            raise asyncio.TimeoutError

        monkeypatch.setattr("agent.messaging.bridge.asyncio.wait_for", fake_wait_for)

        with pytest.raises(asyncio.TimeoutError):
            await bridge._send_request({"type": "getExtensionState"})

    asyncio.run(runner())


def test_send_request_disconnect():
    async def runner():
        broker = EventBroker()
        bridge = ExtensionBridge(broker)
        fake_socket = FakeWebSocket()
        bridge._extension_socket = fake_socket  # type: ignore[attr-defined]

        request_task = asyncio.create_task(bridge._send_request({"type": "getExtensionState"}))
        await asyncio.sleep(0)
        assert fake_socket.sent_messages

        async with bridge._lock:  # type: ignore[attr-defined]
            bridge._extension_socket = None  # type: ignore[attr-defined]
        for future in bridge._pending_requests.values():  # type: ignore[attr-defined]
            if not future.done():
                future.set_exception(ConnectionError("Extension disconnected"))

        with pytest.raises(ConnectionError, match="Extension disconnected"):
            await request_task

    asyncio.run(runner())


def test_non_dict_response_raises():
    async def runner():
        broker = EventBroker()
        bridge = ExtensionBridge(broker)
        fake_socket = FakeWebSocket()
        bridge._extension_socket = fake_socket  # type: ignore[attr-defined]

        async def run_request():
            return await bridge._send_request({"type": "getExtensionState"})

        request_task = asyncio.create_task(run_request())
        await asyncio.sleep(0)
        envelope = json.loads(fake_socket.sent_messages[0])
        await bridge._handle_extension_message(
            {
                "envelope": "extension-response",
                "requestId": envelope["requestId"],
                "payload": ["not", "a", "dict"],
            }
        )

        with pytest.raises(ValueError, match="must be a JSON object"):
            await request_task

    asyncio.run(runner())


def test_command_result_event_published():
    async def runner():
        broker = EventBroker()
        bridge = ExtensionBridge(broker)

        async def get_event():
            async with broker.subscriber() as queue:
                return await asyncio.wait_for(queue.get(), timeout=1)

        consumer = asyncio.create_task(get_event())
        await asyncio.sleep(0)
        await bridge._handle_extension_message({"type": "commandResult", "payload": {"status": "ok"}})
        event = await consumer
        assert event["type"] == "commandResult"

    asyncio.run(runner())


def test_extension_state_updates_latest_state():
    async def runner():
        broker = EventBroker()
        bridge = ExtensionBridge(broker)

        async def get_event():
            async with broker.subscriber() as queue:
                return await asyncio.wait_for(queue.get(), timeout=1)

        consumer = asyncio.create_task(get_event())
        await asyncio.sleep(0)
        message = {"type": "extensionState", "payload": {"connected": True}}
        await bridge._handle_extension_message(message)
        event = await consumer
        assert bridge.latest_state() == {"connected": True}
        assert event == message

    asyncio.run(runner())


def test_unhandled_message_does_not_publish():
    async def runner():
        broker = EventBroker()
        bridge = ExtensionBridge(broker)

        async with broker.subscriber() as queue:
            await bridge._handle_extension_message({"type": "unknown", "payload": {}})
            with pytest.raises(asyncio.TimeoutError):
                await asyncio.wait_for(queue.get(), timeout=0.1)

    asyncio.run(runner())
