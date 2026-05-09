from types import SimpleNamespace

from src.core import signal_engine


def test_signal_engine_rejects_when_m15_is_not_ready(monkeypatch) -> None:
    monkeypatch.setattr(
        signal_engine,
        "evaluate_h1_peak_context",
        lambda _candles: SimpleNamespace(
            ok=True,
            impulse_up=True,
            rejection_candle=True,
            no_continuation=True,
            reason="ok",
        ),
    )
    monkeypatch.setattr(
        signal_engine,
        "evaluate_m15_entry",
        lambda _candles: SimpleNamespace(
            ready=False,
            ema20_retest_fail=True,
            local_low_break=False,
            entry_trigger=0.0,
            stop=0.0,
            price_above_ema20_15m=False,
            reason="local_low_not_broken",
        ),
    )

    result = signal_engine.evaluate_symbol(
        "BTCUSDT",
        candles_1h=[{}],
        candles_15m=[{}],
        oi_down=True,
        cvd_down=True,
        volume_bounce_weak=True,
    )

    assert result.ready is False
    assert result.reason_code == "m15_local_low_not_broken"
    assert result.entry_trigger == 0.0
    assert result.stop == 0.0


def test_peak_runtime_imports() -> None:
    from src.main import main

    assert callable(main)
