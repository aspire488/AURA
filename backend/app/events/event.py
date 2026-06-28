from __future__ import annotations

import time
import uuid
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class EventType(str, Enum):
    USER_MESSAGE_RECEIVED = "user_message_received"
    ASSISTANT_RESPONSE_GENERATED = "assistant_response_generated"
    TOOL_EXECUTION_STARTED = "tool_execution_started"
    TOOL_EXECUTION_COMPLETED = "tool_execution_completed"
    TASK_CREATED = "task_created"
    TASK_COMPLETED = "task_completed"
    MEMORY_STORED = "memory_stored"
    MEMORY_RETRIEVED = "memory_retrieved"
    BROWSER_ACTION = "browser_action"
    CODE_EXECUTED = "code_executed"
    PROVIDER_INVOKED = "provider_invoked"
    PROVIDER_FAILED = "provider_failed"
    REASONING_STARTED = "reasoning_started"
    REASONING_COMPLETED = "reasoning_completed"
    KNOWLEDGE_CREATED = "knowledge_created"
    WORLD_UPDATED = "world_updated"
    BELIEF_UPDATED = "belief_updated"
    HISTORICAL_IMPORT = "historical_import"
    # ponytail: removed dead event CONFIDENCE_UPDATED
    # ponytail: removed dead event OPINION_UPDATED
    GOAL_UPDATED = "goal_updated"
    REASONING_UPDATED = "reasoning_updated"
    REFLECTION_CREATED = "reflection_created"
    # ponytail: removed dead event OBSERVATION_INGESTED
    # ponytail: removed dead event CONSTRAINT_VIOLATION


class EventMetadata(BaseModel):
    version: str = "1.0"
    correlation_id: str = ""
    parent_event_id: str = ""


class BaseEvent(BaseModel):
    event_id: str = Field(default_factory=lambda: uuid.uuid4().hex[:12])
    event_type: EventType
    timestamp: float = Field(default_factory=time.time)
    session_id: str = ""
    conversation_id: str = ""
    actor: str = "system"
    source: str = ""
    payload: dict[str, Any] = Field(default_factory=dict)
    metadata: EventMetadata = Field(default_factory=EventMetadata)
    version: str = "1.0"
