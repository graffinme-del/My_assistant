import json
import urllib.parse
import urllib.request


class MarketGateway:
    """Small Binance REST gateway used by the peak_to_ema runtime loop."""

    def __init__(self, *, base_url: str = "https://api.binance.com", timeout_sec: float = 12.0) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout_sec = max(1.0, float(timeout_sec))

    def _get_json(self, path: str, params: dict[str, object] | None = None) -> object:
        query = urllib.parse.urlencode(params or {})
        url = f"{self.base_url}{path}"
        if query:
            url = f"{url}?{query}"
        req = urllib.request.Request(url, headers={"Accept": "application/json", "User-Agent": "peak-to-ema/1.0"})
        with urllib.request.urlopen(req, timeout=self.timeout_sec) as resp:
            data = resp.read()
        return json.loads(data.decode("utf-8"))

    def get_klines(self, symbol: str, interval: str, *, limit: int = 120) -> list[dict]:
        try:
            rows = self._get_json(
                "/api/v3/klines",
                {
                    "symbol": symbol.upper().strip(),
                    "interval": interval,
                    "limit": max(1, min(int(limit), 1000)),
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
                    "open": float(row[1]),
                    "high": float(row[2]),
                    "low": float(row[3]),
                    "close": float(row[4]),
                    "volume": float(row[5]),
                    "close_time": row[6] if len(row) > 6 else None,
                }
            )
        return candles

    def get_dynamic_symbols(self, *, min_quote_volume_24h: float, max_symbols: int) -> list[str]:
        try:
            rows = self._get_json("/api/v3/ticker/24hr")
        except Exception:
            return []
        if not isinstance(rows, list):
            return []

        candidates: list[tuple[float, str]] = []
        for row in rows:
            if not isinstance(row, dict):
                continue
            symbol = str(row.get("symbol") or "").upper()
            if not symbol.endswith("USDT") or any(x in symbol for x in ("UPUSDT", "DOWNUSDT", "BULLUSDT", "BEARUSDT")):
                continue
            try:
                quote_volume = float(row.get("quoteVolume") or 0.0)
            except (TypeError, ValueError):
                quote_volume = 0.0
            if quote_volume >= min_quote_volume_24h:
                candidates.append((quote_volume, symbol))

        candidates.sort(reverse=True)
        limit = max(1, int(max_symbols))
        return [symbol for _, symbol in candidates[:limit]]
