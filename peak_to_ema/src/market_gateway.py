import json
import urllib.parse
import urllib.request


class MarketGateway:
    """Small Binance REST client used by the polling runtime."""

    def __init__(self, base_url: str = "https://api.binance.com", timeout_sec: float = 12.0) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout_sec = max(1.0, float(timeout_sec))

    def _get_json(self, path: str, params: dict[str, object] | None = None) -> object:
        query = urllib.parse.urlencode(params or {})
        url = f"{self.base_url}{path}"
        if query:
            url = f"{url}?{query}"
        req = urllib.request.Request(url, headers={"User-Agent": "peak-to-ema/1.0"})
        with urllib.request.urlopen(req, timeout=self.timeout_sec) as resp:
            body = resp.read()
        return json.loads(body.decode("utf-8"))

    def get_klines(self, symbol: str, interval: str, *, limit: int = 120) -> list[dict]:
        rows = self._get_json(
            "/api/v3/klines",
            {"symbol": symbol.upper(), "interval": interval, "limit": int(limit)},
        )
        if not isinstance(rows, list):
            return []
        out: list[dict] = []
        for row in rows:
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
                    "close_time": row[6] if len(row) > 6 else None,
                }
            )
        return out

    def get_dynamic_symbols(self, *, min_quote_volume_24h: float, max_symbols: int) -> list[str]:
        rows = self._get_json("/api/v3/ticker/24hr")
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
        return [symbol for _, symbol in candidates[: max(1, int(max_symbols))]]
