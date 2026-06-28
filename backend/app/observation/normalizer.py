from __future__ import annotations

from app.events.event import BaseEvent, EventType
from app.observation.observation import Observation, ObservationType

# ponytail: flat dict, no class hierarchy. one mapping per event type.
_EVENT_TO_OBSERVATION: dict[EventType, ObservationType] = {
    EventType.USER_MESSAGE_RECEIVED: ObservationType.USER_MESSAGE,
    EventType.ASSISTANT_RESPONSE_GENERATED: ObservationType.ASSISTANT_RESPONSE,
    EventType.TOOL_EXECUTION_STARTED: ObservationType.TOOL_EXECUTION,
    EventType.TOOL_EXECUTION_COMPLETED: ObservationType.TOOL_EXECUTION,
    EventType.TASK_CREATED: ObservationType.TASK,
    EventType.TASK_COMPLETED: ObservationType.TASK,
    EventType.MEMORY_STORED: ObservationType.MEMORY,
    EventType.MEMORY_RETRIEVED: ObservationType.MEMORY,
    EventType.BROWSER_ACTION: ObservationType.BROWSER_ACTION,
    EventType.CODE_EXECUTED: ObservationType.CODE_EXECUTION,
    EventType.PROVIDER_INVOKED: ObservationType.PROVIDER,
    EventType.PROVIDER_FAILED: ObservationType.PROVIDER,
    EventType.REASONING_STARTED: ObservationType.REASONING,
    EventType.REASONING_COMPLETED: ObservationType.REASONING,
    EventType.REFLECTION_CREATED: ObservationType.REFLECTION,
    # ponytail: map historical import to reflection observation
    EventType.HISTORICAL_IMPORT: ObservationType.REFLECTION,
}


def normalize(event: BaseEvent, identity_id: str = "") -> Observation:
    """Transform an Event into a normalized Observation. No reasoning, no logic."""
    obs_type = _EVENT_TO_OBSERVATION.get(event.event_type, ObservationType.REFLECTION)
    return Observation(
        event_id=event.event_id,
        identity_id=identity_id,
        timestamp=event.timestamp,
        observation_type=obs_type,
        source=event.source,
        actor=event.actor,
        summary=f"{event.event_type.value} from {event.source}",
        payload=event.payload,
        metadata={
            "event_type": event.event_type.value,
            "session_id": event.session_id,
            "conversation_id": event.conversation_id,
            "version": event.version,
        },
        confidence=1.0,
    )
