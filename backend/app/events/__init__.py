from app.events.event import BaseEvent, EventType, EventMetadata
from app.events.bus import bus
from app.events.store import event_store
from app.events.registry import registry
from app.events.subscriber import ObservationSubscriber, MetricsSubscriber, KnowledgeCreatedSubscriber, WorldUpdatedSubscriber, BeliefUpdatedSubscriber, ConfidenceUpdatedSubscriber, OpinionUpdatedSubscriber, GoalUpdatedSubscriber, ReasoningUpdatedSubscriber


def init_events() -> None:
    """Register default subscribers and wire up the bus. Call during startup.

    ponytail: ObservationSubscriber is the single event subscriber.
    It handles normalize + identity + persist. IdentitySubscriber removed.
    """
    # Observation subscriber on all event types — single subscriber
    for et in EventType:
        registry.register(et, ObservationSubscriber())

    # Metrics subscriber on all events
    for et in EventType:
        registry.register(et, MetricsSubscriber())

    # Pipeline subscribers – chain events
    registry.register(EventType.KNOWLEDGE_CREATED, KnowledgeCreatedSubscriber())
    registry.register(EventType.WORLD_UPDATED, WorldUpdatedSubscriber())
    registry.register(EventType.BELIEF_UPDATED, BeliefUpdatedSubscriber())
    registry.register(EventType.CONFIDENCE_UPDATED, ConfidenceUpdatedSubscriber())
    registry.register(EventType.OPINION_UPDATED, OpinionUpdatedSubscriber())
    registry.register(EventType.GOAL_UPDATED, GoalUpdatedSubscriber())
    registry.register(EventType.REASONING_UPDATED, ReasoningUpdatedSubscriber())

    # Wire registry into bus
    for event_type, handler in registry.get_all():
        bus.subscribe(event_type, handler)
