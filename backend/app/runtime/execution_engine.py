from __future__ import annotations

import time
import logging
from dataclasses import dataclass, field
from typing import Any

from app.runtime.tool_registry import registry

logger = logging.getLogger(__name__)


@dataclass
class ExecutionStep:
    """A single step in an execution plan."""
    index: int
    query: str
    tool_name: str | None = None
    tool_args: dict = field(default_factory=dict)
    output: str = ""
    status: str = "pending"  # pending | running | completed | failed
    error: str = ""
    latency_ms: float = 0.0

    def to_dict(self) -> dict:
        return {
            "index": self.index,
            "query": self.query,
            "tool_name": self.tool_name,
            "tool_args": self.tool_args,
            "output": self.output,
            "status": self.status,
            "error": self.error,
            "latency_ms": self.latency_ms,
        }

    @classmethod
    def from_dict(cls, d: dict) -> ExecutionStep:
        return cls(
            index=int(d.get("index", 0)),
            query=d.get("query", ""),
            tool_name=d.get("tool_name"),
            tool_args=d.get("tool_args", {}),
            output=d.get("output", ""),
            status=d.get("status", "pending"),
            error=d.get("error", ""),
            latency_ms=float(d.get("latency_ms", 0)),
        )


@dataclass
class ExecutionPlan:
    """Ordered list of steps to execute."""
    query: str
    steps: list[ExecutionStep] = field(default_factory=list)
    created_at: float = 0.0

    def to_dict(self) -> dict:
        return {
            "query": self.query,
            "steps": [s.to_dict() for s in self.steps],
            "created_at": self.created_at,
        }

    @classmethod
    def from_dict(cls, d: dict) -> ExecutionPlan:
        return cls(
            query=d.get("query", ""),
            steps=[ExecutionStep.from_dict(s) for s in d.get("steps", [])],
            created_at=float(d.get("created_at", 0)),
        )


@dataclass
class ExecutionResult:
    """Final result of executing a plan."""
    answer: str
    steps: list[ExecutionStep]
    trace: list[dict]  # step-by-step execution trace
    success: bool
    latency_ms: float
    tool_outputs: dict[str, str]  # tool_name -> output for context passing


class ExecutionEngine:
    """Sequential step executor with context passing.

    ponytail: loop over steps, execute tools, collect outputs.
    No retries, no queues, no async workers.
    """

    async def execute(
        self,
        plan: ExecutionPlan,
        start_from: int = 0,
        llm_callback: Any = None,
    ) -> ExecutionResult:
        """Execute plan steps sequentially starting from start_from.

        Args:
            plan: The execution plan.
            start_from: Step index to resume from (skip completed steps).
            llm_callback: async callable(query, context) -> str for LLM steps.
        """
        start = time.perf_counter()
        trace: list[dict] = []
        tool_outputs: dict[str, str] = {}
        last_output = ""

        for step in plan.steps:
            if step.index < start_from:
                # Already completed on a previous run — collect its output for context
                if step.output:
                    tool_outputs[step.query] = step.output
                    last_output = step.output
                continue

            step.status = "running"
            step_start = time.perf_counter()

            try:
                if step.tool_name:
                    # Tool step — skip if output already exists (dedup)
                    if step.query in tool_outputs and tool_outputs[step.query]:
                        step.output = tool_outputs[step.query]
                        step.status = "completed"
                    else:
                        result = await registry.execute(step.tool_name, **step.tool_args)
                        step.output = str(result)
                        tool_outputs[step.query] = step.output
                elif llm_callback:
                    # LLM step — pass accumulated tool outputs as context
                    context_text = self._build_step_context(tool_outputs, last_output)
                    step.output = await llm_callback(step.query, context_text)
                    tool_outputs[step.query] = step.output
                else:
                    step.output = f"[No handler for step: {step.query}]"
                    step.status = "failed"
                    step.error = "no_handler"

                last_output = step.output
                step.status = "completed"

            except Exception as e:
                logger.warning("Step %d failed: %s", step.index, e)
                step.status = "failed"
                step.error = str(e)
                step.output = f"[Error: {e}]"
                # Fatal: stop immediately
                break

            step.latency_ms = round((time.perf_counter() - step_start) * 1000, 2)
            trace.append(step.to_dict())

        total_ms = round((time.perf_counter() - start) * 1000, 2)
        success = all(s.status == "completed" for s in plan.steps)
        final_answer = last_output or "[No output]"

        return ExecutionResult(
            answer=final_answer,
            steps=plan.steps,
            trace=trace,
            success=success,
            latency_ms=total_ms,
            tool_outputs=tool_outputs,
        )

    def _build_step_context(self, tool_outputs: dict[str, str], last_output: str) -> str:
        """Build context string from previous tool outputs for LLM steps.

        ponytail: join previous outputs, no dedup beyond what the caller provides.
        """
        parts = []
        for query, output in tool_outputs.items():
            if output and output != last_output:
                parts.append(f"Previous result ({query}):\n{output}")
        if last_output and parts:
            parts.append(f"Most recent result:\n{last_output}")
        elif last_output:
            parts.append(f"Previous result:\n{last_output}")
        return "\n\n".join(parts)


# ponytail: module-level, no state.
engine = ExecutionEngine()
