import unittest

from src.detectors.m15_entry import evaluate_m15_entry


def _c(open_: float, high: float, low: float, close: float, volume: float) -> dict:
    return {
        "open": open_,
        "high": high,
        "low": low,
        "close": close,
        "volume": volume,
    }


class M15EntryRegressionTests(unittest.TestCase):
    def test_soft_mode_ready_without_claiming_local_low_break(self) -> None:
        candles = [_c(100.0, 100.2, 99.8, 100.0, 500)] * 20 + [
            _c(99.9, 100.1, 99.7, 99.95, 520),
            _c(99.8, 99.95, 99.6, 99.75, 510),
            _c(99.75, 99.9, 99.62, 99.74, 505),
            _c(99.74, 99.88, 99.63, 99.73, 500),
            _c(99.73, 99.86, 99.64, 99.72, 700),
        ]

        res = evaluate_m15_entry(candles)

        self.assertIs(res.ready, True)
        self.assertIs(res.ema20_retest_fail, True)
        self.assertIs(res.local_low_break, False)
        self.assertGreater(res.entry_trigger, 0)


if __name__ == "__main__":
    unittest.main()
