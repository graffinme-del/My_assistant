import importlib.util
import io
import sys
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from types import ModuleType, SimpleNamespace
from unittest.mock import ANY, patch


def _load_main(signal_module: ModuleType | None = None) -> ModuleType:
    dedup_module = ModuleType("src.core.dedup")
    dedup_module.SignalDedup = object
    if signal_module is None:
        signal_module = ModuleType("src.core.signal_engine")
        signal_module.evaluate_symbol = lambda **_: None
    data_module = ModuleType("src.data")
    gateway_module = ModuleType("src.data.market_gateway")
    gateway_module.MarketGateway = object

    module_path = Path(__file__).parents[1] / "src" / "main.py"
    spec = importlib.util.spec_from_file_location("peak_to_ema_test_main", module_path)
    if spec is None or spec.loader is None:
        raise RuntimeError("Unable to load peak_to_ema main module")
    module = importlib.util.module_from_spec(spec)
    with patch.dict(
        sys.modules,
        {
            "src.core.dedup": dedup_module,
            "src.core.signal_engine": signal_module,
            "src.data": data_module,
            "src.data.market_gateway": gateway_module,
        },
    ):
        spec.loader.exec_module(module)
    return module


def _load_signal_engine() -> ModuleType:
    dedup_module = ModuleType("src.core.dedup")
    dedup_module.SignalDedup = object
    h1_module = ModuleType("src.detectors.h1_peak_context")
    h1_module.evaluate_h1_peak_context = lambda _: SimpleNamespace(
        ok=True,
        impulse_up=True,
        rejection_candle=True,
        no_continuation=True,
        reason="ok",
    )

    module_path = Path(__file__).parents[1] / "src" / "core" / "signal_engine.py"
    spec = importlib.util.spec_from_file_location("peak_to_ema_test_signal_engine", module_path)
    if spec is None or spec.loader is None:
        raise RuntimeError("Unable to load peak_to_ema signal engine")
    module = importlib.util.module_from_spec(spec)
    with patch.dict(
        sys.modules,
        {
            spec.name: module,
            "src.core.dedup": dedup_module,
            "src.detectors.h1_peak_context": h1_module,
        },
    ):
        spec.loader.exec_module(module)
    return module


def _c(
    open_: float,
    high: float,
    low: float,
    close: float,
    volume: float = 500,
    *,
    close_time: int,
) -> dict:
    return {
        "open": open_,
        "high": high,
        "low": low,
        "close": close,
        "volume": volume,
        "close_time": close_time,
    }


class MainClosedCandleTests(unittest.TestCase):
    def test_closed_candles_excludes_open_boundary_and_invalid_rows(self) -> None:
        main = _load_main()
        candles = [
            {"id": "closed", "close_time": "999"},
            {"id": "boundary", "close_time": 1000},
            {"id": "open", "close_time": 1001},
            {"id": "missing"},
        ]

        result = main._closed_candles(candles, now_ms=1000)

        self.assertEqual([candle["id"] for candle in result], ["closed"])

    def test_run_tick_only_evaluates_finalized_h1_and_m15_candles(self) -> None:
        main = _load_main()
        closed_h1 = {"id": "closed-h1", "close_time": 999}
        open_h1 = {"id": "open-h1", "close_time": 1001}
        closed_m15 = {"id": "closed-m15", "close_time": 999}
        open_m15 = {"id": "open-m15", "close_time": 1001}

        class Gateway:
            def get_klines(self, symbol: str, interval: str, *, limit: int) -> list[dict]:
                self.assert_request(symbol, interval, limit)
                if interval == "1h":
                    return [closed_h1, open_h1]
                return [closed_m15, open_m15]

            @staticmethod
            def assert_request(symbol: str, interval: str, limit: int) -> None:
                assert symbol == "TESTUSDT"
                assert (interval, limit) in (("1h", 80), ("15m", 120))

        skipped = SimpleNamespace(ready=False, reason_code="m15_price_closed_above_ema20", score=75)
        with (
            patch.object(main.time, "time", return_value=1.0),
            patch.object(main, "evaluate_symbol", return_value=skipped) as evaluate,
            patch.object(main, "_send_telegram") as send_telegram,
            redirect_stdout(io.StringIO()),
        ):
            main._run_tick(Gateway(), object(), "TESTUSDT", "token", "chat")

        evaluate.assert_called_once_with(
            symbol="TESTUSDT",
            candles_1h=[closed_h1],
            candles_15m=[closed_m15],
            dedup=ANY,
        )
        send_telegram.assert_not_called()

    def test_forming_candle_is_only_source_of_detector_ready_state(self) -> None:
        signal_engine = _load_signal_engine()
        main = _load_main(signal_engine)
        candles_1h = [_c(100, 104, 99.8, 100, close_time=100 + idx) for idx in range(12)]
        candles_15m = [
            *[_c(100, 100.2, 99.8, 100, close_time=100 + idx) for idx in range(19)],
            _c(101.5, 102.2, 101.2, 102, close_time=119),
            _c(100.1, 100.3, 99.8, 100.0, close_time=120),
            _c(99.9, 100.0, 99.5, 99.7, close_time=121),
            _c(99.7, 99.85, 99.4, 99.6, close_time=122),
            _c(99.6, 99.8, 99.3, 99.45, close_time=123),
        ]
        forming = _c(99.45, 99.6, 99.1, 99.2, 700, close_time=1001)
        finalized = {**forming, "high": 102.2, "close": 102.0, "close_time": 999}

        prior_result = signal_engine.evaluate_symbol(
            "TESTUSDT",
            candles_1h=candles_1h,
            candles_15m=candles_15m,
        )
        forming_result = signal_engine.evaluate_symbol(
            "TESTUSDT",
            candles_1h=candles_1h,
            candles_15m=[*candles_15m, forming],
        )
        finalized_result = signal_engine.evaluate_symbol(
            "TESTUSDT",
            candles_1h=candles_1h,
            candles_15m=[*candles_15m, finalized],
        )

        self.assertFalse(prior_result.ready)
        self.assertEqual(prior_result.reason_code, "m15_ema20_retest_fail_missing")
        self.assertTrue(forming_result.ready)
        self.assertEqual(forming_result.entry_trigger, 99.1512)
        self.assertFalse(finalized_result.ready)
        self.assertEqual(finalized_result.reason_code, "m15_price_closed_above_ema20")

        class Gateway:
            def get_klines(self, symbol: str, interval: str, *, limit: int) -> list[dict]:
                assert symbol == "TESTUSDT"
                assert (interval, limit) in (("1h", 80), ("15m", 120))
                return candles_1h if interval == "1h" else [*candles_15m, forming]

        with (
            patch.object(main.time, "time", return_value=1.0),
            patch.object(main, "_send_telegram") as send_telegram,
            redirect_stdout(io.StringIO()) as output,
        ):
            main._run_tick(Gateway(), None, "TESTUSDT", "token", "chat")

        send_telegram.assert_not_called()
        self.assertIn("reason=m15_ema20_retest_fail_missing score=65", output.getvalue())


if __name__ == "__main__":
    unittest.main()
