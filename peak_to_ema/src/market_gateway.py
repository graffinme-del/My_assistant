import json
import urllib.parse
import urllib.request


class MarketGateway:
    def __init__(self, *, timeout_sec: float = 12.0, base_url: str = "https://api.binance.com") -> None:
        self.timeout_sec = timeout_sec
        self.base_url = base_url.rstrip("/")

    def _get_json(self, path: str, params: dict[str, object]) -> object:
        query = urllib.parse.urlencode(params)
        url = f"{self.base_url}{path}?{query}" if query else f"{self.base_url}{path}"
        req = urllib.request.Request(url, headers={"User-Agent": "peak-to-ema/1.0"})
        with urllib.request.urlopen(req, timeout=self.timeout_sec) as resp:
            return json.loads(resp.read().decode("utf-8"))

    def get_klines(self, symbol: str, interval: str, *, limit: int = 120) -> list[dict]:
        try:
            rows = self._get_json(
                "/api/v3/klines",
                {
                    "symbol": symbol.upper(),
                    "interval": interval,
                    "limit": max(1, int(limit)),
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

    def get_dynamic_symbols(self, *, min_quote_volume_24h: float, max_symbols: int) -> list[str]:
        try:
            rows = self._get_json("/api/v3/ticker/24hr", {})
        except Exception:
            return []
        if not isinstance(rows, list):
            return []

        symbols: list[tuple[float, str]] = []
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
                symbols.append((quote_volume, symbol))

        symbols.sort(reverse=True)
        return [symbol for _, symbol in symbols[: max(1, int(max_symbols))]]
