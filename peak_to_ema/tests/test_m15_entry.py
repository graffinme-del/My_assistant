import importlib
import os
import sys
import types
from dataclasses import dataclass

from src.detectors.m15_entry import evaluate_m15_entry


def _c(open_: float, high: float, low: float, close: float, volume: float) -> dict:
    return {
        "open": open_,
        "high": high,
        "low": low,
        "close": close,
        "volume": volume,
    }


def test_m15_entry_ready_with_retest_fail_and_local_low_break() -> None:
    candles = [_c(100.0, 100.2, 99.8, 100.0, 500)] * 20 + [
        _c(99.9, 100.1, 99.7, 99.95, 520),   # retest fail
        _c(99.8, 99.95, 99.5, 99.7, 510),
        _c(99.7, 99.85, 99.4, 99.6, 505),
        _c(99.6, 99.8, 99.3, 99.45, 500),    # local low
        _c(99.45, 99.6, 99.1, 99.2, 700),    # break
    ]
    res = evaluate_m15_entry(candles)
    assert res.ready is True
    assert res.ema20_retest_fail is True
    assert res.local_low_break is True
    assert res.entry_trigger > 0
    assert res.stop > res.entry_trigger


def test_m15_entry_ready_on_close_below_ema20_without_local_low_break_in_soft_mode() -> None:
    candles = [_c(100.0, 100.2, 99.8, 100.0, 500)] * 20 + [
        _c(99.9, 100.1, 99.7, 99.95, 520),   # retest fail
        _c(99.8, 99.95, 99.6, 99.75, 510),
        _c(99.75, 99.9, 99.62, 99.74, 505),
        _c(99.74, 99.88, 99.63, 99.73, 500),  # no local low break
        _c(99.73, 99.86, 99.64, 99.72, 700),  # still below EMA20
    ]
    res = evaluate_m15_entry(candles)
    assert res.ready is True
    assert res.ema20_retest_fail is True
    assert res.local_low_break is False
    assert res.entry_trigger > 0


def test_signal_engine_does_not_score_soft_mode_as_local_low_break() -> None:
    candles = [_c(100.0, 100.2, 99.8, 100.0, 500)] * 20 + [
        _c(99.9, 100.1, 99.7, 99.95, 520),   # retest fail
        _c(99.8, 99.95, 99.6, 99.75, 510),
        _c(99.75, 99.9, 99.62, 99.74, 505),
        _c(99.74, 99.88, 99.63, 99.73, 500),
        _c(99.73, 99.86, 99.64, 99.72, 700),  # no local low break
    ]

    engine = _load_signal_engine_with_h1(
        impulse_up=False,
        rejection_candle=True,
        no_continuation=True,
    )
    os.environ.pop("M15_REQUIRE_LOCAL_LOW_BREAK", None)
    res = engine.evaluate_symbol("TEST", candles_1h=[{}], candles_15m=candles)

    assert res.score == 65
    assert res.ready is False
    assert res.reason_code == "score_below_threshold"


def test_signal_engine_requires_m15_ready_before_emitting() -> None:
    candles = [_c(100.0, 100.2, 99.8, 100.0, 500)] * 20 + [
        _c(99.9, 100.1, 99.7, 99.95, 520),   # retest fail
        _c(99.8, 99.95, 99.6, 99.75, 510),
        _c(99.75, 99.9, 99.62, 99.74, 505),
        _c(99.74, 99.88, 99.63, 99.73, 500),
        _c(99.73, 99.86, 99.64, 99.72, 700),  # no local low break
    ]

    engine = _load_signal_engine_with_h1(
        impulse_up=True,
        rejection_candle=True,
        no_continuation=True,
    )
    old_env = os.environ.get("M15_REQUIRE_LOCAL_LOW_BREAK")
    os.environ["M15_REQUIRE_LOCAL_LOW_BREAK"] = "1"
    try:
        res = engine.evaluate_symbol("TEST", candles_1h=[{}], candles_15m=candles)
    finally:
        if old_env is None:
            os.environ.pop("M15_REQUIRE_LOCAL_LOW_BREAK", None)
        else:
            os.environ["M15_REQUIRE_LOCAL_LOW_BREAK"] = old_env

    assert res.ready is False
    assert res.score == 85
    assert res.reason_code == "m15_local_low_not_broken"
    assert res.entry_trigger == 0.0
    assert res.stop == 0.0


def test_m15_entry_rejected_if_price_closes_above_ema20() -> None:
    candles = [_c(100.0, 100.2, 99.8, 100.0, 500)] * 20 + [
        _c(99.9, 100.1, 99.7, 99.95, 520),   # retest fail
        _c(99.8, 99.95, 99.5, 99.7, 510),
        _c(99.7, 99.85, 99.4, 99.6, 505),
        _c(99.6, 99.8, 99.3, 99.45, 500),
        _c(99.45, 100.4, 99.1, 100.35, 700),  # closes above EMA zone
    ]
    res = evaluate_m15_entry(candles)
    assert res.ready is False
    assert res.reason in ("price_closed_above_ema20", "price_closed_above_pullback_high")


def _load_signal_engine_with_h1(
    *,
    impulse_up: bool,
    rejection_candle: bool,
    no_continuation: bool,
):
    core_mod = types.ModuleType("src.core.dedup")

    class SignalDedup:
        pass

    core_mod.SignalDedup = SignalDedup
    sys.modules["src.core.dedup"] = core_mod

    h1_mod = types.ModuleType("src.detectors.h1_peak_context")

    @dataclass
    class H1Result:
        ok: bool
        reason: str
        impulse_up: bool
        rejection_candle: bool
        no_continuation: bool

    def evaluate_h1_peak_context(_candles):
        return H1Result(
            ok=True,
            reason="ok",
            impulse_up=impulse_up,
            rejection_candle=rejection_candle,
            no_continuation=no_continuation,
        )

    h1_mod.evaluate_h1_peak_context = evaluate_h1_peak_context
    sys.modules["src.detectors.h1_peak_context"] = h1_mod
    sys.modules.pop("src.core.signal_engine", None)
    return importlib.import_module("src.core.signal_engine")
