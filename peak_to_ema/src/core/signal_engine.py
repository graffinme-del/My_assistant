from dataclasses import dataclass
from typing import Optional

from src.core.dedup import SignalDedup
from src.detectors.h1_peak_context import evaluate_h1_peak_context
from src.detectors.m15_entry import evaluate_m15_entry


@dataclass
class SignalResult:
    symbol: str
    signal: str
    score: int
    ready: bool
    reason_code: str
    entry_trigger: float = 0.0
    stop: float = 0.0
    dedup_key: str = ""


def _score_signal(
    *,
    h1_impulse_up: bool,
    h1_rejection: bool,
    h1_no_continuation: bool,
    m15_retest_fail: bool,
    m15_local_low_break: bool,
    oi_down: bool,
    cvd_down: bool,
    volume_bounce_weak: bool,
    btc_pumping: bool,
    price_above_ema20_15m: bool,
) -> int:
    score = 0
    if h1_impulse_up:
        score += 20
    if h1_rejection:
        score += 25
    if h1_no_continuation:
        score += 20
    if m15_retest_fail:
        score += 20
    if m15_local_low_break:
        score += 15
    if oi_down:
        score += 10
    if cvd_down:
        score += 10
    if volume_bounce_weak:
        score += 10
    if btc_pumping:
        score -= 20
    if price_above_ema20_15m:
        score -= 25
    return score


def evaluate_symbol(
    symbol: str,
    *,
    candles_1h: Optional[list[dict]] = None,
    candles_15m: Optional[list[dict]] = None,
    oi_down: bool = False,
    cvd_down: bool = False,
    volume_bounce_weak: bool = False,
    btc_pumping: bool = False,
    dedup: Optional[SignalDedup] = None,
) -> SignalResult:
    if not candles_1h or not candles_15m:
        return SignalResult(
            symbol=symbol,
            signal="H1_PEAK_TO_EMA_SHORT",
            score=0,
            ready=False,
            reason_code="missing_market_data",
        )

    h1 = evaluate_h1_peak_context(candles_1h)
    m15 = evaluate_m15_entry(candles_15m)
    score = _score_signal(
        h1_impulse_up=h1.impulse_up,
        h1_rejection=h1.rejection_candle,
        h1_no_continuation=h1.no_continuation,
        m15_retest_fail=m15.ema20_retest_fail,
        m15_local_low_break=m15.local_low_break,
        oi_down=oi_down,
        cvd_down=cvd_down,
        volume_bounce_weak=volume_bounce_weak,
        btc_pumping=btc_pumping,
        price_above_ema20_15m=m15.price_above_ema20_15m,
    )

    mandatory_ok = h1.rejection_candle and m15.ema20_retest_fail
    ready = mandatory_ok and h1.no_continuation and m15.ready and score >= 75

    reason_code = "ok" if ready else "mandatory_or_score_failed"
    if not h1.ok:
        reason_code = f"h1_{h1.reason}"
    elif not m15.ready:
        reason_code = f"m15_{m15.reason}"
    elif score < 75:
        reason_code = "score_below_threshold"

    dedup_key = ""
    if m15.entry_trigger > 0 and m15.stop > 0:
        dedup_key = f"{symbol}|SHORT|{m15.entry_trigger:.8g}|{m15.stop:.8g}"
    if ready and dedup and dedup_key:
        if dedup.is_duplicate(dedup_key):
            ready = False
            reason_code = "duplicate_signal"
        else:
            dedup.mark(dedup_key)

    return SignalResult(
        symbol=symbol,
        signal="H1_PEAK_TO_EMA_SHORT",
        score=score,
        ready=ready,
        reason_code=reason_code,
        entry_trigger=m15.entry_trigger,
        stop=m15.stop,
        dedup_key=dedup_key,
    )
