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
    """
    Detect a simple H1 exhaustion context for a short setup:
    recent upward impulse, a rejection candle, then no break of that rejection high.
    """
    if len(candles_1h) < 8:
        return H1PeakContextResult(False, False, False, False, "not_enough_candles")

    previous = candles_1h[-8:-2]
    rejection = candles_1h[-2]
    confirm = candles_1h[-1]

    previous_lows = [_to_float(c.get("low")) for c in previous]
    previous_highs = [_to_float(c.get("high")) for c in previous]
    if not previous_lows or not previous_highs:
        return H1PeakContextResult(False, False, False, False, "bad_candle_data")

    base_low = min(previous_lows)
    prior_high = max(previous_highs)
    rej_open = _to_float(rejection.get("open"))
    rej_high = _to_float(rejection.get("high"))
    rej_low = _to_float(rejection.get("low"))
    rej_close = _to_float(rejection.get("close"))
    conf_high = _to_float(confirm.get("high"))
    conf_close = _to_float(confirm.get("close"))

    if min(base_low, rej_open, rej_high, rej_low, rej_close, conf_high, conf_close) <= 0:
        return H1PeakContextResult(False, False, False, False, "bad_candle_data")

    impulse_up = rej_high >= prior_high and (rej_high - base_low) / base_low >= 0.015
    candle_range = max(rej_high - rej_low, 0.0)
    upper_wick = rej_high - max(rej_open, rej_close)
    body = abs(rej_close - rej_open)
    rejection_candle = candle_range > 0 and upper_wick >= candle_range * 0.35 and upper_wick >= body
    no_continuation = conf_high <= rej_high and conf_close < rej_close

    if not impulse_up:
        reason = "impulse_up_missing"
    elif not rejection_candle:
        reason = "rejection_candle_missing"
    elif not no_continuation:
        reason = "continuation_after_rejection"
    else:
        reason = "ok"

    return H1PeakContextResult(
        ok=impulse_up and rejection_candle and no_continuation,
        impulse_up=impulse_up,
        rejection_candle=rejection_candle,
        no_continuation=no_continuation,
        reason=reason,
    )
