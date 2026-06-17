import time


class SignalDedup:
    """In-memory TTL deduplication for runtime signal alerts."""

    def __init__(self, ttl_sec: float = 1800.0) -> None:
        self.ttl_sec = max(1.0, float(ttl_sec))
        self._seen: dict[str, float] = {}

    def _prune(self, now: float) -> None:
        expired = [key for key, expires_at in self._seen.items() if expires_at <= now]
        for key in expired:
            self._seen.pop(key, None)

    def is_duplicate(self, key: str) -> bool:
        if not key:
            return False
        now = time.monotonic()
        self._prune(now)
        return self._seen.get(key, 0.0) > now

    def mark(self, key: str) -> None:
        if not key:
            return
        now = time.monotonic()
        self._prune(now)
        self._seen[key] = now + self.ttl_sec
