from types import SimpleNamespace

from src.core.signal_engine import evaluate_symbol


def test_signal_engine_importable() -> None:
    import src.core.signal_engine  # noqa: F401
    import src.main  # noqa: F401


def test_signal_not_ready_when_m15_rejected_despite_high_score() -> None:
    import src.core.signal_engine as signal_engine

    original_h1 = signal_engine.evaluate_h1_peak_context
    original_m15 = signal_engine.evaluate_m15_entry
    try:
        signal_engine.evaluate_h1_peak_context = lambda candles: SimpleNamespace(
            ok=True,
            impulse_up=True,
            rejection_candle=True,
            no_continuation=True,
            reason="ok",
        )
        signal_engine.evaluate_m15_entry = lambda candles: SimpleNamespace(
            ready=False,
            ema20_retest_fail=True,
            local_low_break=True,
            entry_trigger=0.0,
            stop=0.0,
            price_above_ema20_15m=False,
            reason="price_closed_above_ema20",
        )

        result = evaluate_symbol(symbol="BTCUSDT", candles_1h=[{"close": 1}], candles_15m=[{"close": 1}])
    finally:
        signal_engine.evaluate_h1_peak_context = original_h1
        signal_engine.evaluate_m15_entry = original_m15

    assert result.score >= 75
    assert result.ready is False
    assert result.reason_code == "m15_price_closed_above_ema20"
    assert result.dedup_key == ""
