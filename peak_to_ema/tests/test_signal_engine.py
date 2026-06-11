import unittest
from types import SimpleNamespace

import src.core.signal_engine as signal_engine
from src.detectors.m15_entry import evaluate_m15_entry


def _c(open_: float, high: float, low: float, close: float, volume: float = 500) -> dict:
    return {
        "open": open_,
        "high": high,
        "low": low,
        "close": close,
        "volume": volume,
    }


class SignalEngineGateTest(unittest.TestCase):
    def test_rejected_m15_entry_cannot_emit_ready_signal(self) -> None:
        old_h1 = signal_engine.evaluate_h1_peak_context
        old_m15 = signal_engine.evaluate_m15_entry
        try:
            signal_engine.evaluate_h1_peak_context = lambda _candles: SimpleNamespace(
                ok=True,
                impulse_up=True,
                rejection_candle=True,
                no_continuation=True,
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
            self.assertEqual(result.entry_trigger, 0.0)
            self.assertEqual(result.stop, 0.0)
        finally:
            signal_engine.evaluate_h1_peak_context = old_h1
            signal_engine.evaluate_m15_entry = old_m15

    def test_soft_m15_without_local_low_break_does_not_get_break_score(self) -> None:
        candles = [_c(100.0, 100.2, 99.8, 100.0)] * 20 + [
            _c(99.9, 100.1, 99.7, 99.95),
            _c(99.8, 99.95, 99.6, 99.75),
            _c(99.75, 99.9, 99.62, 99.74),
            _c(99.74, 99.88, 99.63, 99.73),
            _c(99.73, 99.86, 99.64, 99.72),
        ]

        m15 = evaluate_m15_entry(candles)
        score = signal_engine._score_signal(
            h1_impulse_up=False,
            h1_rejection=True,
            h1_no_continuation=True,
            m15_retest_fail=m15.ema20_retest_fail,
            m15_local_low_break=m15.local_low_break,
            oi_down=False,
            cvd_down=False,
            volume_bounce_weak=False,
            btc_pumping=False,
            price_above_ema20_15m=m15.price_above_ema20_15m,
        )

        self.assertTrue(m15.ready)
        self.assertFalse(m15.local_low_break)
        self.assertEqual(score, 65)

    def test_runtime_entrypoint_imports(self) -> None:
        import src.main  # noqa: F401


if __name__ == "__main__":
    unittest.main()
