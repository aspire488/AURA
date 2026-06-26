from app.events.event import BaseEvent, EventType, EventMetadata
from app.events.bus import bus
from app.events.store import event_store
from app.events.registry import registry
from app.events.subscriber import ObservationSubscriber, MemorySubscriber, MetricsSubscriber


def init_events() -> None:
    """Register default subscribers and wire up the bus. Call during startup."""
    from app.events.event import EventType

    registry.register(EventType.USER_MESSAGE_RECEIVED, ObservationSubscriber())
    registry.register(EventType.ASSISTANT_RESPONSE_GENERATED, ObservationSubscriber())
    registry.register(EventType.TOOL_EXECUTION_STARTED, ObservationSubscriber())
    registry.register(EventType.TOOL_EXECUTION_COMPLETED, ObservationSubscriber())
    registry.register(EventType.TASK_CREATED, ObservationSubscriber())
    registry.register(EventType.TASK_COMPLETED, ObservationSubscriber())
    registry.register(EventType.MEMORY_STORED, MemorySubscriber())
    registry.register(EventType.MEMORY_RETRIEVED, MemorySubscriber())
    registry.register(EventType.BROWSER_ACTION, ObservationSubscriber())
    registry.register(EventType.CODE_EXECUTED, ObservationSubscriber())
    registry.register(EventType.PROVIDER_INVOKED, ObservationSubscriber())
    registry.register(EventType.PROVIDER_FAILED, ObservationSubscriber())
    registry.register(EventType.REASONING_STARTED, ObservationSubscriber())
    registry.register(EventType.REASONING_COMPLETED, ObservationSubscriber())
    registry.register(EventType.REFLECTION_CREATED, ObservationSubscriber())

    # Metrics subscriber on all events
    for et in EventType:
        registry.register(et, MetricsSubscriber())

    # Wire registry into bus
    for event_type, handler in registry.get_all():
        bus.subscribe(event_type, handler)
