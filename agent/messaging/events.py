"""Async event broker that broadcasts extension events to listeners."""
from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager
from typing import Any, AsyncIterator, Dict, Set

LOGGER = logging.getLogger(__name__)


class EventBroker:
    """Simple pub/sub broker backed by asyncio queues."""

    def __init__(self) -> None:
        self._queues: Set[asyncio.Queue] = set()
        self._lock = asyncio.Lock()
        LOGGER.info("EventBroker initialized")

    async def publish(self, event: Dict[str, Any]) -> None:
        async with self._lock:
            if not self._queues:
                LOGGER.debug("No subscribers, event dropped", extra={"eventType": event.get("type")})
                return
            LOGGER.debug(
                "Publishing event to subscribers",
                extra={"subscriberCount": len(self._queues), "eventType": event.get("type")},
            )
            for queue in list(self._queues):
                await queue.put(event)

    @asynccontextmanager
    async def subscriber(self) -> AsyncIterator[asyncio.Queue]:
        queue: asyncio.Queue = asyncio.Queue()
        async with self._lock:
            self._queues.add(queue)
            LOGGER.info(
                "Subscriber added to EventBroker",
                extra={"subscriberCount": len(self._queues)},
            )
        try:
            yield queue
        finally:
            async with self._lock:
                self._queues.discard(queue)
                LOGGER.info(
                    "Subscriber removed from EventBroker",
                    extra={"subscriberCount": len(self._queues)},
                )


__all__ = ["EventBroker"]
