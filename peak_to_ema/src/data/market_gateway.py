import json
import os
import urllib.parse
import urllib.request
from typing import Any


class MarketGateway:
    """Small Binance-compatible HTTP gateway used by the signal runtime."""

    def __init__(self, *, base_url: str | None = None, timeout_sec: float = 12.0) -> None:
        self.base_url = (base_url or os.getenv("MARKET_API_BASE_URL") or "https://fapi.binance.com").rstrip("/")
        self.timeout_sec = max(1.0, float(timeout_sec))

    def _get_json(self, path: str, params: dict[str, Any]) -> Any:
        query = urllib.parse.urlencode({k: v for k, v in params.items() if v is not None})
        url = f"{self.base_url}{path}"
        if query:
            url = f"{url}?{query}"
        req = urllib.request.Request(url, headers={"Accept": "application/json"})
        with urllib.request.urlopen(req, timeout=self.timeout_sec) as resp:
            return json.loads(resp.read().decode("utf-8"))

    def get_klines(self, symbol: str, interval: str, *, limit: int = 120) -> list[dict]:
        try:
            rows = self._get_json(
                "/fapi/v1/klines",
                {
                    "symbol": (symbol or "").upper(),
                    "interval": interval,
                    "limit": max(1, min(int(limit), 1500)),
                },
            )
        except Exception:
            return []
        if not isinstance(rows, list):
            return []

        candles: list[dict] = []
        for row in rows:
            if not isinstance(row, list) or len(row) < 6:
                continue
            candles.append(
                {
                    "open_time": row[0],
                    "open": row[1],
                    "high": row[2],
                    "low": row[3],
                    "close": row[4],
                    "volume": row[5],
                    "close_time": row[6] if len(row) > 6 else None,
                }
            )
        return candles

    def get_dynamic_symbols(
        self,
        *,
        min_quote_volume_24h: float = 5_000_000.0,
        max_symbols: int = 120,
    ) -> list[str]:
        try:
            rows = self._get_json("/fapi/v1/ticker/24hr", {})
        except Exception:
            return []
        if not isinstance(rows, list):
            return []

        candidates: list[tuple[float, str]] = []
        for row in rows:
            if not isinstance(row, dict):
                continue
            symbol = str(row.get("symbol") or "").upper()
            if not symbol.endswith("USDT"):
                continue
            try:
                quote_volume = float(row.get("quoteVolume") or 0.0)
            except (TypeError, ValueError):
                quote_volume = 0.0
            if quote_volume >= min_quote_volume_24h:
                candidates.append((quote_volume, symbol))

        candidates.sort(reverse=True)
        cap = max(1, int(max_symbols))
        return [symbol for _volume, symbol in candidates[:cap]]
