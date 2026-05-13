import importlib.util
import sys
import types
from types import SimpleNamespace


class SignalDedup:
    pass


class MarketGateway:
    pass


def _install_stub_if_missing(module_name: str, **attrs: object) -> None:
    if module_name in sys.modules:
        return
    try:
        spec = importlib.util.find_spec(module_name)
    except ModuleNotFoundError:
        spec = None
    if spec is not None:
        return
    module = types.ModuleType(module_name)
    for name, value in attrs.items():
        setattr(module, name, value)
    sys.modules[module_name] = module


_install_stub_if_missing("src.core.dedup", SignalDedup=SignalDedup)
_install_stub_if_missing("src.detectors.h1_peak_context", evaluate_h1_peak_context=lambda candles: None)
_install_stub_if_missing("src.data.market_gateway", MarketGateway=MarketGateway)

from src.core import signal_engine
from src import main as runtime_main


class _Dedup:
    def __init__(self) -> None:
        self.marked: list[str] = []
        self.duplicates: set[str] = set()

    def is_duplicate(self, key: str) -> bool:
        return key in self.duplicates

    def mark(self, key: str) -> None:
        self.marked.append(key)


def test_evaluate_symbol_can_check_dedup_without_marking() -> None:
    original_h1 = signal_engine.evaluate_h1_peak_context
    original_m15 = signal_engine.evaluate_m15_entry
    try:
        signal_engine.evaluate_h1_peak_context = lambda candles: SimpleNamespace(
            ok=True,
            impulse_up=True,
            rejection_candle=True,
            no_continuation=True,
            reason="ok",
        )
        signal_engine.evaluate_m15_entry = lambda candles: SimpleNamespace(
            ready=True,
            ema20_retest_fail=True,
            local_low_break=True,
            price_above_ema20_15m=False,
            entry_trigger=99.0,
            stop=101.0,
            reason="ok",
        )
        dedup = _Dedup()

        result = signal_engine.evaluate_symbol(
            "BTCUSDT",
            candles_1h=[{}],
            candles_15m=[{}],
            dedup=dedup,
            mark_dedup=False,
        )

        assert result.ready is True
        assert result.dedup_key
        assert dedup.marked == []
    finally:
        signal_engine.evaluate_h1_peak_context = original_h1
        signal_engine.evaluate_m15_entry = original_m15


def test_run_tick_marks_dedup_only_after_successful_telegram_send() -> None:
    original_evaluate_symbol = runtime_main.evaluate_symbol
    original_send_telegram = runtime_main._send_telegram
    try:
        def fake_evaluate_symbol(**kwargs):
            assert kwargs["mark_dedup"] is False
            return SimpleNamespace(
                ready=True,
                signal="H1_PEAK_TO_EMA_SHORT",
                score=90,
                entry_trigger=99.0,
                stop=101.0,
                reason_code="ok",
                dedup_key="BTCUSDT|SHORT|99|101",
            )

        class Gateway:
            def get_klines(self, symbol: str, interval: str, *, limit: int) -> list[dict]:
                return [{}]

        dedup = _Dedup()
        runtime_main.evaluate_symbol = fake_evaluate_symbol
        runtime_main._send_telegram = lambda token, chat_id, text: False

        runtime_main._run_tick(Gateway(), dedup, "BTCUSDT", "token", "chat")

        assert dedup.marked == []

        runtime_main._send_telegram = lambda token, chat_id, text: True
        runtime_main._run_tick(Gateway(), dedup, "BTCUSDT", "token", "chat")

        assert dedup.marked == ["BTCUSDT|SHORT|99|101"]
    finally:
        runtime_main.evaluate_symbol = original_evaluate_symbol
        runtime_main._send_telegram = original_send_telegram
