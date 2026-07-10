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


def evaluate_h1_peak_context(
    candles_1h: list[dict],
    *,
    lookback_bars: int = 24,
    impulse_min_pct: float = 0.018,
    rejection_wick_ratio: float = 0.45,
    continuation_tolerance: float = 0.001,
) -> H1PeakContextResult:
    if len(candles_1h) < max(6, lookback_bars // 2):
        return H1PeakContextResult(
            ok=False,
            impulse_up=False,
            rejection_candle=False,
            no_continuation=False,
            reason="not_enough_candles",
        )

    window = candles_1h[-lookback_bars:]
    closes = [_to_float(c.get("close")) for c in window]
    highs = [_to_float(c.get("high")) for c in window]
    if not closes or not highs or min(closes) <= 0:
        return H1PeakContextResult(
            ok=False,
            impulse_up=False,
            rejection_candle=False,
            no_continuation=False,
            reason="invalid_candles",
        )

    last = window[-1]
    prev_low = min(closes[:-1]) if len(closes) > 1 else closes[0]
    last_high = _to_float(last.get("high"))
    last_open = _to_float(last.get("open"))
    last_close = _to_float(last.get("close"))
    last_low = _to_float(last.get("low"))

    impulse_up = (max(highs) - prev_low) / prev_low >= impulse_min_pct
    range_size = max(last_high - last_low, 0.0)
    upper_wick = max(last_high - max(last_open, last_close), 0.0)
    rejection_candle = range_size > 0 and upper_wick / range_size >= rejection_wick_ratio and last_close < last_high
    prior_high = max(highs[:-1]) if len(highs) > 1 else last_high
    no_continuation = last_close <= prior_high * (1 + continuation_tolerance)

    if not impulse_up:
        reason = "impulse_up_missing"
    elif not rejection_candle:
        reason = "rejection_missing"
    elif not no_continuation:
        reason = "continuation_detected"
    else:
        reason = "ok"

    return H1PeakContextResult(
        ok=impulse_up and rejection_candle and no_continuation,
        impulse_up=impulse_up,
        rejection_candle=rejection_candle,
        no_continuation=no_continuation,
        reason=reason,
    )
