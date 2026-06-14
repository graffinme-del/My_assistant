import time
from collections.abc import Callable


class SignalDedup:
    """In-memory TTL deduplication for repeated signal keys."""

    def __init__(self, ttl_sec: float = 1800.0, now_func: Callable[[], float] | None = None) -> None:
        self.ttl_sec = max(0.0, float(ttl_sec))
        self._now = now_func or time.time
        self._expires_at: dict[str, float] = {}

    def _prune(self, now: float) -> None:
        expired = [key for key, expires_at in self._expires_at.items() if expires_at <= now]
        for key in expired:
            self._expires_at.pop(key, None)

    def is_duplicate(self, key: str) -> bool:
        if not key:
            return False
        now = self._now()
        self._prune(now)
        return key in self._expires_at

    def mark(self, key: str) -> None:
        if not key:
            return
        now = self._now()
        self._prune(now)
        self._expires_at[key] = now + self.ttl_sec
