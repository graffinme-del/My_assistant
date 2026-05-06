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
    assert res.entry_trigger > 0


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
