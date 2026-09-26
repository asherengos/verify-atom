"""Per-IP sliding-window rate limiter -- stdlib only, no dependencies.

Used to guard POST /verify against abuse on a free public endpoint.
Thread-safe; bounded memory (idle client buckets are swept).
"""

from __future__ import annotations

import threading
from collections import deque


class RateLimiter:
    """Allow at most ``max_requests`` per ``window_s`` seconds per client IP."""

    _SWEEP_THRESHOLD = 4096  # sweep idle buckets once we track this many IPs

    def __init__(self, max_requests: int, window_s: float = 60.0):
        if max_requests <= 0:
            raise ValueError("max_requests must be positive")
        self.max_requests = max_requests
        self.window_s = float(window_s)
        self._lock = threading.Lock()
        self._hits: dict[str, deque[float]] = {}

    def check(self, client_ip: str, now: float) -> tuple[bool, float]:
        """Record a hit and report ``(allowed, retry_after_s)``.

        ``retry_after_s`` is > 0 only when the request is denied: the
        seconds until the oldest hit in the window expires.
        """
        with self._lock:
            bucket = self._hits.get(client_ip)
            if bucket is None:
                bucket = deque()
                self._hits[client_ip] = bucket
            cutoff = now - self.window_s
            while bucket and bucket[0] <= cutoff:
                bucket.popleft()
            if len(bucket) >= self.max_requests:
                retry_after = bucket[0] + self.window_s - now
                return False, max(retry_after, 0.0)
            bucket.append(now)
            if len(self._hits) > self._SWEEP_THRESHOLD:
                self._sweep_locked(now)
            return True, 0.0

    def _sweep_locked(self, now: float) -> None:
        cutoff = now - self.window_s
        idle = [ip for ip, bucket in self._hits.items()
                if not bucket or bucket[-1] <= cutoff]
        for ip in idle:
            del self._hits[ip]
