"""Async event broker that broadcasts extension events to listeners."""
from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from typing import Any, AsyncIterator, Dict, Set


class EventBroker:
    """Simple pub/sub broker backed by asyncio queues."""

    def __init__(self) -> None:
        self._queues: Set[asyncio.Queue] = set()
        self._lock = asyncio.Lock()

    async def publish(self, event: Dict[str, Any]) -> None:
        async with self._lock:
            if not self._queues:
                return
            for queue in list(self._queues):
                await queue.put(event)

    @asynccontextmanager
    async def subscriber(self) -> AsyncIterator[asyncio.Queue]:
        queue: asyncio.Queue = asyncio.Queue()
        async with self._lock:
            self._queues.add(queue)
        try:
            yield queue
        finally:
            async with self._lock:
                self._queues.discard(queue)


__all__ = ["EventBroker"]
