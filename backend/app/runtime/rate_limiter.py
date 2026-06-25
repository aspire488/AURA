"""In-memory rate limiter. ponytail: token bucket per key, no Redis, no external deps."""
from __future__ import annotations

import time
import threading
from dataclasses import dataclass, field


@dataclass
class _Bucket:
    tokens: float
    last_refill: float


class RateLimiter:
    """Per-key token bucket rate limiter. ponytail: in-memory, single-process."""

    def __init__(self, requests_per_minute: int = 60):
        self._rpm = requests_per_minute
        self._buckets: dict[str, _Bucket] = {}
        self._lock = threading.Lock()

    def allow(self, key: str) -> bool:
        now = time.monotonic()
        with self._lock:
            bucket = self._buckets.get(key)
            if bucket is None:
                self._buckets[key] = _Bucket(tokens=self._rpm - 1, last_refill=now)
                return True
            elapsed = now - bucket.last_refill
            bucket.tokens = min(self._rpm, bucket.tokens + elapsed * (self._rpm / 60.0))
            bucket.last_refill = now
            if bucket.tokens < 1:
                return False
            bucket.tokens -= 1
            return True

    def cleanup(self, max_age: float = 300.0) -> int:
        """Remove stale buckets. ponytail: called lazily, not on a timer."""
        now = time.monotonic()
        with self._lock:
            stale = [k for k, b in self._buckets.items() if now - b.last_refill > max_age]
            for k in stale:
                del self._buckets[k]
            return len(stale)


# ponytail: module-level, configurable via AURA_RATE_LIMIT_RPM env var.
_limiter: RateLimiter | None = None


def get_rate_limiter() -> RateLimiter:
    global _limiter
    if _limiter is None:
        from app.config import settings
        _limiter = RateLimiter(requests_per_minute=settings.rate_limit_rpm)
    return _limiter
