from types import SimpleNamespace
from unittest.mock import patch

import src.core.signal_engine as signal_engine
import src.main as runtime
from src.core.dedup import SignalDedup
from src.core.signal_engine import SignalResult


class FakeGateway:
    def get_klines(self, symbol: str, interval: str, *, limit: int) -> list[dict]:
        return [{"symbol": symbol, "interval": interval, "limit": limit}]


def _ready_result() -> SignalResult:
    return SignalResult(
        symbol="BTCUSDT",
        signal="H1_PEAK_TO_EMA_SHORT",
        score=80,
        ready=True,
        reason_code="ok",
        entry_trigger=100.0,
        stop=105.0,
        dedup_key="BTCUSDT|SHORT|100|105",
    )


def test_evaluate_symbol_does_not_mark_dedup_before_delivery() -> None:
    h1 = SimpleNamespace(
        ok=True,
        impulse_up=True,
        rejection_candle=True,
        no_continuation=True,
        reason="ok",
    )
    m15 = SimpleNamespace(
        ready=True,
        ema20_retest_fail=True,
        local_low_break=True,
        price_above_ema20_15m=False,
        entry_trigger=100.0,
        stop=105.0,
        reason="ok",
    )
    dedup = SignalDedup(ttl_sec=300)

    with patch.object(signal_engine, "evaluate_h1_peak_context", return_value=h1), patch.object(
        signal_engine, "evaluate_m15_entry", return_value=m15
    ):
        result = signal_engine.evaluate_symbol(
            "BTCUSDT",
            candles_1h=[{"close": 1}],
            candles_15m=[{"close": 1}],
            dedup=dedup,
        )

    assert result.ready is True
    assert result.dedup_key == "BTCUSDT|SHORT|100|105"
    assert dedup.is_duplicate(result.dedup_key) is False


def test_run_tick_marks_dedup_only_after_successful_telegram_send() -> None:
    failed_dedup = SignalDedup(ttl_sec=300)
    with patch.object(runtime, "evaluate_symbol", return_value=_ready_result()), patch.object(
        runtime, "_send_telegram", return_value=False
    ):
        runtime._run_tick(FakeGateway(), failed_dedup, "BTCUSDT", "token", "chat")
    assert failed_dedup.is_duplicate("BTCUSDT|SHORT|100|105") is False

    delivered_dedup = SignalDedup(ttl_sec=300)
    with patch.object(runtime, "evaluate_symbol", return_value=_ready_result()), patch.object(
        runtime, "_send_telegram", return_value=True
    ):
        runtime._run_tick(FakeGateway(), delivered_dedup, "BTCUSDT", "token", "chat")
    assert delivered_dedup.is_duplicate("BTCUSDT|SHORT|100|105") is True
