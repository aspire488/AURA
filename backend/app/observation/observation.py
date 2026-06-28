from __future__ import annotations

import time
import uuid
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class ObservationType(str, Enum):
    """Canonical observation types. ponytail: one enum, flat mapping from EventType."""
    USER_MESSAGE = "user_message"
    ASSISTANT_RESPONSE = "assistant_response"
    TOOL_EXECUTION = "tool_execution"
    TASK = "task"
    MEMORY = "memory"
    BROWSER_ACTION = "browser_action"
    CODE_EXECUTION = "code_execution"
    PROVIDER = "provider"
    REASONING = "reasoning"
    REFLECTION = "reflection"
    IMPORT = "import"
    MEDIA = "media"


class Observation(BaseModel):
    """Normalized description of what happened. No reasoning, no memory, no knowledge."""
    observation_id: str = Field(default_factory=lambda: uuid.uuid4().hex[:12])
    event_id: str = ""
    identity_id: str = ""
    timestamp: float = Field(default_factory=time.time)
    observation_type: ObservationType
    source: str = ""
    actor: str = "system"
    summary: str = ""
    payload: dict[str, Any] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)
    confidence: float = 1.0
