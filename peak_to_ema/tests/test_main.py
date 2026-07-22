import importlib.util
import io
import sys
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from types import ModuleType, SimpleNamespace
from unittest.mock import ANY, patch


def _load_main() -> ModuleType:
    dedup_module = ModuleType("src.core.dedup")
    dedup_module.SignalDedup = object
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


if __name__ == "__main__":
    unittest.main()
