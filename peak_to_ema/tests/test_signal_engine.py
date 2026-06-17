from types import SimpleNamespace

from src.core.dedup import SignalDedup
from src.core import signal_engine
from src import main as runtime_main


def _h1_ok() -> SimpleNamespace:
    return SimpleNamespace(
        ok=True,
        reason="ok",
        impulse_up=True,
        rejection_candle=True,
        no_continuation=True,
    )


def _m15_rejected() -> SimpleNamespace:
    return SimpleNamespace(
        ready=False,
        reason="local_low_not_broken",
        ema20_retest_fail=True,
        local_low_break=True,
        price_above_ema20_15m=False,
        entry_trigger=99.0,
        stop=101.0,
    )


def _m15_ready() -> SimpleNamespace:
    return SimpleNamespace(
        ready=True,
        reason="ok",
        ema20_retest_fail=True,
        local_low_break=True,
        price_above_ema20_15m=False,
        entry_trigger=99.0,
        stop=101.0,
    )


def test_signal_not_ready_when_m15_rejects_entry() -> None:
    old_h1 = signal_engine.evaluate_h1_peak_context
    old_m15 = signal_engine.evaluate_m15_entry
    try:
        signal_engine.evaluate_h1_peak_context = lambda candles: _h1_ok()
        signal_engine.evaluate_m15_entry = lambda candles: _m15_rejected()

        result = signal_engine.evaluate_symbol("BTCUSDT", candles_1h=[{}], candles_15m=[{}])

        assert result.ready is False
        assert result.score >= 75
        assert result.reason_code == "m15_local_low_not_broken"
    finally:
        signal_engine.evaluate_h1_peak_context = old_h1
        signal_engine.evaluate_m15_entry = old_m15


def test_signal_engine_checks_duplicate_without_marking_new_signal() -> None:
    old_h1 = signal_engine.evaluate_h1_peak_context
    old_m15 = signal_engine.evaluate_m15_entry
    dedup = SignalDedup(ttl_sec=60)
    try:
        signal_engine.evaluate_h1_peak_context = lambda candles: _h1_ok()
        signal_engine.evaluate_m15_entry = lambda candles: _m15_ready()

        first = signal_engine.evaluate_symbol("BTCUSDT", candles_1h=[{}], candles_15m=[{}], dedup=dedup)
        second = signal_engine.evaluate_symbol("BTCUSDT", candles_1h=[{}], candles_15m=[{}], dedup=dedup)
        dedup.mark(first.dedup_key)
        third = signal_engine.evaluate_symbol("BTCUSDT", candles_1h=[{}], candles_15m=[{}], dedup=dedup)

        assert first.ready is True
        assert second.ready is True
        assert third.ready is False
        assert third.reason_code == "duplicate_signal"
    finally:
        signal_engine.evaluate_h1_peak_context = old_h1
        signal_engine.evaluate_m15_entry = old_m15


def test_run_tick_marks_dedup_only_after_successful_send() -> None:
    result = SimpleNamespace(
        ready=True,
        signal="H1_PEAK_TO_EMA_SHORT",
        score=95,
        entry_trigger=99.0,
        stop=101.0,
        reason_code="ok",
        dedup_key="BTCUSDT|SHORT|99|101",
    )

    class FakeGateway:
        def get_klines(self, symbol: str, interval: str, *, limit: int) -> list[dict]:
            return [{"close": "100"}]

    class FakeDedup:
        def __init__(self) -> None:
            self.marked: list[str] = []

        def mark(self, key: str) -> None:
            self.marked.append(key)

    old_evaluate = runtime_main.evaluate_symbol
    old_send = runtime_main._send_telegram
    try:
        runtime_main.evaluate_symbol = lambda **kwargs: result

        failed_dedup = FakeDedup()
        runtime_main._send_telegram = lambda token, chat_id, text: False
        runtime_main._run_tick(FakeGateway(), failed_dedup, "BTCUSDT", "token", "chat")

        successful_dedup = FakeDedup()
        runtime_main._send_telegram = lambda token, chat_id, text: True
        runtime_main._run_tick(FakeGateway(), successful_dedup, "BTCUSDT", "token", "chat")

        assert failed_dedup.marked == []
        assert successful_dedup.marked == [result.dedup_key]
    finally:
        runtime_main.evaluate_symbol = old_evaluate
        runtime_main._send_telegram = old_send
