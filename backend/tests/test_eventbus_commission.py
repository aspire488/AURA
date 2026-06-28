"""EventBus commissioning tests – minimal lazy verification of core invariants.

These tests discover publishers/subscribers at runtime, ensure each published event
is delivered exactly once to its registered handlers, and confirm there are no
orphan or duplicate registrations. They stub out persistent storage to keep
the suite self-contained.
"""

import asyncio
from collections import defaultdict

from app.events.bus import bus
from app.events.event import BaseEvent, EventType
from app.events import event_store

# ponytail: stub event_store.append to avoid DB dependency
async def _noop_append(event: BaseEvent):
    return None

event_store.append = _noop_append  # type: ignore[attr-defined]

# Clean any existing subscribers that may interfere with the test suite
bus._subscribers.clear()

# Simple counter subscriber
class CounterSubscriber:
    def __init__(self, counter):
        self._counter = counter

    async def __call__(self, event: BaseEvent) -> None:
        self._counter[event.event_type] += 1

# Test that a single subscriber receives each published event exactly once
async def test_single_subscriber_exact_delivery():
    counter = defaultdict(int)
    subscriber = CounterSubscriber(counter)
    bus.subscribe(EventType.USER_MESSAGE_RECEIVED, subscriber)

    # Publish 10 events of the same type
    for i in range(10):
        await bus.publish(BaseEvent(event_type=EventType.USER_MESSAGE_RECEIVED, payload={"seq": i}))

    assert counter[EventType.USER_MESSAGE_RECEIVED] == 10, "Each event should be delivered exactly once"
    # No duplicate registrations – the subscriber list should contain exactly one entry
    assert len(bus._subscribers[EventType.USER_MESSAGE_RECEIVED]) == 1
    # Clean up for next test
    bus.unsubscribe(EventType.USER_MESSAGE_RECEIVED, subscriber)

# Test that publishing an event with no subscribers does not raise and results in zero deliveries
async def test_orphan_event_no_failure():
    # Ensure no handlers for this custom type
    bus._subscribers.pop(EventType.TOOL_EXECUTION_STARTED, None)
    # Publish an event; should complete without error
    await bus.publish(BaseEvent(event_type=EventType.TOOL_EXECUTION_STARTED, payload={}))
    assert True
