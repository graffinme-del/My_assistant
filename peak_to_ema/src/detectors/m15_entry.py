import os
from dataclasses import dataclass
from typing import Optional


@dataclass
class M15EntryResult:
    ready: bool
    ema20_retest_fail: bool
    local_low_break: bool
    local_low: float
    pullback_high: float
    entry_trigger: float
    stop: float
    atr_15m: float
    price_above_ema20_15m: bool
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


def _ema_series(values: list[float], period: int) -> list[Optional[float]]:
    out: list[Optional[float]] = [None] * len(values)
    if len(values) < period:
        return out
    k = 2.0 / (period + 1)
    ema_value = sum(values[:period]) / period
    out[period - 1] = ema_value
    for idx in range(period, len(values)):
        ema_value = values[idx] * k + ema_value * (1 - k)
        out[idx] = ema_value
    return out


def _atr(candles: list[dict], period: int = 14) -> float:
    if len(candles) < period + 1:
        return 0.0
    trs: list[float] = []
    for idx in range(-period, 0):
        h = _to_float(candles[idx].get("high"))
        l = _to_float(candles[idx].get("low"))
        pc = _to_float(candles[idx - 1].get("close"))
        trs.append(max(h - l, abs(h - pc), abs(l - pc)))
    return sum(trs) / len(trs) if trs else 0.0


def evaluate_m15_entry(
    candles_15m: list[dict],
    *,
    ema_period: int = 20,
    atr_period: int = 14,
    retest_touch_ratio: float = 0.998,
    local_low_min_bars: int = 3,
    local_low_max_bars: int = 8,
) -> M15EntryResult:
    min_required = max(ema_period + 2, atr_period + local_low_max_bars + 2)
    if len(candles_15m) < min_required:
        return M15EntryResult(
            ready=False,
            ema20_retest_fail=False,
            local_low_break=False,
            local_low=0.0,
            pullback_high=0.0,
            entry_trigger=0.0,
            stop=0.0,
            atr_15m=0.0,
            price_above_ema20_15m=False,
            reason="not_enough_candles",
        )

    closes = [_to_float(c.get("close")) for c in candles_15m]
    ema_row = _ema_series(closes, ema_period)
    atr_value = _atr(candles_15m, atr_period)

    trigger_idx = len(candles_15m) - 1
    trigger = candles_15m[trigger_idx]
    trigger_close = _to_float(trigger.get("close"))

    search_from = max(ema_period - 1, trigger_idx - local_low_max_bars)
    search_to = max(search_from, trigger_idx - local_low_min_bars + 1)

    retest_candidates: list[tuple[int, float]] = []
    for idx in range(search_from, search_to):
        ema = ema_row[idx]
        if ema is None:
            continue
        candle = candles_15m[idx]
        high = _to_float(candle.get("high"))
        close = _to_float(candle.get("close"))
        touched = high >= ema * retest_touch_ratio
        failed = close <= ema
        if touched and failed:
            retest_candidates.append((idx, high))

    retest_idx = -1
    pullback_high = 0.0
    for idx, high in reversed(retest_candidates):
        bars_after = trigger_idx - idx - 1
        if local_low_min_bars <= bars_after <= local_low_max_bars:
            retest_idx = idx
            pullback_high = high
            break

    if retest_idx < 0:
        return M15EntryResult(
            ready=False,
            ema20_retest_fail=False,
            local_low_break=False,
            local_low=0.0,
            pullback_high=0.0,
            entry_trigger=0.0,
            stop=0.0,
            atr_15m=atr_value,
            price_above_ema20_15m=False,
            reason="ema20_retest_fail_missing",
        )

    lows_slice = candles_15m[retest_idx + 1 : trigger_idx]
    if len(lows_slice) < local_low_min_bars:
        return M15EntryResult(
            ready=False,
            ema20_retest_fail=True,
            local_low_break=False,
            local_low=0.0,
            pullback_high=pullback_high,
            entry_trigger=0.0,
            stop=0.0,
            atr_15m=atr_value,
            price_above_ema20_15m=False,
            reason="local_low_window_too_small",
        )

    local_low = min(_to_float(c.get("low")) for c in lows_slice)
    local_low_break = _to_float(trigger.get("low")) < local_low and trigger_close < local_low

    last_ema = ema_row[trigger_idx] or _ema(closes, ema_period) or 0.0
    price_above_ema20 = trigger_close > last_ema if last_ema > 0 else False
    if price_above_ema20:
        return M15EntryResult(
            ready=False,
            ema20_retest_fail=True,
            local_low_break=False,
            local_low=local_low,
            pullback_high=pullback_high,
            entry_trigger=0.0,
            stop=0.0,
            atr_15m=atr_value,
            price_above_ema20_15m=True,
            reason="price_closed_above_ema20",
        )

    if trigger_close > pullback_high:
        return M15EntryResult(
            ready=False,
            ema20_retest_fail=True,
            local_low_break=False,
            local_low=local_low,
            pullback_high=pullback_high,
            entry_trigger=0.0,
            stop=0.0,
            atr_15m=atr_value,
            price_above_ema20_15m=True,
            reason="price_closed_above_pullback_high",
        )

    require_local_low_break = (os.getenv("M15_REQUIRE_LOCAL_LOW_BREAK", "0") or "0").strip().lower() in (
        "1",
        "true",
        "yes",
        "on",
    )
    if require_local_low_break and not local_low_break:
        return M15EntryResult(
            ready=False,
            ema20_retest_fail=True,
            local_low_break=False,
            local_low=local_low,
            pullback_high=pullback_high,
            entry_trigger=0.0,
            stop=0.0,
            atr_15m=atr_value,
            price_above_ema20_15m=False,
            reason="local_low_not_broken",
        )

    entry_buffer = max(trigger_close * 0.0015, atr_value * 0.20)
    stop_buffer = max(trigger_close * 0.0020, atr_value * 0.25)
    # Soft mode (default): signal can fire on confirmed close below EMA20
    # without waiting for local low break.
    entry_trigger = (local_low - entry_buffer) if local_low_break else trigger_close
    stop = pullback_high + stop_buffer

    return M15EntryResult(
        ready=True,
        ema20_retest_fail=True,
        local_low_break=local_low_break,
        local_low=local_low,
        pullback_high=pullback_high,
        entry_trigger=entry_trigger,
        stop=stop,
        atr_15m=atr_value,
        price_above_ema20_15m=False,
        reason="ok",
    )


def m15_entry_ready(candles_15m: list[dict]) -> bool:
    return evaluate_m15_entry(candles_15m).ready
