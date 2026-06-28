"""Integration lifecycle management.

Defines the finite‑state machine for each provider and validates state
transitions.  The manager (in manager.py) uses this to track provider
state.
"""

from __future__ import annotations

from enum import Enum
from typing import Set, Tuple


class IntegrationState(str, Enum):
    UNCONFIGURED = "UNCONFIGURED"
    CONFIGURED = "CONFIGURED"
    CONNECTING = "CONNECTING"
    CONNECTED = "CONNECTED"
    HEALTHY = "HEALTHY"
    ACTIVE = "ACTIVE"
    DEGRADED = "DEGRADED"
    DISCONNECTED = "DISCONNECTED"
    EXPIRED = "EXPIRED"
    REVOKED = "REVOKED"
    FAILED = "FAILED"

# Allowed transitions as (from, to) pairs
_ALLOWED_TRANSITIONS: Set[Tuple[IntegrationState, IntegrationState]] = {
    (IntegrationState.UNCONFIGURED, IntegrationState.CONFIGURED),
    (IntegrationState.CONFIGURED, IntegrationState.CONNECTING),
    (IntegrationState.CONNECTING, IntegrationState.CONNECTED),
    (IntegrationState.CONNECTED, IntegrationState.DEGRADED),
    (IntegrationState.CONNECTED, IntegrationState.HEALTHY),
    (IntegrationState.CONNECTED, IntegrationState.DISCONNECTED),
    (IntegrationState.DEGRADED, IntegrationState.CONNECTED),
    (IntegrationState.DEGRADED, IntegrationState.DISCONNECTED),
    (IntegrationState.HEALTHY, IntegrationState.ACTIVE),
    (IntegrationState.DISCONNECTED, IntegrationState.CONNECTING),
    (IntegrationState.DISCONNECTED, IntegrationState.FAILED),
    (IntegrationState.CONNECTED, IntegrationState.EXPIRED),
    (IntegrationState.EXPIRED, IntegrationState.CONNECTING),
    (IntegrationState.CONNECTED, IntegrationState.REVOKED),
    (IntegrationState.REVOKED, IntegrationState.CONNECTING),
    (IntegrationState.CONNECTING, IntegrationState.FAILED),
    (IntegrationState.CONFIGURED, IntegrationState.FAILED),
    (IntegrationState.FAILED, IntegrationState.CONFIGURED),
}


def validate_transition(current: IntegrationState, target: IntegrationState) -> bool:
    """Return True if moving from *current* to *target* is a valid transition.
    """
    return (current, target) in _ALLOWED_TRANSITIONS
