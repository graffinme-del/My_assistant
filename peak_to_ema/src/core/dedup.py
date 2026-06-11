import time


class SignalDedup:
    """In-memory TTL deduplication for repeated signal alerts."""

    def __init__(self, ttl_sec: float = 1800.0) -> None:
        self.ttl_sec = max(1.0, float(ttl_sec))
        self._seen_at: dict[str, float] = {}

    def _prune(self, now: float | None = None) -> None:
        ts = time.time() if now is None else now
        expired = [key for key, seen_at in self._seen_at.items() if ts - seen_at >= self.ttl_sec]
        for key in expired:
            self._seen_at.pop(key, None)

    def is_duplicate(self, key: str) -> bool:
        if not key:
            return False
        now = time.time()
        self._prune(now)
        return key in self._seen_at

    def mark(self, key: str) -> None:
        if not key:
            return
        now = time.time()
        self._prune(now)
        self._seen_at[key] = now
