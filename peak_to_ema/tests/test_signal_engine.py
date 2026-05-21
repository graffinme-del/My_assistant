import importlib
import sys
import types
import unittest
from types import SimpleNamespace


def _load_signal_engine():
    dedup_module = types.ModuleType("src.core.dedup")
    dedup_module.SignalDedup = type("SignalDedup", (), {})
    sys.modules.setdefault("src.core.dedup", dedup_module)

    h1_module = types.ModuleType("src.detectors.h1_peak_context")
    h1_module.evaluate_h1_peak_context = lambda _candles: SimpleNamespace(
        impulse_up=False,
        rejection_candle=False,
        no_continuation=False,
        ok=False,
        reason="stub_not_configured",
    )
    sys.modules.setdefault("src.detectors.h1_peak_context", h1_module)

    return importlib.import_module("src.core.signal_engine")


class SignalEngineGateTest(unittest.TestCase):
    def test_rejected_m15_entry_cannot_emit_ready_signal(self) -> None:
        signal_engine = _load_signal_engine()
        signal_engine.evaluate_h1_peak_context = lambda _candles: SimpleNamespace(
            impulse_up=True,
            rejection_candle=True,
            no_continuation=True,
            ok=True,
            reason="ok",
        )
        signal_engine.evaluate_m15_entry = lambda _candles: SimpleNamespace(
            ready=False,
            ema20_retest_fail=True,
            local_low_break=True,
            price_above_ema20_15m=False,
            entry_trigger=0.0,
            stop=0.0,
            reason="local_low_window_too_small",
        )

        result = signal_engine.evaluate_symbol(
            "BTCUSDT",
            candles_1h=[{"close": 1.0}],
            candles_15m=[{"close": 1.0}],
        )

        self.assertFalse(result.ready)
        self.assertEqual(result.reason_code, "m15_local_low_window_too_small")


if __name__ == "__main__":
    unittest.main()
