import asyncio

from agent.api import routes
from agent.messaging.events import EventBroker


class FakeWebSocket:
    def __init__(self, disconnect_after: int) -> None:
        self.accepted = False
        self.sent = []
        self.closed = False
        self.disconnect_after = disconnect_after

    async def accept(self) -> None:
        self.accepted = True

    async def send_json(self, data):
        self.sent.append(data)
        if len(self.sent) >= self.disconnect_after:
            raise routes.WebSocketDisconnect()

    async def close(self) -> None:
        self.closed = True


def test_event_stream_sends_events():
    async def runner():
        broker = EventBroker()
        websocket = FakeWebSocket(disconnect_after=2)

        stream_task = asyncio.create_task(routes.event_stream(websocket, broker))
        await asyncio.sleep(0)
        await broker.publish({"type": "event", "index": 1})
        await broker.publish({"type": "event", "index": 2})

        await stream_task
        assert websocket.accepted is True
        assert websocket.closed is True
        assert websocket.sent == [
            {"type": "event", "index": 1},
            {"type": "event", "index": 2},
        ]

    asyncio.run(runner())


def test_event_stream_handles_disconnect():
    async def runner():
        broker = EventBroker()
        websocket = FakeWebSocket(disconnect_after=1)

        stream_task = asyncio.create_task(routes.event_stream(websocket, broker))
        await asyncio.sleep(0)
        await broker.publish({"type": "event", "index": 1})
        await stream_task
        assert websocket.closed is True

    asyncio.run(runner())
