"""SSE fan-out: one shared event_queue (in `state.py`), N subscriber queues."""

import asyncio
import logging

from backend.state import event_queue

logger = logging.getLogger("agents")


class Broadcaster:
    def __init__(self) -> None:
        self.subscribers: set[asyncio.Queue] = set()

    def subscribe(self) -> asyncio.Queue:
        q: asyncio.Queue = asyncio.Queue()
        self.subscribers.add(q)
        return q

    def unsubscribe(self, q: asyncio.Queue) -> None:
        self.subscribers.discard(q)

    async def broadcast(self, event: dict) -> None:
        for q in list(self.subscribers):
            try:
                await q.put(event)
            except Exception:
                pass


broadcaster = Broadcaster()


async def listen_and_broadcast() -> None:
    """Background task: drains the central event_queue into all subscribers."""
    while True:
        try:
            event = await event_queue.get()
            await broadcaster.broadcast(event)
        except Exception as e:
            logger.error(f"Broadcast Error: {e}")
            await asyncio.sleep(1)
