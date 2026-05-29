import time
from threading import Lock


class SignalDedup:
    """Small in-memory TTL deduplicator for repeated signal polls."""

    def __init__(self, ttl_sec: float = 1800.0, *, clock=time.time) -> None:
        self.ttl_sec = max(1.0, float(ttl_sec))
        self._clock = clock
        self._seen: dict[str, float] = {}
        self._lock = Lock()

    def _purge_expired(self, now: float) -> None:
        cutoff = now - self.ttl_sec
        expired = [key for key, marked_at in self._seen.items() if marked_at <= cutoff]
        for key in expired:
            self._seen.pop(key, None)

    def is_duplicate(self, key: str) -> bool:
        if not key:
            return False
        now = float(self._clock())
        with self._lock:
            self._purge_expired(now)
            return key in self._seen

    def mark(self, key: str) -> None:
        if not key:
            return
        now = float(self._clock())
        with self._lock:
            self._purge_expired(now)
            self._seen[key] = now
