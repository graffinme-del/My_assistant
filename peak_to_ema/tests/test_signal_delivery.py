import unittest
from types import SimpleNamespace
from unittest.mock import patch

import src.core.signal_engine as signal_engine
import src.main as runtime
from src.core.dedup import SignalDedup
from src.core.signal_engine import SignalResult


class FakeGateway:
    def get_klines(self, symbol: str, interval: str, *, limit: int) -> list[dict]:
        return [{"symbol": symbol, "interval": interval, "limit": limit}]


def _h1() -> SimpleNamespace:
    return SimpleNamespace(
        ok=True,
        impulse_up=True,
        rejection_candle=True,
        no_continuation=True,
        reason="ok",
    )


def _m15(*, entry: float = 100.0, stop: float = 105.0, local_low_break: bool = True) -> SimpleNamespace:
    return SimpleNamespace(
        ready=True,
        ema20_retest_fail=True,
        local_low_break=local_low_break,
        local_low=99.0,
        pullback_high=106.0,
        price_above_ema20_15m=False,
        entry_trigger=entry,
        stop=stop,
        reason="ok",
    )


def _ready_result() -> SignalResult:
    return SignalResult(
        symbol="BTCUSDT",
        signal="H1_PEAK_TO_EMA_SHORT",
        score=80,
        ready=True,
        reason_code="ok",
        entry_trigger=100.0,
        stop=105.0,
        dedup_key="BTCUSDT|SHORT|99|106",
    )


class SignalDeliveryTests(unittest.TestCase):
    def test_evaluate_symbol_does_not_mark_dedup_before_delivery(self) -> None:
        dedup = SignalDedup(ttl_sec=300)

        with patch.object(signal_engine, "evaluate_h1_peak_context", return_value=_h1()), patch.object(
            signal_engine, "evaluate_m15_entry", return_value=_m15()
        ):
            result = signal_engine.evaluate_symbol(
                "BTCUSDT",
                candles_1h=[{"close": 1}],
                candles_15m=[{"close": 1}],
                dedup=dedup,
            )

        self.assertIs(result.ready, True)
        self.assertEqual(result.dedup_key, "BTCUSDT|SHORT|99|106")
        self.assertIs(dedup.is_duplicate(result.dedup_key), False)

    def test_dedup_key_uses_stable_setup_not_live_entry_and_stop(self) -> None:
        with patch.object(signal_engine, "evaluate_h1_peak_context", return_value=_h1()), patch.object(
            signal_engine, "evaluate_m15_entry", side_effect=[_m15(entry=100.0, stop=105.0), _m15(entry=100.3, stop=105.4)]
        ):
            first = signal_engine.evaluate_symbol(
                "BTCUSDT",
                candles_1h=[{"close": 1}],
                candles_15m=[{"close": 1}],
            )
            second = signal_engine.evaluate_symbol(
                "BTCUSDT",
                candles_1h=[{"close": 1}],
                candles_15m=[{"close": 1}],
            )

        self.assertEqual(first.dedup_key, "BTCUSDT|SHORT|99|106")
        self.assertEqual(second.dedup_key, first.dedup_key)

    def test_run_tick_marks_dedup_only_after_successful_telegram_send(self) -> None:
        failed_dedup = SignalDedup(ttl_sec=300)
        with patch.object(runtime, "evaluate_symbol", return_value=_ready_result()), patch.object(
            runtime, "_send_telegram", return_value=False
        ):
            runtime._run_tick(FakeGateway(), failed_dedup, "BTCUSDT", "token", "chat")
        self.assertIs(failed_dedup.is_duplicate("BTCUSDT|SHORT|99|106"), False)

        delivered_dedup = SignalDedup(ttl_sec=300)
        with patch.object(runtime, "evaluate_symbol", return_value=_ready_result()), patch.object(
            runtime, "_send_telegram", return_value=True
        ):
            runtime._run_tick(FakeGateway(), delivered_dedup, "BTCUSDT", "token", "chat")
        self.assertIs(delivered_dedup.is_duplicate("BTCUSDT|SHORT|99|106"), True)


if __name__ == "__main__":
    unittest.main()
