"""
Minimal in-process rate limiting for sensitive, low-volume endpoints.

Deliberately not backed by Redis: FitnessOS is a single application service and
§39 of the migration brief rules out new infrastructure. The counter therefore
lives per worker process, so a deployment running N workers allows up to N times
the configured budget. That is adequate for slowing down onboarding and account
abuse, and is not a substitute for an edge rate limiter on a multi-worker
deployment.
"""

from __future__ import annotations

import threading
import time
from collections import defaultdict, deque

from fastapi import HTTPException, Request, status


class SlidingWindowRateLimiter:
    """Allow at most ``limit`` events per ``window_seconds`` for each key."""

    def __init__(self, *, limit: int, window_seconds: float) -> None:
        self.limit = limit
        self.window_seconds = window_seconds
        self._events: dict[str, deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()

    def check(self, key: str) -> bool:
        """Record an event for the key and return whether it is within budget."""
        now = time.monotonic()
        cutoff = now - self.window_seconds
        with self._lock:
            events = self._events[key]
            while events and events[0] <= cutoff:
                events.popleft()
            if len(events) >= self.limit:
                return False
            events.append(now)
            return True

    def reset(self) -> None:
        """Forget all recorded events; used by tests."""
        with self._lock:
            self._events.clear()


def rate_limit(
    *,
    limit: int,
    window_seconds: float,
    scope: str,
):
    """Return a dependency that rate-limits a route by client address."""
    limiter = SlidingWindowRateLimiter(limit=limit, window_seconds=window_seconds)

    async def dependency(request: Request) -> None:
        client = request.client.host if request.client else "unknown"
        if not limiter.check(f"{scope}:{client}"):
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Too many requests. Try again later.",
            )

    dependency.limiter = limiter
    return dependency
