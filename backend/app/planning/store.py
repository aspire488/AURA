"""PostgreSQL‑backed persistence for Plan records.

Mirrors GoalStore and DecisionStore with raw SQL. No extra dependencies.
"""

from __future__ import annotations

import json
import logging
import time
from typing import List

from sqlalchemy import text

from app.planning.plan import Plan
from app.substrate.postgres.client import get_session

logger = logging.getLogger(__name__)

CREATE_PLAN_TABLE = """
CREATE TABLE IF NOT EXISTS plans (
    plan_id VARCHAR(12) PRIMARY KEY,
    status VARCHAR(16) DEFAULT 'active',
    priority INTEGER DEFAULT 0,
    goal_ids JSONB DEFAULT '[]',
    decision_ids JSONB DEFAULT '[]',
    action_sequence JSONB DEFAULT '[]',
    created_at DOUBLE PRECISION NOT NULL,
    updated_at DOUBLE PRECISION NOT NULL,
    metadata JSONB DEFAULT '{}'
);
CREATE INDEX IF NOT EXISTS idx_plan_status ON plans(status);
"""


class PlanStore:
    """Raw‑SQL store for Plan records. ponytail: copy pattern of other stores."""

    async def initialize(self) -> None:
        try:
            async with get_session() as session:
                for stmt in CREATE_PLAN_TABLE.strip().split(";"):
                    stmt = stmt.strip()
                    if stmt:
                        await session.execute(text(stmt))
                await session.commit()
            logger.info("Plan table ready")
        except Exception:
            logger.exception("Failed to initialize plan table")

    async def save(self, plan: Plan) -> None:
        try:
            async with get_session() as session:
                await session.execute(
                    text(
                        "INSERT INTO plans (plan_id, status, priority, goal_ids, decision_ids, action_sequence, created_at, updated_at, metadata) "
                        "VALUES (:pid, :status, :prio, :goals, :decisions, :actions, :created, :updated, :meta) "
                        "ON CONFLICT (plan_id) DO UPDATE SET "
                        "status = EXCLUDED.status, priority = EXCLUDED.priority, "
                        "goal_ids = EXCLUDED.goal_ids, decision_ids = EXCLUDED.decision_ids, "
                        "action_sequence = EXCLUDED.action_sequence, updated_at = EXCLUDED.updated_at, "
                        "metadata = EXCLUDED.metadata"
                    ),
                    {
                        "pid": plan.plan_id,
                        "status": plan.status,
                        "prio": plan.priority,
                        "goals": json.dumps(plan.goal_ids),
                        "decisions": json.dumps(plan.decision_ids),
                        "actions": json.dumps(plan.action_sequence),
                        "created": plan.created_at,
                        "updated": plan.updated_at,
                        "meta": json.dumps(plan.metadata),
                    },
                )
                await session.commit()
        except Exception:
            logger.exception("Failed to save plan %s", plan.plan_id)

    async def get(self, plan_id: str) -> Plan | None:
        async with get_session() as session:
            result = await session.execute(text("SELECT * FROM plans WHERE plan_id = :pid"), {"pid": plan_id})
            row = result.mappings().first()
            return self._row_to_plan(row) if row else None

    async def list_all(self, status: str = "", limit: int = 100) -> List[Plan]:
        async with get_session() as session:
            if status:
                result = await session.execute(
                    text("SELECT * FROM plans WHERE status = :status ORDER BY created_at DESC LIMIT :limit"),
                    {"status": status, "limit": limit},
                )
            else:
                result = await session.execute(
                    text("SELECT * FROM plans ORDER BY created_at DESC LIMIT :limit"),
                    {"limit": limit},
                )
            return [self._row_to_plan(row) for row in result.mappings()]

    async def find_by_goal(self, goal_id: str) -> List[Plan]:
        async with get_session() as session:
            result = await session.execute(
                text("SELECT * FROM plans WHERE goal_ids @> :gid::jsonb"),
                {"gid": json.dumps([goal_id])},
            )
            return [self._row_to_plan(row) for row in result.mappings()]

    async def find_by_decision(self, decision_id: str) -> List[Plan]:
        async with get_session() as session:
            result = await session.execute(
                text("SELECT * FROM plans WHERE decision_ids @> :did::jsonb"),
                {"did": json.dumps([decision_id])},
            )
            return [self._row_to_plan(row) for row in result.mappings()]

    async def invalidate(self, plan_id: str) -> Plan | None:
        plan = await self.get(plan_id)
        if not plan:
            return None
        plan.status = "invalid"
        plan.updated_at = time.time()
        await self.save(plan)
        return plan

    def _row_to_plan(self, row: dict) -> Plan:
        return Plan(
            plan_id=row["plan_id"],
            status=row.get("status", "active"),
            priority=row.get("priority", 0),
            goal_ids=json.loads(row["goal_ids"]) if isinstance(row["goal_ids"], str) else (row["goal_ids"] or []),
            decision_ids=json.loads(row["decision_ids"]) if isinstance(row["decision_ids"], str) else (row["decision_ids"] or []),
            action_sequence=json.loads(row["action_sequence"]) if isinstance(row["action_sequence"], str) else (row["action_sequence"] or []),
            created_at=row["created_at"],
            updated_at=row.get("updated_at", row["created_at"]),
            metadata=json.loads(row["metadata"]) if isinstance(row["metadata"], str) else (row["metadata"] or {}),
        )


plan_store = PlanStore()
