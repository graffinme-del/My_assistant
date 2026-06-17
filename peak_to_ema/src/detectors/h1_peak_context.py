from dataclasses import dataclass
from typing import Optional


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


def _ema(values: list[float], period: int) -> Optional[float]:
    if len(values) < period:
        return None
    k = 2.0 / (period + 1)
    ema_value = sum(values[:period]) / period
    for value in values[period:]:
        ema_value = value * k + ema_value * (1 - k)
    return ema_value


def evaluate_h1_peak_context(
    candles_1h: list[dict],
    *,
    ema_period: int = 20,
    impulse_lookback: int = 12,
) -> H1PeakContextResult:
    min_required = max(ema_period + 2, impulse_lookback + 2)
    if len(candles_1h) < min_required:
        return H1PeakContextResult(False, False, False, False, "not_enough_candles")

    closes = [_to_float(c.get("close")) for c in candles_1h]
    ema_value = _ema(closes[:-1], ema_period)
    if not ema_value or ema_value <= 0:
        return H1PeakContextResult(False, False, False, False, "ema_unavailable")

    trigger = candles_1h[-1]
    prev = candles_1h[-2]
    trigger_open = _to_float(trigger.get("open"))
    trigger_high = _to_float(trigger.get("high"))
    trigger_low = _to_float(trigger.get("low"))
    trigger_close = _to_float(trigger.get("close"))
    prev_close = _to_float(prev.get("close"))

    lookback = closes[-impulse_lookback - 1 : -1]
    start_close = lookback[0] if lookback else prev_close
    impulse_up = prev_close > ema_value and prev_close >= start_close * 1.015

    body = abs(trigger_close - trigger_open)
    upper_wick = max(0.0, trigger_high - max(trigger_open, trigger_close))
    total_range = max(trigger_high - trigger_low, 1e-9)
    rejection_candle = (
        trigger_high > max(prev_close, ema_value)
        and trigger_close < trigger_open
        and upper_wick >= max(body, total_range * 0.25)
    )
    no_continuation = trigger_close <= prev_close
    ok = impulse_up and rejection_candle and no_continuation

    if not impulse_up:
        reason = "impulse_up_missing"
    elif not rejection_candle:
        reason = "rejection_candle_missing"
    elif not no_continuation:
        reason = "continuation_detected"
    else:
        reason = "ok"

    return H1PeakContextResult(ok, impulse_up, rejection_candle, no_continuation, reason)
