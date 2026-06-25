from __future__ import annotations

import time
import threading
from dataclasses import dataclass, field


@dataclass
class RetrievalMetrics:
    """In-process metrics. ponytail: no Prometheus, no DB, just counters."""
    retrieval_count: int = 0
    hit_count: int = 0
    total_score: float = 0.0
    total_latency_ms: float = 0.0
    store_count: int = 0
    duplicate_skip_count: int = 0
    # Reasoning metrics
    reasoning_count: int = 0
    total_provider_latency_ms: float = 0.0
    total_pipeline_latency_ms: float = 0.0
    total_prompt_tokens: int = 0
    total_completion_tokens: int = 0
    validation_failures: int = 0
    # Task metrics. ponytail: counters, same lock.
    active_tasks: int = 0
    completed_tasks: int = 0
    cancelled_tasks: int = 0
    resumed_tasks: int = 0
    total_task_latency_ms: float = 0.0
    total_tools_per_task: int = 0
    task_count: int = 0
    _lock: threading.Lock = field(default_factory=threading.Lock, repr=False)

    def record_retrieval(self, score: float, latency_ms: float, hit: bool = True) -> None:
        with self._lock:
            self.retrieval_count += 1
            if hit:
                self.hit_count += 1
                self.total_score += score
            self.total_latency_ms += latency_ms

    def record_store(self, is_duplicate: bool = False) -> None:
        with self._lock:
            self.store_count += 1
            if is_duplicate:
                self.duplicate_skip_count += 1

    def record_reasoning(
        self,
        pipeline_latency_ms: float,
        provider_latency_ms: float,
        prompt_tokens: int,
        completion_tokens: int,
        validation_valid: bool = True,
    ) -> None:
        with self._lock:
            self.reasoning_count += 1
            self.total_pipeline_latency_ms += pipeline_latency_ms
            self.total_provider_latency_ms += provider_latency_ms
            self.total_prompt_tokens += prompt_tokens
            self.total_completion_tokens += completion_tokens
            if not validation_valid:
                self.validation_failures += 1

    def record_task_created(self) -> None:
        with self._lock:
            self.active_tasks += 1

    def record_task_completed(self, latency_ms: float, tools_used: int) -> None:
        with self._lock:
            self.active_tasks = max(0, self.active_tasks - 1)
            self.completed_tasks += 1
            self.task_count += 1
            self.total_task_latency_ms += latency_ms
            self.total_tools_per_task += tools_used

    def record_task_cancelled(self) -> None:
        with self._lock:
            self.active_tasks = max(0, self.active_tasks - 1)
            self.cancelled_tasks += 1

    def record_task_resumed(self) -> None:
        with self._lock:
            self.resumed_tasks += 1

    def snapshot(self) -> dict:
        with self._lock:
            ret_count = self.retrieval_count or 1
            reason_count = self.reasoning_count or 1
            task_count = self.task_count or 1
            return {
                "retrieval_count": self.retrieval_count,
                "hit_count": self.hit_count,
                "average_score": round(self.total_score / max(self.hit_count, 1), 4),
                "average_latency_ms": round(self.total_latency_ms / ret_count, 2),
                "duplicate_rate": round(self.duplicate_skip_count / max(self.store_count, 1), 4),
                "store_count": self.store_count,
                "duplicate_skip_count": self.duplicate_skip_count,
                "reasoning_count": self.reasoning_count,
                "average_pipeline_latency_ms": round(self.total_pipeline_latency_ms / reason_count, 2),
                "average_provider_latency_ms": round(self.total_provider_latency_ms / reason_count, 2),
                "total_prompt_tokens": self.total_prompt_tokens,
                "total_completion_tokens": self.total_completion_tokens,
                "validation_failures": self.validation_failures,
                # Task metrics
                "active_tasks": self.active_tasks,
                "completed_tasks": self.completed_tasks,
                "cancelled_tasks": self.cancelled_tasks,
                "resumed_tasks": self.resumed_tasks,
                "average_task_latency_ms": round(self.total_task_latency_ms / task_count, 2),
                "average_tools_per_task": round(self.total_tools_per_task / task_count, 2),
            }


# Global singleton — one process, one metrics store. ponytail: module-level.
metrics = RetrievalMetrics()
