from __future__ import annotations

import logging

from app.events.event import BaseEvent

logger = logging.getLogger(__name__)


# ponytail: thin adapter — calls observe() which handles normalize + identity + persist.
class ObservationSubscriber:
    async def __call__(self, event: BaseEvent) -> None:
        from app.observation.observer import observe
        await observe(event)


class MetricsSubscriber:
    async def __call__(self, event: BaseEvent) -> None:
        from app.intelligence.metrics import metrics
        metrics.record_event(event.event_type.value)


# ponytail: simple pass‑through subscribers that chain events

class KnowledgeCreatedSubscriber:
    async def __call__(self, event: BaseEvent) -> None:
        logger.debug("G. KnowledgeCreatedSubscriber entered for %s", event.payload.get('knowledge_id'))
        from app.knowledge.manager import get as get_knowledge
        from app.world.manager import update_from_knowledge
        from app.main import emit
        from app.events.event import EventType
        kid = event.payload.get("knowledge_id")
        if not kid:
            return
        knowledge = await get_knowledge(kid)
        if not knowledge:
            return
        await update_from_knowledge(knowledge)
        await emit(EventType.WORLD_UPDATED, payload={"knowledge_id": kid})

class WorldUpdatedSubscriber:
    async def __call__(self, event: BaseEvent) -> None:
        from app.main import emit
        from app.events.event import EventType
        await emit(EventType.BELIEF_UPDATED, payload={})

class BeliefUpdatedSubscriber:
    async def __call__(self, event: BaseEvent) -> None:
        # Create a minimal belief on world update
        from app.belief.manager import create as create_belief
        # Simple placeholder statement
        await create_belief("World updated")
        from app.main import emit
        from app.events.event import EventType
        await emit(EventType.CONFIDENCE_UPDATED, payload={})

class ConfidenceUpdatedSubscriber:
    async def __call__(self, event: BaseEvent) -> None:
        # Create confidence for the most recent belief
        from app.belief.store import belief_store
        from app.confidence.manager import create as create_confidence
        beliefs = await belief_store.list_all(limit=1)
        if beliefs:
            belief = beliefs[0]
            await create_confidence(belief.belief_id)
        from app.main import emit
        from app.events.event import EventType
        await emit(EventType.OPINION_UPDATED, payload={})

class OpinionUpdatedSubscriber:
    async def __call__(self, event: BaseEvent) -> None:
        # Create opinion, then goal and reasoning in one go
        from app.main import emit
        from app.events.event import EventType
        from app.belief.store import belief_store
        from app.opinion.manager import create as create_opinion
        from app.goal.manager import create as create_goal
        from app.reasoning.manager import create as create_reasoning
        beliefs = await belief_store.list_all()
        belief_ids = [b.belief_id for b in beliefs]
        if not belief_ids:
            return
        opinion = await create_opinion(belief_ids)
        # create goal from this opinion
        goal = await create_goal([opinion.opinion_id])
        await emit(EventType.GOAL_UPDATED, payload={})
        # create reasoning for the goal (no beliefs/opinions attached for simplicity)
        await create_reasoning(goal.goal_id)
        # No further event emission needed (pipeline ends)


class GoalUpdatedSubscriber:
    async def __call__(self, event: BaseEvent) -> None:
        # Create a goal from all opinions
        from app.opinion.store import opinion_store
        from app.goal.manager import create as create_goal
        opinions = await opinion_store.list_all()
        logger.debug("GoalUpdatedSubscriber opinions count: %d", len(opinions))
        opinion_ids = [o.opinion_id for o in opinions]
        if opinion_ids:
            await create_goal(opinion_ids)
        from app.main import emit
        from app.events.event import EventType
        await emit(EventType.REASONING_UPDATED, payload={})

class ReasoningUpdatedSubscriber:
    async def __call__(self, event: BaseEvent) -> None:
        # Create a reasoning record linking latest goal
        from app.goal.store import goal_store
        from app.reasoning.manager import create as create_reasoning
        goals = await goal_store.list_all(limit=1)
        if goals:
            goal = goals[0]
            # For simplicity, no beliefs or opinions linked
            await create_reasoning(goal.goal_id)
        # final stage – no further event
        pass

