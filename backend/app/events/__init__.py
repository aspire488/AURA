from app.events.event import BaseEvent, EventType, EventMetadata
from app.events.bus import bus
from app.events.store import event_store
from app.events.registry import registry
from app.events.subscriber import (
    ObservationSubscriber,
    MetricsSubscriber,
    KnowledgeCreatedSubscriber,
    WorldUpdatedSubscriber,
    BeliefUpdatedSubscriber,
    GoalUpdatedSubscriber,
    ReasoningUpdatedSubscriber,
    ObservationBeliefSubscriber,
    ChallengerSubscriber,
    GoalMonitorSubscriber,
    ProactivitySubscriber,
)



def init_events() -> None:
    # lazy import: strategic intelligence subscriber
    from app.strategic_intelligence.subscriber import StrategicIntelligenceSubscriber
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
    # Confidence/Opinion subscribers removed – unified belief handles these stages
    registry.register(EventType.GOAL_UPDATED, GoalUpdatedSubscriber())
    registry.register(EventType.REASONING_UPDATED, ReasoningUpdatedSubscriber())

    # Observation -> belief calibration (Subsystems 10 & 11)
    # ponytail: removed dead registration for OBSERVATION_INGESTED

    # Challenger: drift/contradiction resolution (Subsystem 15)
    registry.register(EventType.BELIEF_UPDATED, ChallengerSubscriber())

    # Goal monitor: evaluate and dispatch active goals (Subsystem 13)
    registry.register(EventType.GOAL_UPDATED, GoalMonitorSubscriber())

    # Proactivity: autonomous goal/automation generation (Subsystem 21)
    # ponytail: removed dead registration for OBSERVATION_INGESTED (Proactivity)
    registry.register(EventType.BELIEF_UPDATED, ProactivitySubscriber())
    # ponytail: removed dead registration for CONSTRAINT_VIOLATION
    registry.register(EventType.GOAL_UPDATED, ProactivitySubscriber())
    registry.register(EventType.CODE_EXECUTED, ProactivitySubscriber())
    # Strategic Intelligence – deterministic insights
    registry.register(EventType.CODE_EXECUTED, StrategicIntelligenceSubscriber())
    registry.register(EventType.REFLECTION_CREATED, StrategicIntelligenceSubscriber())
    registry.register(EventType.GOAL_UPDATED, StrategicIntelligenceSubscriber())
    # ponytail: removed dead registration for OBSERVATION_INGESTED (StrategicIntelligence)
    registry.register(EventType.KNOWLEDGE_CREATED, StrategicIntelligenceSubscriber())

    # Wire registry into bus
    for event_type, handler in registry.get_all():
        bus.subscribe(event_type, handler)
