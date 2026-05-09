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
    if len(candles_1h) < 24:
        return H1PeakContextResult(
            ok=False,
            impulse_up=False,
            rejection_candle=False,
            no_continuation=False,
            reason="not_enough_candles",
        )

    trigger = candles_1h[-1]
    previous = candles_1h[-2]
    lookback = candles_1h[-24:-1]

    trigger_open = _to_float(trigger.get("open"))
    trigger_high = _to_float(trigger.get("high"))
    trigger_low = _to_float(trigger.get("low"))
    trigger_close = _to_float(trigger.get("close"))
    previous_high = _to_float(previous.get("high"))

    if trigger_high <= trigger_low or trigger_close <= 0:
        return H1PeakContextResult(
            ok=False,
            impulse_up=False,
            rejection_candle=False,
            no_continuation=False,
            reason="bad_candle",
        )

    lows = [_to_float(c.get("low")) for c in lookback if _to_float(c.get("low")) > 0]
    highs = [_to_float(c.get("high")) for c in lookback if _to_float(c.get("high")) > 0]
    if not lows or not highs:
        return H1PeakContextResult(
            ok=False,
            impulse_up=False,
            rejection_candle=False,
            no_continuation=False,
            reason="bad_history",
        )

    range_size = trigger_high - trigger_low
    body_size = abs(trigger_close - trigger_open)
    upper_wick = trigger_high - max(trigger_open, trigger_close)

    impulse_up = trigger_high >= min(lows) * 1.03 and trigger_high >= max(highs) * 0.995
    rejection_candle = upper_wick >= max(body_size, range_size * 0.25) and trigger_close <= trigger_low + range_size * 0.55
    no_continuation = trigger_close <= previous_high

    if not impulse_up:
        reason = "impulse_up_missing"
    elif not rejection_candle:
        reason = "rejection_candle_missing"
    elif not no_continuation:
        reason = "continuation_after_peak"
    else:
        reason = "ok"

    return H1PeakContextResult(
        ok=impulse_up and rejection_candle and no_continuation,
        impulse_up=impulse_up,
        rejection_candle=rejection_candle,
        no_continuation=no_continuation,
        reason=reason,
    )
