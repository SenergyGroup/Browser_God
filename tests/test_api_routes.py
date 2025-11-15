from __future__ import annotations

import asyncio

import pytest

from agent.api import routes
from agent.schemas.command import CommandType, RunCommandRequest, ToggleAgentControlRequest


class DummyBridge:
    def __init__(self) -> None:
        self.enqueued = []
        self.enqueue_response = {"accepted": True}
        self.enqueue_error: Exception | None = None
        self.state_response = {"status": "ready"}
        self.state_error: Exception | None = None
        self.toggle_response = {"ok": True}
        self.toggle_error: Exception | None = None

    async def enqueue_command(self, command):
        if self.enqueue_error:
            raise self.enqueue_error
        self.enqueued.append(command)
        return self.enqueue_response

    async def request_state(self):
        if self.state_error:
            raise self.state_error
        return self.state_response

    async def toggle_agent_control(self, enabled: bool):
        if self.toggle_error:
            raise self.toggle_error
        self.toggle_response = {"enabled": enabled}
        return self.toggle_response


def test_run_command_success():
    bridge = DummyBridge()
    request = RunCommandRequest(
        type=CommandType.OPEN_URL,
        payload={"url": "https://example.com"},
    )
    response = asyncio.run(routes.run_command(request, bridge))
    assert response == {"ok": True, "result": {"accepted": True}, "commandId": bridge.enqueued[0].id}
    assert bridge.enqueued[0].type == CommandType.OPEN_URL
    assert bridge.enqueued[0].payload == {"url": "https://example.com"}


def test_run_command_error():
    bridge = DummyBridge()
    bridge.enqueue_error = RuntimeError("boom")
    request = RunCommandRequest(type=CommandType.WAIT, payload={"milliseconds": 1})
    with pytest.raises(routes.HTTPException) as exc:
        asyncio.run(routes.run_command(request, bridge))
    assert exc.value.status_code == 500
    assert exc.value.detail == "boom"


def test_get_state_success():
    bridge = DummyBridge()
    bridge.state_response = {"connected": True}
    response = asyncio.run(routes.get_state(bridge))
    assert response == {"connected": True}


def test_get_state_error():
    bridge = DummyBridge()
    bridge.state_error = RuntimeError("offline")
    with pytest.raises(routes.HTTPException) as exc:
        asyncio.run(routes.get_state(bridge))
    assert exc.value.status_code == 503
    assert exc.value.detail == "offline"


def test_toggle_agent_control_success():
    bridge = DummyBridge()
    request = ToggleAgentControlRequest(enabled=True)
    response = asyncio.run(routes.toggle_agent_control(request, bridge))
    assert response == {"enabled": True}


def test_toggle_agent_control_error():
    bridge = DummyBridge()
    bridge.toggle_error = RuntimeError("not ready")
    request = ToggleAgentControlRequest(enabled=False)
    with pytest.raises(routes.HTTPException) as exc:
        asyncio.run(routes.toggle_agent_control(request, bridge))
    assert exc.value.status_code == 503
    assert exc.value.detail == "not ready"


def test_schema_endpoint_returns_copy():
    first = asyncio.run(routes.get_schema())
    second = asyncio.run(routes.get_schema())
    assert first == second
    first["enqueueCommand"]["type"] = "mutated"
    refreshed = asyncio.run(routes.get_schema())
    assert refreshed["enqueueCommand"]["type"] == "enqueueCommand"
