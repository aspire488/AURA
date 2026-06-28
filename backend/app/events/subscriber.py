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
        # Deterministic belief revision from promoted Knowledge
        from app.belief.revision import revise
        report = await revise()
        # Log revision report
        import logging
        logging.getLogger(__name__).debug("Belief revision report: %s", report)
        # Fetch the most recent active belief and update consolidated metrics
        from app.belief.store import belief_store
        from app.events.event import EventType
        from app.main import emit
        import time
        beliefs = await belief_store.list_all(limit=1)
        if beliefs:
            belief = beliefs[0]
            belief.confidence_value = 1.0  # ponytail: default confidence
            belief.opinion_value = 0.0    # ponytail: default opinion
            belief.updated_at = time.time()
            await belief_store.save(belief)
        # Directly trigger downstream processing
        await emit(EventType.GOAL_UPDATED, payload={})

# ConfidenceUpdatedSubscriber removed – unified belief model handles confidence directly

# OpinionUpdatedSubscriber removed – opinion now stored within unified belief


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
        logger.info(f"ReasoningUpdatedSubscriber START @ {__import__('datetime').datetime.utcnow().isoformat()}")
        # Create a reasoning record linking latest goal (existing behavior)
        from app.goal.store import goal_store
        from app.reasoning.manager import create as create_reasoning
        goals = await goal_store.list_all(limit=1)
        if goals:
            goal = goals[0]
            # For simplicity, no beliefs or opinions linked
            reasoning = await create_reasoning(goal.goal_id)
            # Create decision linking this reasoning (Oracle) → deterministic conclusion
            from app.oracle.manager import create as create_decision, derive_final
            decision = await create_decision(reasoning_ids=[reasoning.reasoning_id])
            await derive_final(decision.decision_id)
            # Execution stage: invoke appropriate tool based on decision.final_conclusion
            from app.runtime.decision_executor import execute_decision
            exec_result = await execute_decision(decision)
            # Emit execution event for observation pipeline
            from app.main import emit
            from app.events.event import EventType
            await emit(EventType.CODE_EXECUTED, payload={
                "decision_id": decision.decision_id,
                "result": exec_result,
                "summary": exec_result.get("summary", ""),
            })
            # ---- New: generate a reflection for this reasoning and trigger learning ----
            from app.reflection.reflection import Reflection
            from app.reflection.store import reflection_store
            from app.reflection.reflection import process_reflection
            # create reflection linking this reasoning
            reflection = Reflection(reasoning_ids=[reasoning.reasoning_id])
            await reflection_store.save(reflection)
            # emit event for possible subscribers (optional)
            from app.main import emit
            from app.events.event import EventType
            await emit(EventType.REFLECTION_CREATED, payload={"reflection_id": reflection.reflection_id})
            # directly process reflection to generate learning
            await process_reflection(reflection)
        # final stage – no further event
        pass


class ObservationBeliefSubscriber:
    """Processes OBSERVATION_INGESTED events into belief updates.

    ponytail: extracts observation from event payload, delegates to process_observation().
    """

    async def __call__(self, event: BaseEvent) -> None:
        from app.belief.revision import process_observation
        from app.observation.observation import Observation, ObservationType

        payload = event.payload
        obs_id = payload.get("observation_id")

        # If we have an observation_id, load from store; otherwise build from event
        if obs_id:
            from app.observation.store import observation_store
            obs = await observation_store.get(obs_id)
            if not obs:
                logger.debug("ObservationBeliefSubscriber: observation %s not found", obs_id)
                return
        else:
            # Build observation from event fields
            obs = Observation(
                event_id=event.event_id,
                observation_type=ObservationType(payload.get("observation_type", "user_message")),
                source=event.source,
                actor=event.actor,
                summary=payload.get("summary", ""),
                payload=payload,
                confidence=payload.get("confidence", 1.0),
            )

        report = await process_observation(obs)
        logger.debug("ObservationBeliefSubscriber report: %s", report)


class ChallengerSubscriber:
    """Handles BELIEF_UPDATED events where drift_detected is flagged.

    ponytail: extracts drift info from event payload, delegates to handle_drift_event().
    """

    async def __call__(self, event: BaseEvent) -> None:
        from app.runtime.challenger import handle_drift_event

        payload = event.payload
        belief_id = payload.get("belief_id", "")
        if not belief_id:
            return

        drift_detected = payload.get("drift_detected", False)
        observation_id = payload.get("observation_id", "")
        old_conf = payload.get("old_confidence", 0.0)
        new_conf = payload.get("new_confidence", 0.0)

        if not drift_detected:
            return

        report = await handle_drift_event(
            belief_id=belief_id,
            drift_observation_id=observation_id,
            old_confidence=old_conf,
            new_confidence=new_conf,
        )
        logger.debug("ChallengerSubscriber report: %s", report)


class GoalMonitorSubscriber:
    """Evaluates active goals on GOAL_UPDATED events.

    ponytail: delegates to evaluate_goals() which checks resolution
    and dispatches unresolved goals to n8n.
    """

    async def __call__(self, event: BaseEvent) -> None:
        from app.runtime.goal_monitor import evaluate_goals

        report = await evaluate_goals()
        logger.debug("GoalMonitorSubscriber report: %s", report)


class ProactivitySubscriber:
    """Delegates to ProactivityManager for autonomous goal/automation generation."""

    async def __call__(self, event: BaseEvent) -> None:
        from app.runtime.proactivity_manager import proactivity_manager
        await proactivity_manager.evaluate(event)

