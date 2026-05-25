from src.core.dedup import SignalDedup
from src.core.signal_engine import SignalResult


class FakeGateway:
    def get_klines(self, symbol: str, interval: str, limit: int = 120) -> list[dict]:
        return [{"close": 1.0}]


def test_run_tick_marks_dedup_only_after_successful_telegram_send() -> None:
    import src.main as main

    dedup = SignalDedup(ttl_sec=60)
    result = SignalResult(
        symbol="BTCUSDT",
        signal="H1_PEAK_TO_EMA_SHORT",
        score=90,
        ready=True,
        reason_code="ok",
        entry_trigger=99.0,
        stop=101.0,
        dedup_key="BTCUSDT|SHORT|99|101",
    )

    original_evaluate_symbol = main.evaluate_symbol
    original_send_telegram = main._send_telegram
    try:
        main.evaluate_symbol = lambda **kwargs: result
        main._send_telegram = lambda token, chat_id, text: False

        main._run_tick(FakeGateway(), dedup, "BTCUSDT", "token", "chat")
        assert dedup.is_duplicate(result.dedup_key) is False

        main._send_telegram = lambda token, chat_id, text: True
        main._run_tick(FakeGateway(), dedup, "BTCUSDT", "token", "chat")
        assert dedup.is_duplicate(result.dedup_key) is True
    finally:
        main.evaluate_symbol = original_evaluate_symbol
        main._send_telegram = original_send_telegram
