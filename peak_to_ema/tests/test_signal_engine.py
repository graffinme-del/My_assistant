import unittest
from types import SimpleNamespace
from unittest.mock import patch

from src.core.signal_engine import SignalResult, evaluate_symbol
from src.main import _run_tick


class RecordingDedup:
    def __init__(self, duplicate: bool = False) -> None:
        self.duplicate = duplicate
        self.marked: list[str] = []

    def is_duplicate(self, key: str) -> bool:
        return self.duplicate

    def mark(self, key: str) -> None:
        self.marked.append(key)


def _h1_ok() -> SimpleNamespace:
    return SimpleNamespace(
        ok=True,
        impulse_up=True,
        rejection_candle=True,
        no_continuation=True,
        reason="ok",
    )


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
    def test_evaluate_symbol_does_not_mark_dedup_before_delivery(self) -> None:
        dedup = RecordingDedup()
        with patch("src.core.signal_engine.evaluate_h1_peak_context", return_value=_h1_ok()), patch(
            "src.core.signal_engine.evaluate_m15_entry", return_value=_m15()
        ):
            result = evaluate_symbol("BTCUSDT", candles_1h=[{}], candles_15m=[{}], dedup=dedup)

        self.assertTrue(result.ready)
        self.assertEqual(result.score, 100)
        self.assertEqual(result.dedup_key, "BTCUSDT|SHORT|98.5|101")
        self.assertEqual(dedup.marked, [])

    def test_evaluate_symbol_uses_m15_ready_as_mandatory_gate(self) -> None:
        dedup = RecordingDedup()
        with patch("src.core.signal_engine.evaluate_h1_peak_context", return_value=_h1_ok()), patch(
            "src.core.signal_engine.evaluate_m15_entry",
            return_value=_m15(ready=False, reason="local_low_not_broken"),
        ):
            result = evaluate_symbol("BTCUSDT", candles_1h=[{}], candles_15m=[{}], dedup=dedup)

        self.assertFalse(result.ready)
        self.assertEqual(result.score, 100)
        self.assertEqual(result.reason_code, "m15_local_low_not_broken")
        self.assertEqual(dedup.marked, [])

    def test_evaluate_symbol_uses_setup_anchors_for_dedup_key(self) -> None:
        dedup = RecordingDedup()
        h1 = _h1_ok()
        first_m15 = _m15(local_low_break=False, entry_trigger=99.72, stop=101.25)
        next_bar_m15 = _m15(local_low_break=False, entry_trigger=99.68, stop=101.28)

        with patch("src.core.signal_engine.evaluate_h1_peak_context", return_value=h1), patch(
            "src.core.signal_engine.evaluate_m15_entry", return_value=first_m15
        ):
            first = evaluate_symbol("BTCUSDT", candles_1h=[{}], candles_15m=[{}], dedup=dedup)
        with patch("src.core.signal_engine.evaluate_h1_peak_context", return_value=h1), patch(
            "src.core.signal_engine.evaluate_m15_entry", return_value=next_bar_m15
        ):
            second = evaluate_symbol("BTCUSDT", candles_1h=[{}], candles_15m=[{}], dedup=dedup)

        self.assertTrue(first.ready)
        self.assertTrue(second.ready)
        self.assertEqual(first.dedup_key, second.dedup_key)

    def test_run_tick_marks_dedup_only_after_successful_send(self) -> None:
        key = "BTCUSDT|SHORT|98.5|101"
        result = SignalResult(
            symbol="BTCUSDT",
            signal="H1_PEAK_TO_EMA_SHORT",
            score=100,
            ready=True,
            reason_code="ok",
            entry_trigger=99.0,
            stop=101.0,
            dedup_key=key,
        )
        gateway = SimpleNamespace(get_klines=lambda *args, **kwargs: [{}])
        dedup = RecordingDedup()

        with patch("src.main.evaluate_symbol", return_value=result), patch("src.main._send_telegram", return_value=False):
            _run_tick(gateway, dedup, "BTCUSDT", "token", "chat")
        self.assertEqual(dedup.marked, [])

        with patch("src.main.evaluate_symbol", return_value=result), patch("src.main._send_telegram", return_value=True):
            _run_tick(gateway, dedup, "BTCUSDT", "token", "chat")
        self.assertEqual(dedup.marked, [key])


if __name__ == "__main__":
    unittest.main()
