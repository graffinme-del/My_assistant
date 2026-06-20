import importlib
import sys
import types
import unittest


class _H1Result:
    ok = True
    reason = "ok"
    impulse_up = True
    rejection_candle = True
    no_continuation = True


class _Dedup:
    def __init__(self) -> None:
        self.marked: list[str] = []

    def is_duplicate(self, key: str) -> bool:
        return False

    def mark(self, key: str) -> None:
        self.marked.append(key)


def _c(open_: float, high: float, low: float, close: float, volume: float) -> dict:
    return {
        "open": open_,
        "high": high,
        "low": low,
        "close": close,
        "volume": volume,
    }


def _soft_mode_candles(trigger_close: float) -> list[dict]:
    return [_c(100.0, 100.2, 99.8, 100.0, 500)] * 20 + [
        _c(99.9, 100.1, 99.7, 99.95, 520),
        _c(99.8, 99.95, 99.6, 99.75, 510),
        _c(99.75, 99.9, 99.62, 99.74, 505),
        _c(99.74, 99.88, 99.63, 99.73, 500),
        _c(99.73, 99.86, 99.64, trigger_close, 700),
    ]


class SignalEngineDedupTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        h1_module = types.ModuleType("src.detectors.h1_peak_context")
        h1_module.evaluate_h1_peak_context = lambda _candles: _H1Result()
        dedup_module = types.ModuleType("src.core.dedup")
        dedup_module.SignalDedup = _Dedup
        sys.modules["src.detectors.h1_peak_context"] = h1_module
        sys.modules["src.core.dedup"] = dedup_module
        cls.signal_engine = importlib.import_module("src.core.signal_engine")

    def test_evaluate_symbol_does_not_mark_before_delivery(self) -> None:
        dedup = _Dedup()
        result = self.signal_engine.evaluate_symbol(
            "BTCUSDT",
            candles_1h=[{}],
            candles_15m=_soft_mode_candles(99.72),
            dedup=dedup,
        )

        self.assertTrue(result.ready)
        self.assertEqual(dedup.marked, [])

    def test_dedup_key_is_stable_when_soft_mode_close_moves(self) -> None:
        first = self.signal_engine.evaluate_symbol(
            "BTCUSDT",
            candles_1h=[{}],
            candles_15m=_soft_mode_candles(99.72),
        )
        second = self.signal_engine.evaluate_symbol(
            "BTCUSDT",
            candles_1h=[{}],
            candles_15m=_soft_mode_candles(99.71),
        )

        self.assertTrue(first.ready)
        self.assertTrue(second.ready)
        self.assertEqual(first.dedup_key, second.dedup_key)


if __name__ == "__main__":
    unittest.main()
