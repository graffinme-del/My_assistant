import time


class SignalDedup:
    def __init__(self, ttl_sec: float = 1800.0) -> None:
        self.ttl_sec = max(0.0, float(ttl_sec))
        self._expires_at: dict[str, float] = {}

    def _purge_expired(self, now: float) -> None:
        expired = [key for key, expires_at in self._expires_at.items() if expires_at <= now]
        for key in expired:
            self._expires_at.pop(key, None)

    def is_duplicate(self, key: str) -> bool:
        if not key:
            return False
        now = time.monotonic()
        self._purge_expired(now)
        return key in self._expires_at

    def mark(self, key: str) -> None:
        if not key:
            return
        now = time.monotonic()
        self._purge_expired(now)
        self._expires_at[key] = now + self.ttl_sec
