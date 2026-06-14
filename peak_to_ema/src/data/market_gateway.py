import json
import os
import urllib.parse
import urllib.request
from typing import Any


class MarketGateway:
    def __init__(self, base_url: str | None = None, timeout_sec: float = 12.0) -> None:
        self.base_url = (base_url or os.getenv("BINANCE_BASE_URL") or "https://api.binance.com").rstrip("/")
        self.timeout_sec = max(1.0, float(timeout_sec))

    def _get_json(self, path: str, params: dict[str, object] | None = None) -> Any:
        query = urllib.parse.urlencode(params or {})
        url = f"{self.base_url}{path}"
        if query:
            url = f"{url}?{query}"
        req = urllib.request.Request(url, headers={"User-Agent": "peak-to-ema/1.0"})
        with urllib.request.urlopen(req, timeout=self.timeout_sec) as resp:
            return json.loads(resp.read().decode("utf-8"))

    def get_klines(self, symbol: str, interval: str, limit: int = 120) -> list[dict]:
        safe_limit = max(1, min(int(limit), 1000))
        try:
            rows = self._get_json(
                "/api/v3/klines",
                {"symbol": symbol.upper(), "interval": interval, "limit": safe_limit},
            )
        except Exception:
            return []
        out: list[dict] = []
        for row in rows if isinstance(rows, list) else []:
            if not isinstance(row, list) or len(row) < 6:
                continue
            out.append(
                {
                    "open_time": row[0],
                    "open": row[1],
                    "high": row[2],
                    "low": row[3],
                    "close": row[4],
                    "volume": row[5],
                    "close_time": row[6] if len(row) > 6 else 0,
                }
            )
        return out

    def get_dynamic_symbols(self, min_quote_volume_24h: float = 5_000_000.0, max_symbols: int = 120) -> list[str]:
        try:
            rows = self._get_json("/api/v3/ticker/24hr")
        except Exception:
            return []
        candidates: list[tuple[float, str]] = []
        for row in rows if isinstance(rows, list) else []:
            if not isinstance(row, dict):
                continue
            symbol = str(row.get("symbol") or "").upper()
            if not symbol.endswith("USDT"):
                continue
            try:
                quote_volume = float(row.get("quoteVolume") or 0.0)
            except (TypeError, ValueError):
                continue
            if quote_volume >= min_quote_volume_24h:
                candidates.append((quote_volume, symbol))
        candidates.sort(reverse=True)
        return [symbol for _volume, symbol in candidates[: max(1, int(max_symbols))]]
