import pytest

from app.events.subscriber import BeliefUpdatedSubscriber
from app.events.event import BaseEvent, EventType

@pytest.mark.asyncio
async def test_guard_prevents_recursive_revision(monkeypatch):
    called = False
    async def fake_revise(*args, **kwargs):
        nonlocal called
        called = True
        return {}
    monkeypatch.setattr('app.belief.revision.revise', fake_revise)
    sub = BeliefUpdatedSubscriber()
    event = BaseEvent(event_type=EventType.BELIEF_UPDATED, source="belief_revision/contradiction")
    await sub(event)
    assert not called, "revise should not be called for contradiction source"

@pytest.mark.asyncio
async def test_normal_event_calls_revise(monkeypatch):
    called = False
    async def fake_revise(*args, **kwargs):
        nonlocal called
        called = True
        return {}
    monkeypatch.setattr('app.belief.revision.revise', fake_revise)
    sub = BeliefUpdatedSubscriber()
    event = BaseEvent(event_type=EventType.BELIEF_UPDATED)
    await sub(event)
    assert called, "revise should be called for normal BELIEF_UPDATED events"
