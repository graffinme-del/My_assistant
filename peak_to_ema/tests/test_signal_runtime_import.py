import unittest

from src.core.dedup import SignalDedup
from src.core.signal_engine import evaluate_symbol
from src.main import _run_tick


class _EmptyGateway:
    def get_klines(self, _symbol: str, _interval: str, limit: int = 120) -> list[dict]:
        return []


class SignalRuntimeImportTest(unittest.TestCase):
    def test_signal_dedup_expires_keys(self) -> None:
        now = 100.0
        dedup = SignalDedup(ttl_sec=10.0, now_func=lambda: now)

        self.assertFalse(dedup.is_duplicate("BTCUSDT|SHORT|1|2"))
        dedup.mark("BTCUSDT|SHORT|1|2")
        self.assertTrue(dedup.is_duplicate("BTCUSDT|SHORT|1|2"))

        now = 111.0
        self.assertFalse(dedup.is_duplicate("BTCUSDT|SHORT|1|2"))

    def test_runtime_tick_imports_and_handles_missing_market_data(self) -> None:
        dedup = SignalDedup(ttl_sec=60.0)
        _run_tick(_EmptyGateway(), dedup, "BTCUSDT", "", "")

        result = evaluate_symbol("BTCUSDT", candles_1h=[], candles_15m=[], dedup=dedup)
        self.assertFalse(result.ready)
        self.assertEqual(result.reason_code, "missing_market_data")


if __name__ == "__main__":
    unittest.main()
