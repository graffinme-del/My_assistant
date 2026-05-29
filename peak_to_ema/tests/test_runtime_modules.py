import importlib

from src.core.dedup import SignalDedup
from src.detectors.h1_peak_context import evaluate_h1_peak_context


def _c(open_: float, high: float, low: float, close: float, volume: float = 500) -> dict:
    return {
        "open": open_,
        "high": high,
        "low": low,
        "close": close,
        "volume": volume,
    }


def test_runtime_main_imports_with_committed_dependencies() -> None:
    module = importlib.import_module("src.main")
    assert module.MarketGateway is not None
    assert module.SignalDedup is not None


def test_signal_dedup_expires_keys() -> None:
    now = [100.0]
    dedup = SignalDedup(ttl_sec=10.0, clock=lambda: now[0])
    dedup.mark("BTCUSDT|SHORT|1|2")
    assert dedup.is_duplicate("BTCUSDT|SHORT|1|2") is True
    now[0] = 111.0
    assert dedup.is_duplicate("BTCUSDT|SHORT|1|2") is False


def test_h1_peak_context_detects_rejection_without_crashing() -> None:
    candles = [_c(100.0, 100.4, 99.8, 100.1)] * 24 + [
        _c(100.2, 104.0, 100.0, 103.2),
        _c(103.1, 104.1, 101.2, 101.7),
    ]
    result = evaluate_h1_peak_context(candles)
    assert result.ok is True
    assert result.rejection_candle is True
    assert result.no_continuation is True
