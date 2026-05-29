import json
import urllib.parse
import urllib.request


class MarketGateway:
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
            return json.loads(resp.read().decode("utf-8"))

    def get_klines(self, symbol: str, interval: str, *, limit: int = 120) -> list[dict]:
        data = self._get_json(
            "/api/v3/klines",
            {
                "symbol": (symbol or "").upper(),
                "interval": interval,
                "limit": max(1, int(limit)),
            },
        )
        if not isinstance(data, list):
            return []
        candles: list[dict] = []
        for row in data:
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
        data = self._get_json("/api/v3/ticker/24hr")
        if not isinstance(data, list):
            return []
        rows: list[tuple[float, str]] = []
        for item in data:
            if not isinstance(item, dict):
                continue
            symbol = str(item.get("symbol") or "").upper()
            if not symbol.endswith("USDT"):
                continue
            try:
                quote_volume = float(item.get("quoteVolume") or 0.0)
            except (TypeError, ValueError):
                quote_volume = 0.0
            if quote_volume >= min_quote_volume_24h:
                rows.append((quote_volume, symbol))
        rows.sort(reverse=True)
        return [symbol for _quote_volume, symbol in rows[: max(1, int(max_symbols))]]
