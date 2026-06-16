import unittest
from types import SimpleNamespace
from unittest.mock import patch

from src.core.dedup import SignalDedup
from src.core import signal_engine
from src.main import _run_tick


class _EmptyGateway:
    def get_klines(self, _symbol: str, _interval: str, limit: int = 120) -> list[dict]:
        return []


class _FakeDedup:
    def __init__(self) -> None:
        self.marked: list[str] = []

    def is_duplicate(self, _key: str) -> bool:
        return False

    def mark(self, key: str) -> None:
        self.marked.append(key)


class SignalRuntimeTest(unittest.TestCase):
    def test_runtime_tick_imports_and_handles_missing_market_data(self) -> None:
        dedup = SignalDedup(ttl_sec=60.0)
        _run_tick(_EmptyGateway(), dedup, "BTCUSDT", "", "")

        result = signal_engine.evaluate_symbol("BTCUSDT", candles_1h=[], candles_15m=[], dedup=dedup)
        self.assertFalse(result.ready)
        self.assertEqual(result.reason_code, "missing_market_data")

    def test_signal_engine_rejects_when_m15_is_not_ready(self) -> None:
        with patch.object(
            signal_engine,
            "evaluate_h1_peak_context",
            return_value=SimpleNamespace(
                ok=True,
                impulse_up=True,
                rejection_candle=True,
                no_continuation=True,
                reason="ok",
            ),
        ), patch.object(
            signal_engine,
            "evaluate_m15_entry",
            return_value=SimpleNamespace(
                ready=False,
                ema20_retest_fail=True,
                local_low_break=False,
                entry_trigger=0.0,
                stop=0.0,
                price_above_ema20_15m=False,
                reason="local_low_window_too_small",
            ),
        ):
            result = signal_engine.evaluate_symbol(
                "BTCUSDT",
                candles_1h=[{}],
                candles_15m=[{}],
                oi_down=True,
                cvd_down=True,
                volume_bounce_weak=True,
                dedup=_FakeDedup(),
            )

        self.assertFalse(result.ready)
        self.assertEqual(result.reason_code, "m15_local_low_window_too_small")
        self.assertEqual(result.entry_trigger, 0.0)
        self.assertEqual(result.stop, 0.0)

    def test_failed_telegram_send_does_not_mark_signal_duplicate(self) -> None:
        dedup = _FakeDedup()
        result = SimpleNamespace(
            ready=True,
            signal="H1_PEAK_TO_EMA_SHORT",
            score=90,
            entry_trigger=100.0,
            stop=110.0,
            reason_code="ok",
            dedup_key="BTCUSDT|SHORT|100|110",
        )

        with patch("src.main.evaluate_symbol", return_value=result), patch("src.main._send_telegram", return_value=False):
            _run_tick(_EmptyGateway(), dedup, "BTCUSDT", "token", "chat")

        self.assertEqual(dedup.marked, [])

    def test_successful_telegram_send_marks_signal_duplicate(self) -> None:
        dedup = _FakeDedup()
        result = SimpleNamespace(
            ready=True,
            signal="H1_PEAK_TO_EMA_SHORT",
            score=90,
            entry_trigger=100.0,
            stop=110.0,
            reason_code="ok",
            dedup_key="BTCUSDT|SHORT|100|110",
        )

        with patch("src.main.evaluate_symbol", return_value=result), patch("src.main._send_telegram", return_value=True):
            _run_tick(_EmptyGateway(), dedup, "BTCUSDT", "token", "chat")

        self.assertEqual(dedup.marked, ["BTCUSDT|SHORT|100|110"])


if __name__ == "__main__":
    unittest.main()
