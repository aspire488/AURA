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
    # Execution engine metrics. ponytail: extend existing, no second system.
    plans_executed: int = 0
    steps_executed: int = 0
    failed_plans: int = 0
    failed_steps: int = 0
    total_steps_per_plan: int = 0
    total_execution_latency_ms: float = 0.0
    # Browser metrics. ponytail: extend existing, same lock.
    browser_requests: int = 0
    browser_failures: int = 0
    browser_latency_ms: float = 0.0
    # Code execution metrics. ponytail: extend existing, same lock.
    code_requests: int = 0
    code_failures: int = 0
    code_latency_ms: float = 0.0
    # Provider resilience metrics. ponytail: extend existing, same lock.
    provider_failures: int = 0
    provider_fallbacks: int = 0
    # Request metrics. ponytail: extend existing, same lock.
    active_requests: int = 0
    stream_requests: int = 0
    rate_limit_hits: int = 0
    # Event metrics. ponytail: extend existing, same lock.
    events_published: int = 0
    events_processed: int = 0
    subscriber_failures: int = 0
    total_publish_latency_ms: float = 0.0
    # Identity metrics. ponytail: extend existing, same lock.
    identities_created: int = 0
    identity_merges: int = 0
    identity_resolutions: int = 0
    relationship_updates: int = 0
    # Observation metrics. ponytail: extend existing, same lock.
    observations_created: int = 0
    observations_failed: int = 0
    total_observation_latency_ms: float = 0.0
    # Memory metrics. ponytail: extend existing, same lock.
    memories_created: int = 0
    memories_skipped: int = 0
    memory_retrievals: int = 0
    total_importance: float = 0.0
    # Knowledge metrics. ponytail: extend existing, same lock.
    knowledge_created: int = 0
    knowledge_updated: int = 0
    knowledge_queries: int = 0
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

    def record_execution(self, steps: int, latency_ms: float, success: bool) -> None:
        """Record execution engine run. ponytail: extend existing metrics."""
        with self._lock:
            self.plans_executed += 1
            self.steps_executed += steps
            self.total_steps_per_plan += steps
            self.total_execution_latency_ms += latency_ms
            if not success:
                self.failed_plans += 1

    def record_step_failed(self) -> None:
        with self._lock:
            self.failed_steps += 1

    def record_browser(self, latency_ms: float, success: bool) -> None:
        """Record browser command. ponytail: extend existing metrics."""
        with self._lock:
            self.browser_requests += 1
            self.browser_latency_ms += latency_ms
            if not success:
                self.browser_failures += 1

    def record_code(self, latency_ms: float, success: bool) -> None:
        """Record code execution. ponytail: extend existing metrics."""
        with self._lock:
            self.code_requests += 1
            self.code_latency_ms += latency_ms
            if not success:
                self.code_failures += 1

    def record_provider_failure(self) -> None:
        with self._lock:
            self.provider_failures += 1

    def record_provider_fallback(self) -> None:
        with self._lock:
            self.provider_fallbacks += 1

    def record_request_start(self) -> None:
        with self._lock:
            self.active_requests += 1

    def record_request_end(self) -> None:
        with self._lock:
            self.active_requests = max(0, self.active_requests - 1)

    def record_stream_request(self) -> None:
        with self._lock:
            self.stream_requests += 1

    def record_rate_limit_hit(self) -> None:
        with self._lock:
            self.rate_limit_hits += 1

    def record_event(self, event_type: str) -> None:
        """Record event processed. ponytail: extend existing metrics."""
        with self._lock:
            self.events_processed += 1

    def record_event_published(self, latency_ms: float) -> None:
        with self._lock:
            self.events_published += 1
            self.total_publish_latency_ms += latency_ms

    def record_subscriber_failure(self) -> None:
        with self._lock:
            self.subscriber_failures += 1

    def record_identity_created(self) -> None:
        with self._lock:
            self.identities_created += 1

    def record_identity_merge(self) -> None:
        with self._lock:
            self.identity_merges += 1

    def record_identity_resolution(self) -> None:
        with self._lock:
            self.identity_resolutions += 1

    def record_relationship_update(self) -> None:
        with self._lock:
            self.relationship_updates += 1

    def record_observation_created(self, latency_ms: float) -> None:
        with self._lock:
            self.observations_created += 1
            self.total_observation_latency_ms += latency_ms

    def record_observation_failed(self) -> None:
        with self._lock:
            self.observations_failed += 1

    def record_memory_created(self, importance: float) -> None:
        with self._lock:
            self.memories_created += 1
            self.total_importance += importance

    def record_memory_skipped(self) -> None:
        with self._lock:
            self.memories_skipped += 1

    def record_memory_retrieval(self) -> None:
        with self._lock:
            self.memory_retrievals += 1

    def record_knowledge_created(self) -> None:
        with self._lock:
            self.knowledge_created += 1

    def record_knowledge_updated(self) -> None:
        with self._lock:
            self.knowledge_updated += 1

    def record_knowledge_query(self) -> None:
        with self._lock:
            self.knowledge_queries += 1

    def snapshot(self) -> dict:
        with self._lock:
            ret_count = self.retrieval_count or 1
            reason_count = self.reasoning_count or 1
            task_count = self.task_count or 1
            plan_count = self.plans_executed or 1
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
                # Execution engine metrics
                "plans_executed": self.plans_executed,
                "steps_executed": self.steps_executed,
                "failed_plans": self.failed_plans,
                "failed_steps": self.failed_steps,
                "average_steps_per_plan": round(self.total_steps_per_plan / plan_count, 2),
                "average_execution_latency_ms": round(self.total_execution_latency_ms / plan_count, 2),
                # Browser metrics
                "browser_requests": self.browser_requests,
                "browser_failures": self.browser_failures,
                "average_browser_latency_ms": round(self.browser_latency_ms / max(self.browser_requests, 1), 2),
                # Code execution metrics
                "code_requests": self.code_requests,
                "code_failures": self.code_failures,
                "average_code_latency_ms": round(self.code_latency_ms / max(self.code_requests, 1), 2),
                # Provider resilience
                "provider_failures": self.provider_failures,
                "provider_fallbacks": self.provider_fallbacks,
                # Request metrics
                "active_requests": self.active_requests,
                "stream_requests": self.stream_requests,
                "rate_limit_hits": self.rate_limit_hits,
                # Event metrics
                "events_published": self.events_published,
                "events_processed": self.events_processed,
                "subscriber_failures": self.subscriber_failures,
                "average_publish_latency_ms": round(
                    self.total_publish_latency_ms / max(self.events_published, 1), 2
                ),
                # Identity metrics
                "identities_created": self.identities_created,
                "identity_merges": self.identity_merges,
                "identity_resolutions": self.identity_resolutions,
                "relationship_updates": self.relationship_updates,
                # Observation metrics
                "observations_created": self.observations_created,
                "observations_failed": self.observations_failed,
                "average_observation_latency_ms": round(
                    self.total_observation_latency_ms / max(self.observations_created, 1), 2
                ),
                # Memory metrics
                "memories_created": self.memories_created,
                "memories_skipped": self.memories_skipped,
                "memory_retrievals": self.memory_retrievals,
                "average_importance": round(
                    self.total_importance / max(self.memories_created, 1), 4
                ),
                # Knowledge metrics
                "knowledge_created": self.knowledge_created,
                "knowledge_updated": self.knowledge_updated,
                "knowledge_queries": self.knowledge_queries,
            }


# Global singleton — one process, one metrics store. ponytail: module-level.
metrics = RetrievalMetrics()
