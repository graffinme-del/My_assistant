import sys
import types
from types import SimpleNamespace


class _DummyDedup:
    def __init__(self, *args, **kwargs) -> None:
        pass

    def is_duplicate(self, key: str) -> bool:
        return False

    def mark(self, key: str) -> None:
        pass


def _import_signal_engine():
    dedup_mod = types.ModuleType("src.core.dedup")
    dedup_mod.SignalDedup = _DummyDedup
    h1_mod = types.ModuleType("src.detectors.h1_peak_context")
    h1_mod.evaluate_h1_peak_context = lambda candles: SimpleNamespace(
        impulse_up=False,
        rejection_candle=False,
        no_continuation=False,
        ok=False,
        reason="stub",
    )
    sys.modules["src.core.dedup"] = dedup_mod
    sys.modules["src.detectors.h1_peak_context"] = h1_mod

    from src.core import signal_engine

    return signal_engine


def test_signal_engine_rejects_when_m15_detector_is_not_ready() -> None:
    signal_engine = _import_signal_engine()
    signal_engine.evaluate_h1_peak_context = lambda candles: SimpleNamespace(
        impulse_up=True,
        rejection_candle=True,
        no_continuation=True,
        ok=True,
        reason="ok",
    )
    signal_engine.evaluate_m15_entry = lambda candles: SimpleNamespace(
        ready=False,
        ema20_retest_fail=True,
        local_low_break=True,
        entry_trigger=0.0,
        stop=0.0,
        price_above_ema20_15m=False,
        reason="local_low_not_broken",
    )

    result = signal_engine.evaluate_symbol("BTCUSDT", candles_1h=[{}], candles_15m=[{}])

    assert result.ready is False
    assert result.score >= 75
    assert result.reason_code == "m15_local_low_not_broken"
    assert result.entry_trigger == 0.0
    assert result.stop == 0.0


def test_signal_engine_scores_soft_mode_without_phantom_local_low_break() -> None:
    signal_engine = _import_signal_engine()
    signal_engine.evaluate_h1_peak_context = lambda candles: SimpleNamespace(
        impulse_up=False,
        rejection_candle=True,
        no_continuation=True,
        ok=True,
        reason="ok",
    )
    signal_engine.evaluate_m15_entry = lambda candles: SimpleNamespace(
        ready=True,
        ema20_retest_fail=True,
        local_low_break=False,
        entry_trigger=99.5,
        stop=101.0,
        price_above_ema20_15m=False,
        reason="ok",
    )

    result = signal_engine.evaluate_symbol("BTCUSDT", candles_1h=[{}], candles_15m=[{}])

    assert result.score == 65
    assert result.ready is False
    assert result.reason_code == "score_below_threshold"
