import unittest
from types import SimpleNamespace
from unittest.mock import patch

from src.core.signal_engine import evaluate_symbol


class RecordingDedup:
    def __init__(self, duplicate: bool = False) -> None:
        self.duplicate = duplicate
        self.marked: list[str] = []

    def is_duplicate(self, key: str) -> bool:
        return self.duplicate

    def mark(self, key: str) -> None:
        self.marked.append(key)


def _h1(**overrides: object) -> SimpleNamespace:
    values = {
        "ok": True,
        "impulse_up": True,
        "rejection_candle": True,
        "no_continuation": True,
        "reason": "ok",
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def _m15(**overrides: object) -> SimpleNamespace:
    values = {
        "ready": True,
        "ema20_retest_fail": True,
        "local_low_break": True,
        "local_low": 98.5,
        "pullback_high": 101.0,
        "price_above_ema20_15m": False,
        "entry_trigger": 99.0,
        "stop": 101.2,
        "reason": "ok",
    }
    values.update(overrides)
    return SimpleNamespace(**values)


class SignalEngineRegressionTests(unittest.TestCase):
    def test_rejected_m15_entry_cannot_emit_ready_signal(self) -> None:
        with patch("src.core.signal_engine.evaluate_h1_peak_context", return_value=_h1()), patch(
            "src.core.signal_engine.evaluate_m15_entry",
            return_value=_m15(
                ready=False,
                local_low_break=False,
                entry_trigger=0.0,
                stop=0.0,
                reason="local_low_not_broken",
            ),
        ):
            result = evaluate_symbol("BTCUSDT", candles_1h=[{}], candles_15m=[{}], dedup=RecordingDedup())

        self.assertFalse(result.ready)
        self.assertEqual(result.reason_code, "m15_local_low_not_broken")
        self.assertEqual(result.entry_trigger, 0.0)
        self.assertEqual(result.stop, 0.0)

    def test_soft_m15_without_local_low_break_does_not_inflate_score(self) -> None:
        weak_h1 = _h1(ok=False, impulse_up=False, reason="impulse_up_missing")
        soft_m15 = _m15(local_low_break=False, entry_trigger=99.72, stop=101.25)
        with patch("src.core.signal_engine.evaluate_h1_peak_context", return_value=weak_h1), patch(
            "src.core.signal_engine.evaluate_m15_entry",
            return_value=soft_m15,
        ):
            result = evaluate_symbol("BTCUSDT", candles_1h=[{}], candles_15m=[{}], dedup=RecordingDedup())

        self.assertFalse(result.ready)
        self.assertEqual(result.score, 65)
        self.assertEqual(result.reason_code, "h1_impulse_up_missing")


if __name__ == "__main__":
    unittest.main()
