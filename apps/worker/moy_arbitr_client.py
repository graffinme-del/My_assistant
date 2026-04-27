from __future__ import annotations

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

MOY_ARBITR_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36"
)


class MoyArbitrAuthRequired(RuntimeError):
    pass


class MoyArbitrNoResults(RuntimeError):
    pass


def state_file_exists() -> bool:
    p = Path(MOY_ARBITR_STATE_PATH)
    return p.exists() and p.stat().st_size > 20


def _query_type_without_prefix(query_type: str) -> str:
    return (query_type or "").removeprefix("moy_arbitr_")


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
    candidates.extend([page.locator("input[type='search']").first, page.locator("input").first])
    for loc in candidates:
        try:
            if loc.is_visible(timeout=1500):
                loc.fill(value, timeout=4000)
                return True
        except Exception:
            continue
    return False


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
    page.goto(_search_url(query_type, query_value), wait_until="domcontentloaded", timeout=nav_ms)
    page.wait_for_timeout(1800)
    ensure_authorized(page)
    _dismiss_common_overlays(page)
    qt = _query_type_without_prefix(query_type)
    if qt == "case_number":
        patterns = (r"номер.*дел", r"дело", r"case")
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
    nav_ms = max(60_000, MOY_ARBITR_TIMEOUT_SEC * 1000)
    with sync_playwright() as pw:
        browser = pw.chromium.launch(
            headless=MOY_ARBITR_HEADLESS,
            args=["--disable-blink-features=AutomationControlled"],
        )
        try:
            context = _new_context(browser)
            page = context.new_page()
            if progress and job_id is not None:
                progress(job_id, "searching", f"Мой Арбитр: поиск {query_type}={query_value}")
            _drive_search_form(page, query_type, query_value, nav_ms)
            results = _extract_case_results(page)
            if not results and _page_looks_unauthorized(page):
                raise MoyArbitrAuthRequired(_manual_login_message("сессия «Мой Арбитр» истекла"))
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
            args=["--disable-blink-features=AutomationControlled"],
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
            return context, browser, docs
        except Exception:
            browser.close()
            raise
