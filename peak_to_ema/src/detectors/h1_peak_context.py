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
    lookback = candles_1h[-24:]
    prior = lookback[:-1]

    start_close = _to_float(prior[0].get("close"))
    peak_high = max((_to_float(c.get("high")) for c in prior), default=0.0)
    impulse_up = start_close > 0 and peak_high >= start_close * 1.03

    open_ = _to_float(trigger.get("open"))
    high = _to_float(trigger.get("high"))
    low = _to_float(trigger.get("low"))
    close = _to_float(trigger.get("close"))
    body = abs(close - open_)
    upper_wick = max(0.0, high - max(open_, close))
    candle_range = max(0.0, high - low)
    rejection_candle = (
        candle_range > 0
        and high >= peak_high * 0.995
        and close < open_
        and upper_wick >= max(body, candle_range * 0.25)
    )
    no_continuation = peak_high > 0 and close <= peak_high * 0.995

    reason = "ok"
    if not impulse_up:
        reason = "impulse_up_missing"
    elif not rejection_candle:
        reason = "rejection_candle_missing"
    elif not no_continuation:
        reason = "continuation_detected"

    return H1PeakContextResult(
        ok=impulse_up and rejection_candle and no_continuation,
        impulse_up=impulse_up,
        rejection_candle=rejection_candle,
        no_continuation=no_continuation,
        reason=reason,
    )
