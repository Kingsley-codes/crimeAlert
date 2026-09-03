"""Small, dependency-free security controls shared by routes."""

from collections import defaultdict, deque
from threading import Lock
from time import monotonic

from flask import current_app, request


class InMemoryRateLimiter:
    """Best-effort process-local limiter for unauthenticated abuse-sensitive routes.

    Deployments with more than one worker should use the same limits at the proxy or
    replace this with a shared-store limiter; this still protects each worker.
    """

    def __init__(self) -> None:
        self._events: dict[str, deque[float]] = defaultdict(deque)
        self._lock = Lock()

    def allow(self, bucket: str, limit: int) -> bool:
        now = monotonic()
        window = current_app.config["RATE_LIMIT_WINDOW_SECONDS"]
        # Include the application object so isolated test/application instances do
        # not share a limiter bucket in the same Python process.
        key = f"{id(current_app._get_current_object())}:{bucket}:{request.remote_addr or 'unknown'}"
        with self._lock:
            events = self._events[key]
            while events and events[0] <= now - window:
                events.popleft()
            if len(events) >= limit:
                return False
            events.append(now)
            return True


rate_limiter = InMemoryRateLimiter()
