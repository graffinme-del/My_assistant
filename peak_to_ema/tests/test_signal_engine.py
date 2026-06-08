from types import SimpleNamespace

import src.core.signal_engine as signal_engine
import src.main as runtime


class _FakeDedup:
    def __init__(self, duplicate: bool = False) -> None:
        self.duplicate = duplicate
        self.marked: list[str] = []

    def is_duplicate(self, key: str) -> bool:
        return self.duplicate

    def mark(self, key: str) -> None:
        self.marked.append(key)


def test_evaluate_symbol_does_not_mark_dedup_before_delivery() -> None:
    old_h1 = signal_engine.evaluate_h1_peak_context
    old_m15 = signal_engine.evaluate_m15_entry
    try:
        signal_engine.evaluate_h1_peak_context = lambda _candles: SimpleNamespace(
            ok=True,
            impulse_up=True,
            rejection_candle=True,
            no_continuation=True,
            reason="ok",
        )
        signal_engine.evaluate_m15_entry = lambda _candles: SimpleNamespace(
            ready=True,
            ema20_retest_fail=True,
            local_low_break=True,
            price_above_ema20_15m=False,
            entry_trigger=99.0,
            stop=105.0,
            reason="ok",
        )
        dedup = _FakeDedup()
        result = signal_engine.evaluate_symbol(
            "BTCUSDT",
            candles_1h=[{"close": 1}],
            candles_15m=[{"close": 1}],
            dedup=dedup,
        )

        assert result.ready is True
        assert result.dedup_key
        assert dedup.marked == []

        dedup.duplicate = True
        duplicate = signal_engine.evaluate_symbol(
            "BTCUSDT",
            candles_1h=[{"close": 1}],
            candles_15m=[{"close": 1}],
            dedup=dedup,
        )
        assert duplicate.ready is False
        assert duplicate.reason_code == "duplicate_signal"
    finally:
        signal_engine.evaluate_h1_peak_context = old_h1
        signal_engine.evaluate_m15_entry = old_m15


def test_evaluate_symbol_requires_h1_ok_even_when_score_is_high() -> None:
    old_h1 = signal_engine.evaluate_h1_peak_context
    old_m15 = signal_engine.evaluate_m15_entry
    try:
        signal_engine.evaluate_h1_peak_context = lambda _candles: SimpleNamespace(
            ok=False,
            impulse_up=False,
            rejection_candle=True,
            no_continuation=True,
            reason="impulse_up_missing",
        )
        signal_engine.evaluate_m15_entry = lambda _candles: SimpleNamespace(
            ready=True,
            ema20_retest_fail=True,
            local_low_break=True,
            price_above_ema20_15m=False,
            entry_trigger=99.0,
            stop=105.0,
            reason="ok",
        )

        result = signal_engine.evaluate_symbol(
            "BTCUSDT",
            candles_1h=[{"close": 1}],
            candles_15m=[{"close": 1}],
        )

        assert result.score >= 75
        assert result.ready is False
        assert result.reason_code == "h1_impulse_up_missing"
    finally:
        signal_engine.evaluate_h1_peak_context = old_h1
        signal_engine.evaluate_m15_entry = old_m15


def test_evaluate_symbol_requires_m15_ready_even_when_retest_flag_is_true() -> None:
    old_h1 = signal_engine.evaluate_h1_peak_context
    old_m15 = signal_engine.evaluate_m15_entry
    try:
        signal_engine.evaluate_h1_peak_context = lambda _candles: SimpleNamespace(
            ok=True,
            impulse_up=True,
            rejection_candle=True,
            no_continuation=True,
            reason="ok",
        )
        signal_engine.evaluate_m15_entry = lambda _candles: SimpleNamespace(
            ready=False,
            ema20_retest_fail=True,
            local_low_break=False,
            price_above_ema20_15m=False,
            entry_trigger=0.0,
            stop=0.0,
            reason="local_low_not_broken",
        )

        result = signal_engine.evaluate_symbol(
            "BTCUSDT",
            candles_1h=[{"close": 1}],
            candles_15m=[{"close": 1}],
        )

        assert result.score >= 75
        assert result.ready is False
        assert result.reason_code == "m15_local_low_not_broken"
        assert result.entry_trigger == 0.0
        assert result.stop == 0.0
    finally:
        signal_engine.evaluate_h1_peak_context = old_h1
        signal_engine.evaluate_m15_entry = old_m15


def test_run_tick_marks_dedup_only_after_successful_delivery() -> None:
    old_evaluate = runtime.evaluate_symbol
    old_send = runtime._send_telegram
    try:
        runtime.evaluate_symbol = lambda **_kwargs: SimpleNamespace(
            ready=True,
            signal="H1_PEAK_TO_EMA_SHORT",
            score=100,
            entry_trigger=99.0,
            stop=105.0,
            reason_code="ok",
            dedup_key="BTCUSDT|SHORT|99|105",
        )
        gw = SimpleNamespace(get_klines=lambda *_args, **_kwargs: [{"close": 1}])
        dedup = _FakeDedup()

        runtime._send_telegram = lambda *_args, **_kwargs: False
        runtime._run_tick(gw, dedup, "BTCUSDT", "token", "chat")
        assert dedup.marked == []

        runtime._send_telegram = lambda *_args, **_kwargs: True
        runtime._run_tick(gw, dedup, "BTCUSDT", "token", "chat")
        assert dedup.marked == ["BTCUSDT|SHORT|99|105"]
    finally:
        runtime.evaluate_symbol = old_evaluate
        runtime._send_telegram = old_send
