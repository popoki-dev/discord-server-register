"""Small in-memory sliding-window rate limiter.

State lives in this process, so limits apply per server process and reset on restart. That's
enough for a single uvicorn process; with several workers or hosts, use a shared store (e.g. Redis).
"""

import math
import threading
import time
from collections import defaultdict, deque

from fastapi import HTTPException, Request, status


class RateLimiter:
    def __init__(self, limit: int, window_seconds: int):
        self.limit = limit
        self.window = window_seconds
        self._events: dict[str, deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()

    def _prune(self, key: str, now: float) -> deque[float]:
        events = self._events[key]
        while events and now - events[0] >= self.window:
            events.popleft()
        if not events:
            self._events.pop(key, None)
            events = self._events[key]
        return events

    def retry_after(self, key: str) -> int:
        """Seconds until another event is allowed for this key (0 if allowed now)."""
        with self._lock:
            now = time.monotonic()
            events = self._prune(key, now)
            if len(events) < self.limit:
                return 0
            return max(1, math.ceil(self.window - (now - events[0])))

    def record(self, key: str) -> None:
        with self._lock:
            now = time.monotonic()
            self._prune(key, now).append(now)

    def hit(self, key: str) -> int:
        """Record an event if allowed; return 0, or the seconds to wait if the limit is reached."""
        with self._lock:
            now = time.monotonic()
            events = self._prune(key, now)
            if len(events) >= self.limit:
                return max(1, math.ceil(self.window - (now - events[0])))
            events.append(now)
            return 0

    def reset(self) -> None:
        with self._lock:
            self._events.clear()


def client_ip(request: Request) -> str:
    # Behind a reverse proxy, run uvicorn with --proxy-headers --forwarded-allow-ips=<proxy IP>
    # so this is the visitor's address rather than the proxy's.
    return request.client.host if request.client else "unknown"


def too_many(wait_seconds: int, what: str) -> HTTPException:
    minutes = math.ceil(wait_seconds / 60)
    when = f"{minutes} minute{'s' if minutes != 1 else ''}" if wait_seconds >= 60 else f"{wait_seconds} seconds"
    return HTTPException(
        status.HTTP_429_TOO_MANY_REQUESTS,
        f"Too many {what}. Please try again in {when}.",
        headers={"Retry-After": str(wait_seconds)},
    )


# Failed sign-ins: per account (stops guessing one password from many addresses) and per
# address (stops trying many accounts from one address).
LOGIN_FAILURES_PER_EMAIL = RateLimiter(limit=10, window_seconds=15 * 60)
LOGIN_FAILURES_PER_IP = RateLimiter(limit=30, window_seconds=15 * 60)
# Discord lookups per user, so one account can't get this server rate-limited by Discord.
CHECKS_PER_USER = RateLimiter(limit=20, window_seconds=60)

ALL_LIMITERS = (LOGIN_FAILURES_PER_EMAIL, LOGIN_FAILURES_PER_IP, CHECKS_PER_USER)
