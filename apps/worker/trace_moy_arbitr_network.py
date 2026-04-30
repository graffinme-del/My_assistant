from __future__ import annotations

import argparse
import json
import re
import time
from pathlib import Path
from typing import Optional
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

from playwright.sync_api import sync_playwright


SENSITIVE_QUERY_KEYS = {
    "access_token",
    "auth",
    "authorization",
    "code",
    "id_token",
    "jwt",
    "password",
    "refresh_token",
    "session",
    "sid",
    "state",
    "token",
}
SENSITIVE_JSON_KEYS = re.compile(
    r'("(?:access_token|authorization|code|id_token|jwt|password|refresh_token|session|sid|token)"\s*:\s*)"[^"]*"',
    flags=re.IGNORECASE,
)
STATIC_EXTENSIONS = (
    ".css",
    ".gif",
    ".ico",
    ".jpg",
    ".jpeg",
    ".js",
    ".map",
    ".png",
    ".svg",
    ".ttf",
    ".webp",
    ".woff",
    ".woff2",
)


def redact_url(raw_url: str) -> str:
    try:
        parsed = urlparse(raw_url)
        query = []
        for key, value in parse_qsl(parsed.query, keep_blank_values=True):
            if key.lower() in SENSITIVE_QUERY_KEYS:
                query.append((key, "[REDACTED]"))
            else:
                query.append((key, value))
        return urlunparse(parsed._replace(query=urlencode(query, doseq=True)))
    except Exception:
        return raw_url


def redact_text(value: Optional[str], *, max_chars: int) -> str:
    if not value:
        return ""
    text = SENSITIVE_JSON_KEYS.sub(r'\1"[REDACTED]"', value)
    text = re.sub(r"Bearer\s+[A-Za-z0-9._~+/=-]+", "Bearer [REDACTED]", text, flags=re.IGNORECASE)
    return text[:max_chars]


def looks_static(url: str, resource_type: str) -> bool:
    low = urlparse(url).path.lower()
    if resource_type in {"font", "image", "media", "stylesheet"}:
        return True
    return low.endswith(STATIC_EXTENSIONS)


def is_interesting(url: str, resource_type: str, *, include_static: bool) -> bool:
    if include_static:
        return True
    if "google-analytics.com" in url or "googletagmanager.com" in url or "mc.yandex" in url:
        return False
    if looks_static(url, resource_type):
        return False
    return True


def append(events, item: dict) -> None:
    item["t"] = round(time.time(), 3)
    events.append(item)


def console_text(msg) -> str:
    try:
        value = msg.text
        if callable(value):
            value = value()
        return str(value)[:1000]
    except Exception as exc:
        return f"console_text_error={str(exc)[:200]}"


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Открыть «Мой Арбитр» в видимом Chromium, дать пользователю вручную выполнить поиск "
            "и сохранить network trace в JSON без cookies/секретных заголовков."
        )
    )
    parser.add_argument("--base-url", default="https://my.arbitr.ru", help="Адрес «Мой Арбитр».")
    parser.add_argument("--state", default="state.json", help="Playwright storage_state для входа/сохранения сессии.")
    parser.add_argument("--out", default="moy_arbitr_network_trace.json", help="Куда сохранить JSON-трассу.")
    parser.add_argument("--headless", action="store_true", help="Запустить без окна браузера (для диагностики, не для входа).")
    parser.add_argument("--include-static", action="store_true", help="Писать в trace также статику/картинки/шрифты.")
    parser.add_argument("--max-body-chars", type=int, default=4000, help="Максимум символов request/response body.")
    args = parser.parse_args()

    base_url = args.base_url.rstrip("/")
    state_path = Path(args.state)
    out_path = Path(args.out)
    events = []

    print("Открою браузер. Дальше вручную:")
    print("1) войдите в «Мой Арбитр», если вход не сохранён;")
    print("2) откройте «Мои дела» или нужный раздел;")
    print("3) выполните поиск по номеру дела/участнику;")
    print("4) дождитесь результата;")
    print("5) вернитесь в этот терминал и нажмите Enter.")
    print()
    print(f"Trace будет сохранён в: {out_path.resolve()}")
    print("В JSON не сохраняются cookies и заголовки Authorization, но там могут быть номера дел/ФИО из страницы.")

    with sync_playwright() as pw:
        browser = pw.chromium.launch(
            headless=args.headless,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--enable-unsafe-swiftshader",
                "--use-gl=swiftshader",
                "--ignore-gpu-blocklist",
            ],
        )
        context_kwargs = {
            "accept_downloads": True,
            "locale": "ru-RU",
            "viewport": {"width": 1440, "height": 950},
        }
        if state_path.exists() and state_path.stat().st_size > 20:
            context_kwargs["storage_state"] = str(state_path)
            print(f"Использую сохранённую сессию: {state_path.resolve()}")
        context = browser.new_context(**context_kwargs)
        page = context.new_page()

        def on_request(req) -> None:
            if not is_interesting(req.url, req.resource_type, include_static=args.include_static):
                return
            append(
                events,
                {
                    "type": "request",
                    "method": req.method,
                    "resource_type": req.resource_type,
                    "url": redact_url(req.url),
                    "post_data": redact_text(req.post_data, max_chars=args.max_body_chars),
                },
            )

        def on_response(resp) -> None:
            req = resp.request
            if not is_interesting(resp.url, req.resource_type, include_static=args.include_static):
                return
            item = {
                "type": "response",
                "status": resp.status,
                "resource_type": req.resource_type,
                "url": redact_url(resp.url),
                "content_type": resp.headers.get("content-type", ""),
            }
            if req.resource_type in {"fetch", "xhr"} or "json" in item["content_type"]:
                try:
                    item["body"] = redact_text(resp.text(), max_chars=args.max_body_chars)
                except Exception as exc:
                    item["body_error"] = str(exc)[:300]
            append(events, item)

        page.on("request", on_request)
        page.on("response", on_response)
        page.on(
            "requestfailed",
            lambda req: append(
                events,
                {
                    "type": "requestfailed",
                    "method": req.method,
                    "resource_type": req.resource_type,
                    "url": redact_url(req.url),
                    "failure": str(req.failure)[:500],
                },
            ),
        )
        page.on("console", lambda msg: append(events, {"type": f"console.{msg.type}", "text": console_text(msg)}))
        page.on("pageerror", lambda exc: append(events, {"type": "pageerror", "text": str(exc)[:1000]}))

        page.goto(base_url, wait_until="domcontentloaded", timeout=120_000)
        input("Когда вручную закончите поиск в браузере, нажмите Enter здесь...")

        state_path.parent.mkdir(parents=True, exist_ok=True)
        context.storage_state(path=str(state_path))
        out_path.write_text(json.dumps(events, ensure_ascii=False, indent=2), encoding="utf-8")
        browser.close()

    print(f"Готово: сохранено событий: {len(events)}")
    print(f"Trace: {out_path.resolve()}")
    print(f"Сессия: {state_path.resolve()}")


if __name__ == "__main__":
    main()
