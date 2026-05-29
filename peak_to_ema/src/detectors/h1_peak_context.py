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
    impulse_ratio: float = 0.018,
) -> H1PeakContextResult:
    min_required = max(ema_period + 3, impulse_lookback + 3)
    if len(candles_1h) < min_required:
        return H1PeakContextResult(
            ok=False,
            impulse_up=False,
            rejection_candle=False,
            no_continuation=False,
            reason="not_enough_candles",
        )

    closes = [_to_float(c.get("close")) for c in candles_1h]
    recent = candles_1h[-1]
    previous = candles_1h[-2]
    ema20 = _ema(closes[:-1], ema_period) or _ema(closes, ema_period) or 0.0

    recent_open = _to_float(recent.get("open"))
    recent_high = _to_float(recent.get("high"))
    recent_low = _to_float(recent.get("low"))
    recent_close = _to_float(recent.get("close"))
    previous_high = _to_float(previous.get("high"))
    previous_close = _to_float(previous.get("close"))

    if min(recent_open, recent_high, recent_low, recent_close) <= 0:
        return H1PeakContextResult(
            ok=False,
            impulse_up=False,
            rejection_candle=False,
            no_continuation=False,
            reason="bad_candle_data",
        )

    base_window = closes[-(impulse_lookback + 2) : -2]
    base_close = min(base_window) if base_window else previous_close
    impulse_up = previous_high >= base_close * (1.0 + impulse_ratio)

    candle_range = max(recent_high - recent_low, recent_high * 0.0001)
    upper_wick = recent_high - max(recent_open, recent_close)
    closes_lower_half = recent_close <= recent_low + candle_range * 0.55
    rejected_from_peak = recent_high >= max(previous_high, ema20) and recent_close < recent_open
    rejection_candle = rejected_from_peak and upper_wick >= candle_range * 0.25 and closes_lower_half

    no_continuation = recent_close <= previous_high and recent_high <= previous_high * 1.004
    ok = rejection_candle and no_continuation
    reason = "ok"
    if not rejection_candle:
        reason = "rejection_missing"
    elif not no_continuation:
        reason = "continuation_after_peak"

    return H1PeakContextResult(
        ok=ok,
        impulse_up=impulse_up,
        rejection_candle=rejection_candle,
        no_continuation=no_continuation,
        reason=reason,
    )
