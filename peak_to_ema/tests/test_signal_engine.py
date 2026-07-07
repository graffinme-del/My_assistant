from types import SimpleNamespace

from src.core import signal_engine


def test_evaluate_symbol_rejects_when_m15_detector_rejects(monkeypatch) -> None:
    monkeypatch.setattr(
        signal_engine,
        "evaluate_h1_peak_context",
        lambda candles: SimpleNamespace(
            ok=True,
            reason="ok",
            impulse_up=True,
            rejection_candle=True,
            no_continuation=True,
        ),
    )
    monkeypatch.setattr(
        signal_engine,
        "evaluate_m15_entry",
        lambda candles: SimpleNamespace(
            ready=False,
            reason="local_low_not_broken",
            ema20_retest_fail=True,
            local_low_break=True,
            price_above_ema20_15m=False,
            entry_trigger=99.0,
            stop=101.0,
        ),
    )

    result = signal_engine.evaluate_symbol(
        "BTCUSDT",
        candles_1h=[{"close": 1.0}],
        candles_15m=[{"close": 1.0}],
    )

    assert result.score >= 75
    assert result.ready is False
    assert result.reason_code == "m15_local_low_not_broken"
