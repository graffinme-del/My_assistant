from __future__ import annotations

import argparse
import json
import re
import time
from pathlib import Path
from typing import Optional
from urllib.parse import parse_qsl, unquote_plus, urlencode, urlparse, urlunparse

SENSITIVE_QUERY_KEYS = {
    "access_token",
    "auth",
    "authorization",
    "code",
    "id_token",
    "jwt",
    "password",
    # SAML / SSO transports can contain long-lived auth material in the URL query.
    "samlrequest",
    "samlpresponse",
    "samlresponse",
    "sigalg",
    "signature",
    "relaystate",
    "refresh_token",
    "session",
    "sessionid",
    "nameid",
    "sid",
    "state",
    "token",
}
SENSITIVE_FORM_KEYS = SENSITIVE_QUERY_KEYS | {
    "command",
    "login",
    "mobile",
    "otp",
    "samlresponse",
}
SENSITIVE_JSON_KEYS = re.compile(
    r'("(?:access_token|authorization|code|command|hash|id_token|jwt|login|mobile|otp|password|refresh_token|'
    r"samlrequest|samlresponse|session|sid|token)\"\s*:\s*)"  # SAML keys must be redacted even if JSON parse fails
    r'"[^"]*"',
    flags=re.IGNORECASE,
)
SENSITIVE_HEADER_KEYS = {
    "authorization",
    "cookie",
    "set-cookie",
    "location",
    "x-csrf-token",
    "x-xsrf-token",
}
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
            lk = key.lower()
            # URL keys are case-sensitive in theory, but gateways vary; normalize.
            if lk in SENSITIVE_QUERY_KEYS:
                query.append((key, "[REDACTED]"))
            else:
                query.append((key, value))
        return urlunparse(parsed._replace(query=urlencode(query, doseq=True)))
    except Exception:
        return raw_url


def redact_text(value: Optional[str], *, max_chars: int) -> str:
    if not value:
        return ""
    text = value
    try:
        pairs = parse_qsl(text, keep_blank_values=True)
        if pairs and urlencode(pairs, doseq=True):
            redacted_pairs = [
                (key, "[REDACTED]" if key.lower() in SENSITIVE_FORM_KEYS else val)
                for key, val in pairs
            ]
            text = urlencode(redacted_pairs, doseq=True)
    except Exception:
        pass
    text = SENSITIVE_JSON_KEYS.sub(r'\1"[REDACTED]"', text)
    text = redact_nested_json_structure(text)
    text = re.sub(r"Bearer\s+[A-Za-z0-9._~+/=-]+", "Bearer [REDACTED]", text, flags=re.IGNORECASE)
    return text[:max_chars]


def redact_headers(headers: dict[str, str]) -> dict[str, str]:
    redacted = {}
    for key, value in headers.items():
        lk = key.lower()
        if lk in SENSITIVE_HEADER_KEYS:
            if lk == "location":
                redacted[key] = redact_url(str(value))
            else:
                redacted[key] = "[REDACTED]"
        else:
            redacted[key] = value[:400]
    return redacted


def maybe_decode_wrapped_json(post_data: str) -> str:
    """
    Some endpoints send body like `%7B...%7D=` (URL-encoded JSON as a form key).
    Decode it to readable JSON-ish text for easier analysis.
    """
    def decode_wrapped(candidate: str) -> str | None:
        c = candidate.strip()
        if not c.endswith("="):
            return None
        key_only = c[:-1].lstrip("&")
        dec = unquote_plus(key_only).strip()
        if dec.startswith("{") or dec.startswith("["):
            return dec
        return None

    try:
        pairs = parse_qsl(post_data, keep_blank_values=True)
        # Case 1: `{"...": ...}=` shipped as www-form-urlencoded "key-only" blob.
        if len(pairs) == 1 and pairs[0][1] == "":
            candidate = unquote_plus(pairs[0][0]).strip()
            if candidate.startswith("{") or candidate.startswith("["):
                return candidate
        # JWT fields inside JSON may include '=' padding, which breaks parse_qsl across the entire payload.
        wrapped = decode_wrapped(post_data)
        if wrapped is not None:
            return wrapped
    except Exception:
        wrapped = decode_wrapped(post_data)
        if wrapped is not None:
            return wrapped
    return post_data


_SENSITIVE_JSON_OBJECT_KEYS_LOWER = frozenset(
    {
        "access_token",
        "authorization",
        "code",
        "command",
        # KAD stamps PDF previews with one-time-ish proof fields.
        "hash",
        "id_token",
        "jwt",
        "login",
        "mobile",
        "otp",
        "password",
        "refresh_token",
        "session",
        "sid",
        "token",
        "samlresponse",
        "relaystate",
    }
)


def redact_json_value(value: object) -> object:
    """Recursively drop secrets from parsed JSON payloads."""
    if isinstance(value, dict):
        redacted_dict: dict = {}
        for k, v in value.items():
            key = str(k)
            lk = key.lower().replace("-", "").replace("_", "")
            if lk in {"samlresponse", "relaystate"} or key.lower() in _SENSITIVE_JSON_OBJECT_KEYS_LOWER:
                redacted_dict[key] = "[REDACTED]"
            else:
                redacted_dict[key] = redact_json_value(v)
        return redacted_dict
    if isinstance(value, list):
        return [redact_json_value(v) for v in value]
    if isinstance(value, str):
        s = redact_sensitive_json_literals(value)
        s = SENSITIVE_JSON_KEYS.sub(r'\1"[REDACTED]"', s)
        return s
    return value


def redact_sensitive_json_literals(text: str) -> str:
    """
    Fallback when JSON parsing cannot be relied on:
    catches `"password": "secret"` variants with lax spacing.
    """
    pattern = re.compile(
        r'(?P<head>"(?:access_token|authorization|code|command|hash|id_token|jwt|login|mobile|otp|password|refresh_token|'
        r"session|sid|token|samlresponse|relaystate)\""
        r"\s*:\s*)"
        r'(?P<val>"([^"\\]|\\.)*"|[^,}\]\s]\S*)',
        flags=re.IGNORECASE,
    )
    return pattern.sub(r'\g<head>"[REDACTED]"', text)


def redact_nested_json_structure(text: str) -> str:
    """
    Prefer structural redaction via json.loads/json.dumps after redact_json_value().
    Keeps readability for analysis traces without leaking passwords/tokens accidentally.
    """
    s = text.strip()
    try:
        if s.startswith("{") or s.startswith("["):
            obj = json.loads(s)
            return json.dumps(redact_json_value(obj), ensure_ascii=False)
    except Exception:
        pass
    return redact_sensitive_json_literals(text)


_SAML_MARKER = re.compile(r"saml(?:response|request)|samlp|[%]22saml(?:response|request)", flags=re.IGNORECASE)


def extract_post_payload(req, *, max_chars: int) -> str:
    try:
        payload_json = req.post_data_json
        if payload_json is not None:
            return redact_text(json.dumps(payload_json, ensure_ascii=False), max_chars=max_chars)
    except Exception:
        pass
    raw_full = req.post_data or ""
    # SAML/XML blobs can defeat json.loads(); never truncate raw bodies before structured redaction.
    if _SAML_MARKER.search(raw_full):
        dec = maybe_decode_wrapped_json(raw_full)
        try:
            if dec.startswith("{") or dec.startswith("["):
                obj = json.loads(dec)
                return redact_text(json.dumps(redact_json_value(obj), ensure_ascii=False), max_chars=max_chars)
        except Exception:
            pass
        return '{"_trace_note":"POST contained SAML/sso payload; stripped before save"}'

    return redact_text(maybe_decode_wrapped_json(raw_full), max_chars=max_chars)


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
    from playwright.sync_api import sync_playwright

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
    parser.add_argument(
        "--drain-seconds",
        type=float,
        default=3.0,
        help="Подождать N секунд после Enter, чтобы дочитать поздние response body.",
    )
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
    print("Подсказка: на kad.arbitr.ru карточка дела часто открывается в НОВОЙ вкладке — это нормально,")
    print("          trace пишет сеть со всех вкладок этого окна. Не закрывайте вкладку с делом до Enter.")
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
        _wired_page_ids: set[int] = set()

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
                    "headers": redact_headers(req.headers),
                    "post_data": extract_post_payload(req, max_chars=args.max_body_chars),
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
                "headers": redact_headers(resp.headers),
            }
            if req.resource_type in {"fetch", "xhr"} or "json" in item["content_type"]:
                try:
                    item["body"] = redact_text(resp.text(), max_chars=args.max_body_chars)
                except Exception as exc:
                    item["body_error"] = str(exc)[:300]
            append(events, item)

        def on_request_failed(req) -> None:
            append(
                events,
                {
                    "type": "requestfailed",
                    "method": req.method,
                    "resource_type": req.resource_type,
                    "url": redact_url(req.url),
                    "failure": str(req.failure)[:500],
                },
            )

        def wire_page(pg) -> None:
            # context.on("page") can fire twice for the same Page in edge cases — avoid duplicated events.
            pid = id(pg)
            if pid in _wired_page_ids:
                return
            _wired_page_ids.add(pid)
            pg.on("request", on_request)
            pg.on("response", on_response)
            pg.on("requestfailed", on_request_failed)
            pg.on("console", lambda msg: append(events, {"type": f"console.{msg.type}", "text": console_text(msg)}))
            pg.on("pageerror", lambda exc: append(events, {"type": "pageerror", "text": str(exc)[:1000]}))

        wire_page(page)
        context.on("page", wire_page)

        page.goto(base_url, wait_until="domcontentloaded", timeout=120_000)
        input("Когда вручную закончите поиск в браузере, нажмите Enter здесь...")
        # Give late XHR/fetch responses a chance to finish across all tabs before closing context.
        if args.drain_seconds > 0:
            for pg in list(context.pages):
                try:
                    pg.wait_for_load_state("networkidle", timeout=min(5000, max(2000, int(args.drain_seconds * 1000))))
                except Exception:
                    pass
            time.sleep(args.drain_seconds)

        state_path.parent.mkdir(parents=True, exist_ok=True)
        context.storage_state(path=str(state_path))
        out_path.write_text(json.dumps(events, ensure_ascii=False, indent=2), encoding="utf-8")
        browser.close()

    print(f"Готово: сохранено событий: {len(events)}")
    print(f"Trace: {out_path.resolve()}")
    print(f"Сессия: {state_path.resolve()}")


if __name__ == "__main__":
    main()
