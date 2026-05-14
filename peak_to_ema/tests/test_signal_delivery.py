import importlib
import sys
import types
from dataclasses import dataclass


class FakeDedup:
    def __init__(self) -> None:
        self.keys: set[str] = set()

    def is_duplicate(self, key: str) -> bool:
        return key in self.keys

    def mark(self, key: str) -> None:
        self.keys.add(key)


@dataclass
class FakeSignalResult:
    symbol: str = "BTCUSDT"
    signal: str = "H1_PEAK_TO_EMA_SHORT"
    score: int = 75
    ready: bool = True
    reason_code: str = "ok"
    entry_trigger: float = 100.0
    stop: float = 105.0
    dedup_key: str = "BTCUSDT|SHORT|100|105"


class FakeGateway:
    def get_klines(self, symbol: str, interval: str, limit: int) -> list[dict]:
        return []


def _install_import_stubs(monkeypatch) -> None:
    dedup_mod = types.ModuleType("src.core.dedup")
    dedup_mod.SignalDedup = FakeDedup
    monkeypatch.setitem(sys.modules, "src.core.dedup", dedup_mod)

    h1_mod = types.ModuleType("src.detectors.h1_peak_context")
    h1_mod.evaluate_h1_peak_context = lambda candles: None
    monkeypatch.setitem(sys.modules, "src.detectors.h1_peak_context", h1_mod)

    gateway_mod = types.ModuleType("src.data.market_gateway")
    gateway_mod.MarketGateway = FakeGateway
    monkeypatch.setitem(sys.modules, "src.data.market_gateway", gateway_mod)


def test_failed_telegram_send_does_not_consume_dedup_key(monkeypatch) -> None:
    _install_import_stubs(monkeypatch)
    main_mod = importlib.import_module("src.main")

    dedup = FakeDedup()
    sends: list[str] = []

    def fake_evaluate_symbol(**kwargs) -> FakeSignalResult:
        if kwargs["dedup"].is_duplicate("BTCUSDT|SHORT|100|105"):
            return FakeSignalResult(ready=False, reason_code="duplicate_signal")
        return FakeSignalResult()

    def failed_send(token: str, chat_id: str, text: str) -> bool:
        sends.append(text)
        return False

    monkeypatch.setattr(main_mod, "evaluate_symbol", fake_evaluate_symbol)
    monkeypatch.setattr(main_mod, "_send_telegram", failed_send)

    main_mod._run_tick(FakeGateway(), dedup, "BTCUSDT", "token", "chat")

    assert sends
    assert not dedup.is_duplicate("BTCUSDT|SHORT|100|105")


def test_successful_telegram_send_marks_dedup_key(monkeypatch) -> None:
    _install_import_stubs(monkeypatch)
    main_mod = importlib.import_module("src.main")

    dedup = FakeDedup()
    monkeypatch.setattr(main_mod, "evaluate_symbol", lambda **kwargs: FakeSignalResult())
    monkeypatch.setattr(main_mod, "_send_telegram", lambda token, chat_id, text: True)

    main_mod._run_tick(FakeGateway(), dedup, "BTCUSDT", "token", "chat")

    assert dedup.is_duplicate("BTCUSDT|SHORT|100|105")
