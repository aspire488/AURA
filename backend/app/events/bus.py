from __future__ import annotations

import asyncio
import logging
from collections import defaultdict
from typing import Any, Callable, Coroutine

from app.events.event import BaseEvent, EventType

logger = logging.getLogger(__name__)

Subscriber = Callable[[BaseEvent], Coroutine[Any, Any, None]]


class EventBus:
    """In-process async event bus. ponytail: asyncio queues, no external deps."""

    def __init__(self):
        self._subscribers: dict[EventType, list[Subscriber]] = defaultdict(list)
        self._queue: asyncio.Queue[BaseEvent] = asyncio.Queue()
        self._running = False
        self._task: asyncio.Task | None = None

    def subscribe(self, event_type: EventType, handler: Subscriber) -> None:
        self._subscribers[event_type].append(handler)

    def unsubscribe(self, event_type: EventType, handler: Subscriber) -> None:
        handlers = self._subscribers.get(event_type, [])
        if handler in handlers:
            handlers.remove(handler)

    async def publish(self, event: BaseEvent) -> None:
        await self._queue.put(event)

    async def start(self) -> None:
        if self._running:
            return
        self._running = True
        self._task = asyncio.create_task(self._dispatch_loop())
        logger.info("EventBus started")

    async def stop(self) -> None:
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        logger.info("EventBus stopped")

    async def _dispatch_loop(self) -> None:
        while self._running:
            try:
                event = await asyncio.wait_for(self._queue.get(), timeout=1.0)
            except asyncio.TimeoutError:
                continue
            handlers = self._subscribers.get(event.event_type, [])
            for handler in handlers:
                try:
                    await handler(event)
                except Exception:
                    logger.exception("Subscriber %s failed for %s", handler.__name__, event.event_type)


bus = EventBus()
