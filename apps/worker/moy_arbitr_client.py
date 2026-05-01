from __future__ import annotations

import json
import os
import re
import tempfile
import time
from pathlib import Path
from urllib.parse import quote_plus, urljoin

from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
from playwright.sync_api import sync_playwright


DEFAULT_BASE_URL = "https://my.arbitr.ru"
MOY_ARBITR_BASE_URL = (os.getenv("MOY_ARBITR_BASE_URL") or DEFAULT_BASE_URL).rstrip("/")
MOY_ARBITR_STATE_PATH = os.getenv("MOY_ARBITR_STATE_PATH", "/app/moy_arbitr/state.json")
MOY_ARBITR_HEADLESS = os.getenv("MOY_ARBITR_HEADLESS", "true").lower() not in ("0", "false", "no")
MOY_ARBITR_TIMEOUT_SEC = int(os.getenv("MOY_ARBITR_TIMEOUT_SEC", "120"))
MOY_ARBITR_MAX_CASES = max(1, int(os.getenv("MOY_ARBITR_MAX_CASES", "25")))
MOY_ARBITR_MAX_DOCS_PER_CASE = max(1, int(os.getenv("MOY_ARBITR_MAX_DOCS_PER_CASE", "80")))
MOY_ARBITR_MANUAL_LOGIN_URL = os.getenv("MOY_ARBITR_MANUAL_LOGIN_URL", f"{MOY_ARBITR_BASE_URL}/")
MOY_ARBITR_DEBUG_DIR = os.getenv("MOY_ARBITR_DEBUG_DIR", "/app/moy_arbitr/debug")

MOY_ARBITR_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36"
)
MOY_ARBITR_CHROMIUM_ARGS = [
    "--disable-blink-features=AutomationControlled",
    # Chromium 140+ no longer falls back to software WebGL unless this is explicit.
    # my.arbitr.ru currently renders a blank SPA shell without WebGL in our headless container.
    "--enable-unsafe-swiftshader",
    "--use-gl=swiftshader",
    "--ignore-gpu-blocklist",
]


class MoyArbitrAuthRequired(RuntimeError):
    pass


class MoyArbitrNoResults(RuntimeError):
    pass


LAST_SEARCH_DIAGNOSTIC = ""
LAST_BROWSER_EVENTS: list[str] = []


def last_search_diagnostics() -> str:
    return LAST_SEARCH_DIAGNOSTIC


def _remember_browser_event(kind: str, message: str) -> None:
    if len(LAST_BROWSER_EVENTS) >= 80:
        return
    clean = re.sub(r"\s+", " ", message or "").strip()
    if clean:
        LAST_BROWSER_EVENTS.append(f"{kind}: {clean[:500]}")


def _safe_debug_part(value: str) -> str:
    s = re.sub(r"[^\w.\-]+", "_", value or "", flags=re.IGNORECASE).strip("_")
    return s[:80] or "query"


def _save_debug_artifacts(page, *, job_id: int | None, query_type: str, query_value: str) -> str:
    debug_dir = Path(MOY_ARBITR_DEBUG_DIR)
    debug_dir.mkdir(parents=True, exist_ok=True)
    stamp = time.strftime("%Y%m%d-%H%M%S")
    prefix = f"job-{job_id or 'manual'}-{_safe_debug_part(query_type)}-{_safe_debug_part(query_value)}-{stamp}"
    html_path = debug_dir / f"{prefix}.html"
    png_path = debug_dir / f"{prefix}.png"
    log_path = debug_dir / f"{prefix}.log"
    saved: list[str] = []
    try:
        html_path.write_text(page.content(), encoding="utf-8")
        saved.append(str(html_path))
    except Exception as exc:
        saved.append(f"html_error={str(exc)[:160]}")
    try:
        page.screenshot(path=str(png_path), full_page=True, timeout=15000)
        saved.append(str(png_path))
    except Exception as exc:
        saved.append(f"screenshot_error={str(exc)[:160]}")
    try:
        log_path.write_text("\n".join(LAST_BROWSER_EVENTS[-80:]), encoding="utf-8")
        saved.append(str(log_path))
    except Exception as exc:
        saved.append(f"log_error={str(exc)[:160]}")
    return "debug_artifacts=" + ", ".join(saved)


def _attach_browser_diagnostics(page) -> None:
    page.on("console", lambda msg: _remember_browser_event(f"console.{msg.type}", msg.text))
    page.on("pageerror", lambda exc: _remember_browser_event("pageerror", str(exc)))
    page.on("requestfailed", lambda req: _remember_browser_event("requestfailed", f"{req.url} {req.failure}"))

    def _response(resp) -> None:
        try:
            if resp.status >= 400:
                _remember_browser_event("http", f"{resp.status} {resp.url}")
        except Exception:
            return

    page.on("response", _response)


def state_file_exists() -> bool:
    p = Path(MOY_ARBITR_STATE_PATH)
    return p.exists() and p.stat().st_size > 20


def _query_type_without_prefix(query_type: str) -> str:
    return (query_type or "").removeprefix("moy_arbitr_")


def _normalize_subscription_case_label(s: str) -> str:
    """Сравниваем номер дела с полем Filter в подписках (латиница А / кириллица А)."""
    t = re.sub(r"\s+", "", (s or "")).strip().upper()
    return t.replace("A", "А")


def _case_numbers_normalized_in_blob(blob: str) -> set[str]:
    """Все номероподобные фрагменты из текста/HTML/JSON строки строки подписки."""
    compact = re.sub(r"\s+", "", blob or "")
    out: set[str] = set()
    for m in re.finditer(r"[АA]\d{1,4}-\d{1,7}/\d{2,4}", compact, flags=re.IGNORECASE):
        norm = _normalize_subscription_case_label(m.group(0))
        if norm:
            out.add(norm)
    return out


def _moy_arbitr_xhr_headers() -> dict[str, str]:
    return {
        "Accept": "application/json, text/javascript, */*; q=0.01",
        "Content-Type": "application/json",
        "Origin": MOY_ARBITR_BASE_URL,
        "X-Requested-With": "XMLHttpRequest",
        "X-Date-Format": "iso",
        "Referer": f"{MOY_ARBITR_BASE_URL}/",
    }


def _subscriptions_api_find_case(context, query_value: str) -> list[dict]:
    """
    Если SPA не отдало поля поиска, пробуем тот же XHR, что и сайт:
    POST /Guard/Subscriptions — там есть номер из подписки и CaseId (КАД).
    Работает только для уже отслеживаемых дел.
    """
    want = _normalize_subscription_case_label(query_value)
    if not want:
        return []
    url = f"{MOY_ARBITR_BASE_URL}/Guard/Subscriptions"
    try:
        resp = context.request.post(
            url,
            headers=_moy_arbitr_xhr_headers(),
            data=json.dumps({"newFirst": True}),
            timeout=max(45_000, MOY_ARBITR_TIMEOUT_SEC * 1000),
        )
        if not resp.ok:
            return []
        data = resp.json()
    except Exception:
        return []
    if not data.get("Success"):
        return []
    basket = (((data.get("Result") or {}) if isinstance(data.get("Result"), dict) else {}) or {}).get("Items") or []
    out: list[dict] = []
    seen: set[str] = set()
    for row in basket:
        if not isinstance(row, dict):
            continue
        extras = row.get("AdditionalFields") if isinstance(row.get("AdditionalFields"), dict) else {}
        cid = str(extras.get("CaseId") or "").strip()
        if not cid:
            continue
        try:
            row_blob = json.dumps(row, ensure_ascii=False)
        except Exception:
            row_blob = str(row)
        nums = _case_numbers_normalized_in_blob(row_blob)
        if want not in nums:
            filt_only = _normalize_subscription_case_label(str(row.get("Filter") or ""))
            if filt_only != want:
                continue
        kad_url = f"https://kad.arbitr.ru/Card/{cid}"
        if kad_url in seen:
            continue
        seen.add(kad_url)
        raw_num = (
            str(row.get("Filter") or "").replace(" ", "")
            or next(
                (
                    m.group(0).replace(" ", "")
                    for m in re.finditer(r"[АA]\d{1,4}-\d{1,7}/\d{2,4}", row_blob, flags=re.IGNORECASE)
                    if _normalize_subscription_case_label(m.group(0)) == want
                ),
                "",
            )
            or query_value.replace(" ", "")
        )
        out.append(
            {
                "remote_case_id": f"moy-arbitr:{cid}"[:255],
                "source_system": "moy_arbitr",
                "card_url": kad_url,
                "case_number": raw_num[:64],
                "title": raw_num[:255],
                "court_name": "",
                "participants": [],
            }
        )
        if len(out) >= MOY_ARBITR_MAX_CASES:
            break
    return out


def _search_url(query_type: str, query_value: str) -> str:
    """Best-effort deep link; my.arbitr.ru may still route to its SPA search UI."""
    qv = quote_plus(query_value or "")
    qt = _query_type_without_prefix(query_type)
    if qt == "case_number":
        return f"{MOY_ARBITR_BASE_URL}/#/cases/my?caseNumber={qv}"
    if qt in ("inn", "ogrn"):
        return f"{MOY_ARBITR_BASE_URL}/#/cases/my?participant={qv}"
    return f"{MOY_ARBITR_BASE_URL}/#/cases/my?participant={qv}"


def _new_context(browser):
    kwargs = {
        "accept_downloads": True,
        "user_agent": MOY_ARBITR_USER_AGENT,
        "locale": "ru-RU",
        "viewport": {"width": 1440, "height": 950},
    }
    if state_file_exists():
        kwargs["storage_state"] = MOY_ARBITR_STATE_PATH
    return browser.new_context(**kwargs)


def _page_looks_unauthorized(page) -> bool:
    url = (page.url or "").lower()
    if any(x in url for x in ("esia", "login", "auth", "sso")):
        return True
    try:
        text = page.locator("body").inner_text(timeout=3000).casefold()[:12000]
    except Exception:
        return False
    return any(
        marker in text
        for marker in (
            "войти в систему",
            "госуслуг",
            "авторизуйтесь",
            "авторизация",
            "личный кабинет",
        )
    ) and not any(marker in text for marker in ("мои дела", "отслеживаемые дела", "документы по делам"))


def ensure_authorized(page) -> None:
    if not state_file_exists():
        raise MoyArbitrAuthRequired(_manual_login_message("не найден файл сохранённой браузерной сессии"))
    if _page_looks_unauthorized(page):
        raise MoyArbitrAuthRequired(_manual_login_message("сессия «Мой Арбитр» отсутствует или истекла"))


def _manual_login_message(reason: str) -> str:
    return (
        f"{reason}. Нужно один раз выполнить вход в «Мой Арбитр» в браузерной сессии Playwright "
        f"и сохранить storage_state в {MOY_ARBITR_STATE_PATH}. "
        f"Откройте {MOY_ARBITR_MANUAL_LOGIN_URL}, войдите через Госуслуги/КЭП, затем сохраните state.json. "
        "Пароль и ключи УКЭП в приложении не хранятся."
    )


def _dismiss_common_overlays(page) -> None:
    for pattern in (r"Принять", r"Согласен", r"Понятно", r"Закрыть", r"OK"):
        try:
            btn = page.get_by_role("button", name=re.compile(pattern, re.IGNORECASE)).first
            if btn.is_visible(timeout=600):
                btn.click(timeout=2500)
                page.wait_for_timeout(400)
        except Exception:
            continue


def _fill_contenteditable_search(page, value: str) -> bool:
    for sel in ("[contenteditable='true']", "[contenteditable=true]"):
        try:
            loc = page.locator(sel).first
            if loc.is_visible(timeout=800):
                loc.click(timeout=1000)
                loc.fill("")  # may not support fill on all libs
                try:
                    loc.fill(value, timeout=3000)
                except Exception:
                    page.keyboard.press("Control+a")
                    page.keyboard.type(value, delay=20)
                return True
        except Exception:
            continue
    return False


def _wait_for_case_number_visible(page, query_value: str, timeout_ms: int) -> bool:
    """SPA иногда ставит фильтр по query-параметру без поля ввода — ждём номер в DOM."""
    want = _normalize_subscription_case_label(query_value)
    if not want:
        return False
    deadline = time.time() + max(1500, timeout_ms) / 1000.0
    while time.time() < deadline:
        try:
            blob = page.locator("body").inner_text(timeout=2500)
        except Exception:
            blob = ""
        if want in _case_numbers_normalized_in_blob(blob):
            return True
        page.wait_for_timeout(450)
    return False


def _fill_fallback_visible_inputs(page, value: str) -> bool:
    """SPA часто без label/placeholder — перебираем видимые поля."""
    try:
        loc = page.locator("input:visible")
        n = min(loc.count(), 50)
        for idx in range(n):
            inp = loc.nth(idx)
            try:
                t = (inp.get_attribute("type") or "").lower()
                if t in ("checkbox", "radio", "hidden", "submit", "button", "file", "image"):
                    continue
                if inp.is_visible(timeout=400):
                    inp.fill("", timeout=500)
                    inp.fill(value, timeout=4500)
                    return True
            except Exception:
                continue
    except Exception:
        pass
    return False


def _fill_first_matching_input(page, value: str, patterns: tuple[str, ...]) -> bool:
    candidates = []
    for p in patterns:
        rx = re.compile(p, re.IGNORECASE)
        candidates.extend(
            [
                page.get_by_placeholder(rx).first,
                page.get_by_label(rx).first,
                page.locator("input").filter(has_text=rx).first,
            ]
        )
    candidates.extend(
        [
            page.get_by_role("searchbox").first,
            page.get_by_role("textbox").first,
            page.locator("input[type='search']").first,
            page.locator("input[type='text']").first,
            page.locator("input:not([type='hidden'])").first,
            page.locator("input").first,
        ]
    )
    for loc in candidates:
        try:
            if loc.is_visible(timeout=1500):
                loc.fill("", timeout=500)
                loc.fill(value, timeout=4000)
                return True
        except Exception:
            continue
    if _fill_contenteditable_search(page, value):
        return True
    return _fill_fallback_visible_inputs(page, value)


def _click_search(page) -> None:
    for loc in (
        page.get_by_role("button", name=re.compile(r"Найти|Поиск|Искать", re.IGNORECASE)).first,
        page.locator("button:has-text('Найти')").first,
        page.locator("button:has-text('Поиск')").first,
        page.locator("input[type='submit']").first,
    ):
        try:
            if loc.is_visible(timeout=1500):
                loc.click(timeout=5000)
                return
        except Exception:
            continue
    try:
        page.keyboard.press("Enter")
    except Exception:
        pass


def _drive_search_form(page, query_type: str, query_value: str, nav_ms: int) -> None:
    global LAST_SEARCH_DIAGNOSTIC
    page.goto(_search_url(query_type, query_value), wait_until="domcontentloaded", timeout=nav_ms)
    page.wait_for_timeout(4500)
    try:
        page.wait_for_load_state("networkidle", timeout=min(nav_ms, 25000))
    except PlaywrightTimeoutError:
        pass
    page.wait_for_timeout(2500)
    ensure_authorized(page)
    _dismiss_common_overlays(page)
    for _sel_try in ("input:visible", "input[type=text]:visible", "[role=combobox]", "textarea:visible"):
        try:
            page.wait_for_selector(_sel_try, state="visible", timeout=14000)
            break
        except PlaywrightTimeoutError:
            continue
    qt = _query_type_without_prefix(query_type)
    if qt == "case_number":
        patterns = (
            r"номер.*дел",
            r"дело",
            r"case",
            r"поиск",
            r"найти.*дел",
            r"фильтр",
        )
    elif qt in ("inn", "ogrn"):
        patterns = (qt, r"участник", r"инн|огрн", r"наименование")
    else:
        patterns = (r"участник", r"наименование", r"фио", r"организац")
    filled = _fill_first_matching_input(page, query_value, patterns)
    if not filled:
        for label in ("Мои дела", "Отслеживаемые дела", "Картотека дел"):
            try:
                page.get_by_text(label, exact=False).first.click(timeout=2500)
                page.wait_for_timeout(1200)
                filled = _fill_first_matching_input(page, query_value, patterns)
                if filled:
                    break
            except Exception:
                continue
    spa_filter_visible = False
    if qt == "case_number" and (query_value or "").strip() and not filled:
        spa_filter_visible = _wait_for_case_number_visible(page, query_value, timeout_ms=min(nav_ms, 35_000))
    LAST_SEARCH_DIAGNOSTIC = f"url={page.url}; input_found={filled}; spa_case_visible={spa_filter_visible}"
    if filled:
        _click_search(page)
    page.wait_for_timeout(3500)
    try:
        page.wait_for_load_state("networkidle", timeout=min(nav_ms, 30000))
    except PlaywrightTimeoutError:
        pass
    page.wait_for_timeout(1500)


def _extract_case_results(page) -> list[dict]:
    seen: set[str] = set()
    out: list[dict] = []

    def add(url: str, text: str) -> None:
        full = urljoin(MOY_ARBITR_BASE_URL, url).rstrip("/")
        if not full.startswith("http") or full in seen:
            return
        if "my.arbitr.ru" not in full and "kad.arbitr.ru" not in full:
            return
        seen.add(full)
        num_match = re.search(r"([АA]\d{1,4}-\d{1,7}/\d{2,4}|\d{1,2}-\d{1,7}/\d{2,4})", text or full)
        rid = full.rstrip("/").split("/")[-1] or full
        out.append(
            {
                "remote_case_id": f"moy-arbitr:{rid}"[:255],
                "source_system": "moy_arbitr",
                "card_url": full,
                "case_number": num_match.group(1).replace(" ", "") if num_match else "",
                "title": (text or full)[:255],
                "court_name": "",
                "participants": [],
            }
        )

    for frame in page.frames:
        try:
            links = frame.locator("a")
            n = min(links.count(), 500)
        except Exception:
            continue
        for idx in range(n):
            try:
                a = links.nth(idx)
                href = (a.get_attribute("href") or "").strip()
                text = (a.inner_text() or "").strip()
            except Exception:
                continue
            if not href:
                continue
            low = href.lower()
            if any(k in low for k in ("/case", "kad.arbitr.ru/card", "card/", "document")) or re.search(
                r"[АA]\d{1,4}-\d{1,7}/\d{2,4}", text
            ):
                add(href, text)
            if len(out) >= MOY_ARBITR_MAX_CASES:
                return out

    if not out:
        try:
            html = page.content()
        except Exception:
            html = ""
        for m in re.finditer(r"([АA]\d{1,4}-\d{1,7}/\d{2,4})", html, flags=re.IGNORECASE):
            num = m.group(1).replace(" ", "")
            if num in seen:
                continue
            seen.add(num)
            out.append(
                {
                    "remote_case_id": f"moy-arbitr:{num}",
                    "source_system": "moy_arbitr",
                    "card_url": page.url,
                    "case_number": num,
                    "title": f"Дело {num}",
                    "court_name": "",
                    "participants": [],
                }
            )
            if len(out) >= MOY_ARBITR_MAX_CASES:
                break
    return out


def search_moy_arbitr_cases(query_type: str, query_value: str, job_id: int | None = None, progress=None) -> list[dict]:
    global LAST_BROWSER_EVENTS, LAST_SEARCH_DIAGNOSTIC
    LAST_SEARCH_DIAGNOSTIC = ""
    LAST_BROWSER_EVENTS = []
    nav_ms = max(60_000, MOY_ARBITR_TIMEOUT_SEC * 1000)
    with sync_playwright() as pw:
        browser = pw.chromium.launch(
            headless=MOY_ARBITR_HEADLESS,
            args=MOY_ARBITR_CHROMIUM_ARGS,
        )
        try:
            context = _new_context(browser)
            if progress and job_id is not None:
                progress(job_id, "searching", f"Мой Арбитр: поиск {query_type}={query_value}")

            qt_short = _query_type_without_prefix(query_type)
            if qt_short == "case_number" and (query_value or "").strip():
                subs_first = _subscriptions_api_find_case(context, query_value)
                if subs_first:
                    LAST_SEARCH_DIAGNOSTIC = f"subscriptions_api_early=len={len(subs_first)}"
                    return subs_first

            page = context.new_page()
            _attach_browser_diagnostics(page)
            _drive_search_form(page, query_type, query_value, nav_ms)
            results = _extract_case_results(page)
            if not results and qt_short == "case_number" and (query_value or "").strip():
                subs = _subscriptions_api_find_case(context, query_value)
                if subs:
                    results = subs
                    LAST_SEARCH_DIAGNOSTIC = (
                        f"{LAST_SEARCH_DIAGNOSTIC}; subscriptions_api=len={len(subs)}"
                    )
            if not results and _page_looks_unauthorized(page):
                raise MoyArbitrAuthRequired(_manual_login_message("сессия «Мой Арбитр» истекла"))
            if not results:
                try:
                    text = page.locator("body").inner_text(timeout=2500)
                    snippet = re.sub(r"\s+", " ", text).strip()[:500]
                except Exception:
                    snippet = ""
                artifacts = _save_debug_artifacts(
                    page,
                    job_id=job_id,
                    query_type=query_type,
                    query_value=query_value,
                )
                LAST_SEARCH_DIAGNOSTIC = (
                    (LAST_SEARCH_DIAGNOSTIC + "; " if LAST_SEARCH_DIAGNOSTIC else "")
                    + f"results=0; page_text={snippet}; {artifacts}"
                )
            return results
        finally:
            browser.close()


def _href_looks_like_document(href: str, text: str = "") -> bool:
    h = (href or "").lower()
    t = (text or "").casefold()
    if not href or href.startswith("#") or h.startswith("javascript:"):
        return False
    if re.search(r"\.(png|jpg|jpeg|gif|svg|css|js|woff2?)(\?|$|#)", h):
        return False
    return any(
        marker in h or marker in t
        for marker in (
            "download",
            "document",
            "file",
            "attachment",
            "pdf",
            "doc",
            "документ",
            "скач",
            "заявлен",
            "ходатай",
            "отзыв",
            "жалоб",
            "приложен",
        )
    )


def collect_moy_arbitr_documents(page, case_url: str) -> list[dict]:
    seen: set[str] = set()
    docs: list[dict] = []
    for label in ("Документы", "Материалы", "Приложения", "Файлы", "Поданные документы", "История"):
        try:
            page.get_by_text(label, exact=False).first.click(timeout=2500)
            page.wait_for_timeout(1200)
        except Exception:
            continue
    for frame in page.frames:
        try:
            anchors = frame.locator("a")
            n = min(anchors.count(), 800)
        except Exception:
            continue
        for idx in range(n):
            try:
                a = anchors.nth(idx)
                href = (a.get_attribute("href") or "").strip()
                text = (a.inner_text() or "").strip()
            except Exception:
                continue
            if not _href_looks_like_document(href, text):
                continue
            full = urljoin(case_url or MOY_ARBITR_BASE_URL, href)
            if full in seen:
                continue
            seen.add(full)
            docs.append(
                {
                    "remote_document_id": f"moy-arbitr:{full}"[:500],
                    "title": text[:500] or full,
                    "filename": "",
                    "file_url": full,
                }
            )
            if len(docs) >= MOY_ARBITR_MAX_DOCS_PER_CASE:
                return docs
    return docs


def download_moy_arbitr_document(context, file_url: str) -> Path:
    if "kad.arbitr.ru" in (file_url or "").lower():
        import worker as worker_mod

        return worker_mod.download_document_via_context(context, file_url)

    response = context.request.get(file_url, timeout=max(30_000, MOY_ARBITR_TIMEOUT_SEC * 1000))
    if not response.ok:
        raise RuntimeError(f"Мой Арбитр: не удалось скачать файл: HTTP {response.status}")
    body = response.body()
    if not body:
        raise RuntimeError("Мой Арбитр: пустой ответ вместо файла")
    ctype = (response.headers.get("content-type") or "").split(";")[0].lower()
    head = body[:160].lower().lstrip()
    if ctype.startswith("text/html") or head.startswith(b"<!doctype") or head.startswith(b"<html"):
        raise RuntimeError("Мой Арбитр: вместо файла пришла HTML-страница (вероятно, нужна авторизация)")
    filename = file_url.rstrip("/").split("/")[-1].split("?")[0] or f"moy-arbitr-{int(time.time())}.bin"
    cd = response.headers.get("content-disposition", "")
    m = re.search(r'filename\*?=(?:UTF-8\'\')?"?([^";]+)"?', cd, flags=re.IGNORECASE)
    if m:
        filename = m.group(1)
    if "." not in filename:
        if body[:4] == b"%PDF":
            filename += ".pdf"
        elif ctype.endswith("pdf"):
            filename += ".pdf"
        else:
            filename += ".bin"
    safe_name = re.sub(r"[^\w.\-а-яА-Я]", "_", filename)
    target = Path(tempfile.mkdtemp()) / safe_name
    target.write_bytes(body)
    return target


def open_case_and_download_documents(case_data: dict, job_id: int | None = None, progress=None):
    nav_ms = max(60_000, MOY_ARBITR_TIMEOUT_SEC * 1000)
    card_url = case_data.get("card_url") or MOY_ARBITR_BASE_URL
    with sync_playwright() as pw:
        browser = pw.chromium.launch(
            headless=MOY_ARBITR_HEADLESS,
            args=MOY_ARBITR_CHROMIUM_ARGS,
        )
        try:
            context = _new_context(browser)
            page = context.new_page()
            if progress and job_id is not None:
                progress(job_id, "opening_case", f"Мой Арбитр: открываю {card_url}")
            page.goto(card_url, wait_until="domcontentloaded", timeout=nav_ms)
            page.wait_for_timeout(2500)
            ensure_authorized(page)
            docs = collect_moy_arbitr_documents(page, card_url)
            seen_fu = {(d.get("file_url") or "").strip() for d in docs if d.get("file_url")}
            try:
                import worker as worker_mod

                extra = worker_mod.collect_kad_documents_from_linked_cards(
                    page,
                    "\n".join([(card_url or "").strip(), (page.url or "").strip()]),
                    nav_ms,
                )
                for row in extra:
                    u = (row.get("file_url") or "").strip()
                    if u and u not in seen_fu:
                        seen_fu.add(u)
                        docs.append(row)
                        if len(docs) >= MOY_ARBITR_MAX_DOCS_PER_CASE:
                            break
            except Exception:
                pass
            return context, browser, docs
        except Exception:
            browser.close()
            raise
