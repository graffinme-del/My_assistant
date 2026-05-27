from dataclasses import dataclass


@dataclass
class H1PeakContextResult:
    ok: bool
    impulse_up: bool
    rejection_candle: bool
    no_continuation: bool
    reason: str
    peak_high: float = 0.0


def _to_float(value: object, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _upper_wick(candle: dict) -> float:
    high = _to_float(candle.get("high"))
    open_ = _to_float(candle.get("open"))
    close = _to_float(candle.get("close"))
    return max(0.0, high - max(open_, close))


def _range(candle: dict) -> float:
    return max(0.0, _to_float(candle.get("high")) - _to_float(candle.get("low")))


def evaluate_h1_peak_context(
    candles_1h: list[dict],
    *,
    lookback_bars: int = 8,
    min_impulse_pct: float = 0.015,
    wick_body_ratio: float = 1.2,
) -> H1PeakContextResult:
    """
    Detect a conservative H1 blow-off/rejection context for a short setup.

    The final candle is treated as confirmation. The peak/rejection candle is
    selected from the preceding lookback window so a new high on the latest bar
    does not count as "no continuation".
    """
    min_required = lookback_bars + 2
    if len(candles_1h) < min_required:
        return H1PeakContextResult(
            ok=False,
            impulse_up=False,
            rejection_candle=False,
            no_continuation=False,
            reason="not_enough_candles",
        )

    confirm = candles_1h[-1]
    window_start = len(candles_1h) - lookback_bars - 1
    rejection_window = candles_1h[window_start:-1]
    base_close = _to_float(candles_1h[window_start - 1].get("close"))
    if base_close <= 0 or not rejection_window:
        return H1PeakContextResult(
            ok=False,
            impulse_up=False,
            rejection_candle=False,
            no_continuation=False,
            reason="bad_market_data",
        )

    peak_candle = max(rejection_window, key=lambda c: _to_float(c.get("high")))
    peak_high = _to_float(peak_candle.get("high"))
    peak_close = _to_float(peak_candle.get("close"))
    peak_open = _to_float(peak_candle.get("open"))
    peak_range = _range(peak_candle)
    peak_body = abs(peak_close - peak_open)
    wick = _upper_wick(peak_candle)

    impulse_up = peak_high >= base_close * (1.0 + min_impulse_pct)
    rejection_candle = (
        peak_range > 0
        and wick >= max(peak_body * wick_body_ratio, peak_range * 0.25)
        and peak_close <= peak_high - peak_range * 0.35
    )
    no_continuation = _to_float(confirm.get("high")) <= peak_high and _to_float(confirm.get("close")) <= peak_close

    reason = "ok"
    if not impulse_up:
        reason = "impulse_up_missing"
    elif not rejection_candle:
        reason = "rejection_candle_missing"
    elif not no_continuation:
        reason = "continuation_after_peak"

    return H1PeakContextResult(
        ok=impulse_up and rejection_candle and no_continuation,
        impulse_up=impulse_up,
        rejection_candle=rejection_candle,
        no_continuation=no_continuation,
        reason=reason,
        peak_high=peak_high,
    )
