import asyncio

from agent.messaging.events import EventBroker


def test_subscriber_receives_published_events():
    async def runner():
        broker = EventBroker()
        async with broker.subscriber() as queue1, broker.subscriber() as queue2:
            await broker.publish({"type": "commandResult"})
            event1 = await asyncio.wait_for(queue1.get(), timeout=1)
            event2 = await asyncio.wait_for(queue2.get(), timeout=1)
        assert event1 == {"type": "commandResult"}
        assert event2 == {"type": "commandResult"}

    asyncio.run(runner())


def test_subscriber_cleanup():
    async def runner():
        broker = EventBroker()
        async with broker.subscriber() as queue:
            await broker.publish({"type": "noop"})
            await asyncio.wait_for(queue.get(), timeout=1)
            assert queue in broker._queues  # type: ignore[attr-defined]
        assert queue not in broker._queues  # type: ignore[attr-defined]

    asyncio.run(runner())


def test_publish_with_no_subscribers():
    async def runner():
        broker = EventBroker()
        await broker.publish({"type": "unused"})
        assert not broker._queues  # type: ignore[attr-defined]

    asyncio.run(runner())
