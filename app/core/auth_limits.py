"""Bounded, process-local admission control for expensive authentication requests."""

from collections import Counter, deque
from collections.abc import Callable, Iterator
from functools import lru_cache
from math import ceil
from threading import Lock
from time import monotonic
from typing import Annotated

from fastapi import Depends, HTTPException, Request

from app.core.config import settings


class AuthLimiter:
    """A sliding window plus an in-flight cap, shared by login and registration.

    All decisions are atomic across FastAPI's worker threads. Accepted attempts,
    including successful ones, consume the window budget. State is bounded by the
    global attempt limit; no username, password, token or request body is retained.
    """

    def __init__(
        self,
        *,
        per_peer: int = 10,
        total: int = 120,
        window_seconds: int = 60,
        concurrent: int = 2,
        clock: Callable[[], float] = monotonic,
    ) -> None:
        if min(per_peer, total, window_seconds, concurrent) < 1:
            raise ValueError("Authentication limits must be positive")
        self.per_peer = per_peer
        self.total = total
        self.window_seconds = window_seconds
        self.concurrent = concurrent
        self._clock = clock
        self._lock = Lock()
        self._events: deque[tuple[float, str]] = deque()
        self._counts: Counter[str] = Counter()
        self._active = 0

    def acquire(self, peer: str) -> int | None:
        """Reserve a slot, or return a conservative Retry-After in seconds."""
        with self._lock:
            now = self._clock()
            while self._events and self._events[0][0] <= now - self.window_seconds:
                _, old_peer = self._events.popleft()
                self._counts[old_peer] -= 1
                if not self._counts[old_peer]:
                    del self._counts[old_peer]
            if len(self._events) >= self.total:
                return max(1, ceil(self._events[0][0] + self.window_seconds - now))
            if self._counts[peer] >= self.per_peer:
                oldest = next(at for at, key in self._events if key == peer)
                return max(1, ceil(oldest + self.window_seconds - now))
            if self._active >= self.concurrent:
                return 1
            self._events.append((now, peer))
            self._counts[peer] += 1
            self._active += 1
            return None

    def release(self) -> None:
        with self._lock:
            if self._active < 1:
                raise RuntimeError("Authentication slot released without a reservation")
            self._active -= 1


@lru_cache(maxsize=1)
def get_auth_limiter() -> AuthLimiter:
    return AuthLimiter(
        per_peer=settings.auth_attempts_per_peer,
        total=settings.auth_attempts_total,
        window_seconds=settings.auth_window_seconds,
        concurrent=settings.auth_max_concurrent,
    )


def auth_attempt(
    request: Request, limiter: Annotated[AuthLimiter, Depends(get_auth_limiter)]
) -> Iterator[None]:
    # Use the ASGI peer, never an arbitrary X-Forwarded-For/CF-Connecting-IP header.
    # The server startup disables proxy-header trust until an operator configures it.
    peer = request.client.host if request.client else "unknown"
    retry_after = limiter.acquire(peer)
    if retry_after is not None:
        raise HTTPException(
            status_code=429,
            detail=f"Too many authentication attempts. Retry in {retry_after} seconds.",
            headers={"Retry-After": str(retry_after), "Cache-Control": "no-store"},
        )
    try:
        yield
    finally:
        limiter.release()
