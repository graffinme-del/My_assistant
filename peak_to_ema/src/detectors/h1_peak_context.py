from dataclasses import dataclass


@dataclass
class H1PeakContextResult:
    ok: bool
    impulse_up: bool
    rejection_candle: bool
    no_continuation: bool
    reason: str


def _to_float(value: object, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def evaluate_h1_peak_context(candles_1h: list[dict]) -> H1PeakContextResult:
    if len(candles_1h) < 8:
        return H1PeakContextResult(
            ok=False,
            impulse_up=False,
            rejection_candle=False,
            no_continuation=False,
            reason="not_enough_candles",
        )

    recent = candles_1h[-8:]
    closes = [_to_float(c.get("close")) for c in recent]
    highs = [_to_float(c.get("high")) for c in recent]
    if not all(closes) or not all(highs):
        return H1PeakContextResult(
            ok=False,
            impulse_up=False,
            rejection_candle=False,
            no_continuation=False,
            reason="bad_market_data",
        )

    peak_candle = recent[-1]
    open_ = _to_float(peak_candle.get("open"))
    high = _to_float(peak_candle.get("high"))
    low = _to_float(peak_candle.get("low"))
    close = _to_float(peak_candle.get("close"))

    baseline = min(closes[:-1])
    impulse_up = baseline > 0 and high >= baseline * 1.01

    body = abs(close - open_)
    upper_wick = high - max(open_, close)
    candle_range = max(high - low, 0.0)
    rejection_candle = (
        candle_range > 0
        and close < open_
        and upper_wick >= max(body * 0.75, candle_range * 0.25)
        and close <= low + candle_range * 0.6
    )

    previous_peak = max(highs[:-1])
    no_continuation = close <= previous_peak and high <= max(previous_peak, open_) * 1.002
    ok = impulse_up and rejection_candle and no_continuation
    if not impulse_up:
        reason = "impulse_up_missing"
    elif not rejection_candle:
        reason = "rejection_missing"
    elif not no_continuation:
        reason = "continuation_detected"
    else:
        reason = "ok"

    return H1PeakContextResult(
        ok=ok,
        impulse_up=impulse_up,
        rejection_candle=rejection_candle,
        no_continuation=no_continuation,
        reason=reason,
    )
