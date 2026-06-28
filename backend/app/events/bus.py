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
        """Publish an event and immediately invoke its subscribers.
        ponytail: bypass async queue for synchronous processing to ensure downstream pipeline runs before caller continues.
        """
        # Ensure DLQ replay worker is running in this process
        if not self._running:
            await self.start()
        logger.debug("C. EventBus.publish entered for %s", event.event_type.value)
        # Directly dispatch to subscribers instead of queuing
        handlers = self._subscribers.get(event.event_type, [])
        logger.debug("F. Subscriber list resolved: %d handlers", len(handlers))
        for handler in handlers:
            try:
                await handler(event)
            except Exception as exc:
                logger.exception("Subscriber %s failed for %s", getattr(handler, '__name__', str(handler)), event.event_type)
                # ponytail: record failure in DLQ for later replay
                from app.events.dlq_store import add as dlq_add
                if not getattr(event, "_replay", False):
                    dlq_add({"event_id": event.event_id, "event_type": event.event_type.value, "handler": getattr(handler, '__name__', str(handler)), "error": str(exc)})
        # Persist event after handlers have run
        try:
            from app.events.store import event_store
            await event_store.append(event)
        except Exception:
            logger.debug("Event persistence failed for %s", event.event_id)
        logger.debug("D. Event processed synchronously for %s", event.event_type.value)

    async def start(self) -> None:
        if self._running:
            return
        self._running = True
        self._task = asyncio.create_task(self._dispatch_loop())
        # start DLQ replay worker
        from app.events.dlq_replayer import replay_loop
        self._dlq_stop = asyncio.Event()
        self._dlq_task = asyncio.create_task(replay_loop(self._dlq_stop))
        logger.info("EventBus started with DLQ replay")

    async def stop(self) -> None:
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        # stop DLQ replay worker
        if hasattr(self, "_dlq_stop"):
            self._dlq_stop.set()
        if hasattr(self, "_dlq_task"):
            await self._dlq_task
        logger.info("EventBus stopped")

    async def _dispatch_loop(self) -> None:
        while self._running:
            try:
                event = await asyncio.wait_for(self._queue.get(), timeout=1.0)
                logger.debug("E. Dispatch loop dequeued event %s", event.event_type.value)
            except asyncio.TimeoutError:
                continue
            handlers = self._subscribers.get(event.event_type, [])
            logger.debug("F. Subscriber list resolved: %d handlers", len(handlers))
            for handler in handlers:
                try:
                    await handler(event)
                except Exception as exc:
                    logger.exception("Subscriber %s failed for %s", handler.__name__, event.event_type)
                    from app.events.dlq_store import add as dlq_add
                    dlq_add({"event_id": event.event_id, "handler": handler.__name__, "error": str(exc)})
            # ponytail: persist event after subscribers run, don't block on failure
            try:
                from app.events.store import event_store
                await event_store.append(event)
            except Exception:
                logger.debug("Event persistence failed for %s", event.event_id)


bus = EventBus()
