import os
import time
import urllib.parse
import urllib.request

from src.core.dedup import SignalDedup
from src.core.signal_engine import evaluate_symbol
from src.data.market_gateway import MarketGateway


def _env_float(name: str, default: float) -> float:
    try:
        return float(os.getenv(name, str(default)) or str(default))
    except (TypeError, ValueError):
        return default


def _env_int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, str(default)) or str(default))
    except (TypeError, ValueError):
        return default


def _symbols_from_env() -> list[str]:
    raw = os.getenv("SYMBOLS", "BTCUSDT").strip()
    out = [x.strip().upper() for x in raw.split(",") if x.strip()]
    return out or ["BTCUSDT"]


def _send_telegram(token: str, chat_id: str, text: str) -> bool:
    if not token or not chat_id or not text:
        return False
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = urllib.parse.urlencode(
        {
            "chat_id": chat_id,
            "text": text,
            "disable_web_page_preview": "true",
        }
    ).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=payload,
        method="POST",
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    try:
        with urllib.request.urlopen(req, timeout=12) as resp:
            return 200 <= int(resp.status) < 300
    except Exception:
        return False


def _format_telegram_signal(symbol: str, score: int, entry: float, stop: float, reason_code: str) -> str:
    return (
        f"🔴 H1_PEAK_TO_EMA_SHORT {symbol}\n"
        f"Score: {score}\n"
        f"Entry (sell stop): {entry:.6g}\n"
        f"Stop: {stop:.6g}\n"
        f"Reason: {reason_code}"
    )


def _run_tick(gw: MarketGateway, dedup: SignalDedup, symbol: str, tg_token: str, tg_chat_id: str) -> None:
    candles_1h = gw.get_klines(symbol, "1h", limit=80)
    candles_15m = gw.get_klines(symbol, "15m", limit=120)
    result = evaluate_symbol(
        symbol=symbol,
        candles_1h=candles_1h,
        candles_15m=candles_15m,
        dedup=dedup,
    )
    if result.ready:
        msg = _format_telegram_signal(
            symbol=symbol,
            score=result.score,
            entry=result.entry_trigger,
            stop=result.stop,
            reason_code=result.reason_code,
        )
        tg_ok = _send_telegram(tg_token, tg_chat_id, msg)
        if result.dedup_key and (tg_ok or not (tg_token and tg_chat_id)):
            dedup.mark(result.dedup_key)
        print(
            f"[SIGNAL] {result.signal} {symbol} score={result.score} "
            f"entry={result.entry_trigger:.6g} stop={result.stop:.6g} key={result.dedup_key} "
            f"tg={'ok' if tg_ok else 'fail'}",
            flush=True,
        )
    else:
        print(
            f"[SKIP] {symbol} reason={result.reason_code} score={result.score}",
            flush=True,
        )


def main() -> None:
    poll_sec = max(5, _env_int("POLL_SEC", 30))
    dedup_ttl = max(60.0, _env_float("DEDUP_TTL_SEC", 1800.0))
    universe_mode = (os.getenv("UNIVERSE_MODE", "dynamic") or "dynamic").strip().lower()
    symbols = _symbols_from_env()
    min_qv_24h = _env_float("UNIVERSE_MIN_QUOTE_VOL_24H", 5_000_000.0)
    max_symbols = max(1, _env_int("UNIVERSE_MAX_SYMBOLS", 120))
    refresh_sec = max(30, _env_int("UNIVERSE_REFRESH_SEC", 300))
    last_universe_refresh = 0.0
    tg_token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
    tg_chat_id = os.getenv("TELEGRAM_CHAT_ID", "").strip()

    gateway = MarketGateway(timeout_sec=_env_float("HTTP_TIMEOUT_SEC", 12.0))
    dedup = SignalDedup(ttl_sec=dedup_ttl)

    if universe_mode == "dynamic":
        dyn = gateway.get_dynamic_symbols(min_quote_volume_24h=min_qv_24h, max_symbols=max_symbols)
        if dyn:
            symbols = dyn

    print(
        f"[BOOT] peak_to_ema started | mode={universe_mode} | symbols={len(symbols)} "
        f"| poll={poll_sec}s | dedup_ttl={int(dedup_ttl)}s | tg={'on' if (tg_token and tg_chat_id) else 'off'}",
        flush=True,
    )
    while True:
        started = time.time()
        if universe_mode == "dynamic" and (started - last_universe_refresh) >= refresh_sec:
            dyn = gateway.get_dynamic_symbols(min_quote_volume_24h=min_qv_24h, max_symbols=max_symbols)
            if dyn:
                symbols = dyn
                last_universe_refresh = started
                print(
                    f"[UNIVERSE] dynamic refreshed: {len(symbols)} symbols "
                    f"(min_qv_24h={int(min_qv_24h)}, max={max_symbols})",
                    flush=True,
                )
        for symbol in symbols:
            try:
                _run_tick(gateway, dedup, symbol, tg_token, tg_chat_id)
            except Exception as exc:
                print(f"[ERROR] {symbol} tick failed: {exc}", flush=True)

        elapsed = time.time() - started
        sleep_for = max(1.0, poll_sec - elapsed)
        time.sleep(sleep_for)


if __name__ == "__main__":
    main()
