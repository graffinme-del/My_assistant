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
    if len(candles_1h) < 12:
        return H1PeakContextResult(
            ok=False,
            impulse_up=False,
            rejection_candle=False,
            no_continuation=False,
            reason="not_enough_candles",
        )

    recent = candles_1h[-8:]
    previous = candles_1h[:-8]
    last = candles_1h[-1]
    prior_high = max(_to_float(c.get("high")) for c in previous)
    recent_high = max(_to_float(c.get("high")) for c in recent)
    recent_low = min(_to_float(c.get("low")) for c in recent)
    last_open = _to_float(last.get("open"))
    last_high = _to_float(last.get("high"))
    last_low = _to_float(last.get("low"))
    last_close = _to_float(last.get("close"))
    prev_close = _to_float(candles_1h[-2].get("close"))

    if prior_high <= 0 or recent_low <= 0 or last_high <= last_low:
        return H1PeakContextResult(
            ok=False,
            impulse_up=False,
            rejection_candle=False,
            no_continuation=False,
            reason="bad_candles",
        )

    impulse_up = recent_high > prior_high and (recent_high - recent_low) / recent_low >= 0.012
    candle_range = last_high - last_low
    upper_wick = last_high - max(last_open, last_close)
    body = abs(last_close - last_open)
    rejection_candle = (
        last_high >= recent_high * 0.999
        and upper_wick >= max(candle_range * 0.35, body * 1.2)
        and last_close <= last_low + candle_range * 0.65
    )
    no_continuation = last_close < recent_high and last_close <= max(prev_close, last_open)
    ok = impulse_up and rejection_candle and no_continuation

    reason = "ok"
    if not impulse_up:
        reason = "impulse_up_missing"
    elif not rejection_candle:
        reason = "rejection_missing"
    elif not no_continuation:
        reason = "continuation_detected"

    return H1PeakContextResult(
        ok=ok,
        impulse_up=impulse_up,
        rejection_candle=rejection_candle,
        no_continuation=no_continuation,
        reason=reason,
    )
