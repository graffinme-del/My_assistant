from src.core.dedup import SignalDedup
from src.core.signal_engine import evaluate_symbol


def _c(open_: float, high: float, low: float, close: float, volume: float = 500) -> dict:
    return {
        "open": open_,
        "high": high,
        "low": low,
        "close": close,
        "volume": volume,
    }


def _soft_m15(final_close: float) -> list[dict]:
    return [_c(100.0, 100.2, 99.8, 100.0)] * 20 + [
        _c(99.9, 100.1, 99.7, 99.95),
        _c(99.8, 99.95, 99.6, 99.75),
        _c(99.75, 99.9, 99.62, 99.74),
        _c(99.74, 99.88, 99.63, 99.73),
        _c(99.73, 99.86, 99.64, final_close),
    ]


def test_soft_m15_without_local_low_break_does_not_get_break_score() -> None:
    h1 = [_c(100.0, 100.2, 99.8, 100.0)] * 24 + [
        _c(100.0, 100.3, 99.8, 100.1),
        _c(100.1, 100.4, 99.0, 99.5),
    ]
    result = evaluate_symbol("BTCUSDT", candles_1h=h1, candles_15m=_soft_m15(99.72))
    assert result.score == 65
    assert result.ready is False
    assert result.reason_code == "score_below_threshold"


def test_soft_m15_dedup_key_stays_stable_when_live_close_moves() -> None:
    h1 = [_c(100.0, 100.4, 99.8, 100.1)] * 24 + [
        _c(100.2, 104.0, 100.0, 103.2),
        _c(103.1, 104.1, 101.2, 101.7),
    ]
    first = evaluate_symbol("BTCUSDT", candles_1h=h1, candles_15m=_soft_m15(99.72))
    second = evaluate_symbol("BTCUSDT", candles_1h=h1, candles_15m=_soft_m15(99.71))
    assert first.ready is True
    assert second.ready is True
    assert first.entry_trigger != second.entry_trigger
    assert first.dedup_key == second.dedup_key


def test_evaluate_symbol_does_not_mark_dedup_before_delivery() -> None:
    h1 = [_c(100.0, 100.4, 99.8, 100.1)] * 24 + [
        _c(100.2, 104.0, 100.0, 103.2),
        _c(103.1, 104.1, 101.2, 101.7),
    ]
    dedup = SignalDedup(ttl_sec=60.0)
    result = evaluate_symbol("BTCUSDT", candles_1h=h1, candles_15m=_soft_m15(99.72), dedup=dedup)
    assert result.ready is True
    assert result.dedup_key
    assert dedup.is_duplicate(result.dedup_key) is False

    dedup.mark(result.dedup_key)
    duplicate = evaluate_symbol("BTCUSDT", candles_1h=h1, candles_15m=_soft_m15(99.72), dedup=dedup)
    assert duplicate.ready is False
    assert duplicate.reason_code == "duplicate_signal"
