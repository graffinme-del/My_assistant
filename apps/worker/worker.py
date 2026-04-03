import os
import re
import tempfile
import time
from datetime import date, datetime
from pathlib import Path
from urllib.parse import urljoin

import httpx
from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
from playwright.sync_api import sync_playwright

from parser_api_client import (
    case_dict_from_parser_case,
    extract_kad_pdf_url_entries_with_dates,
    filter_pdf_urls_by_date_range,
    parser_details_by_id,
    parser_details_by_number,
    parser_pdf_download,
    parser_search,
)

API_BASE = os.getenv("WORKER_API_BASE", "http://api:8000").rstrip("/")
OWNER_TOKEN = os.getenv("OWNER_TOKEN", "owner-dev-token")
COURT_SYNC_ENABLED = os.getenv("COURT_SYNC_ENABLED", "true").lower() == "true"
COURT_SYNC_NIGHT_HOUR = int(os.getenv("COURT_SYNC_NIGHT_HOUR", "2"))
COURT_SYNC_MAX_DOCS_PER_RUN = int(os.getenv("COURT_SYNC_MAX_DOCS_PER_RUN", "200"))
COURT_SYNC_DELAY_SEC = int(os.getenv("COURT_SYNC_DELAY_SEC", "5"))
COURT_SYNC_TIMEOUT_SEC = int(os.getenv("COURT_SYNC_TIMEOUT_SEC", "120"))
# Загрузка дел через Parser-API (HTTP) вместо Playwright, если задан PARSER_API_KEY.
_COURT_SYNC_PARSER_RAW = os.getenv("COURT_SYNC_USE_PARSER_API", "").strip().lower()
if _COURT_SYNC_PARSER_RAW:
    COURT_SYNC_USE_PARSER_API = _COURT_SYNC_PARSER_RAW not in ("0", "false", "no")
else:
    COURT_SYNC_USE_PARSER_API = bool(os.getenv("PARSER_API_KEY", "").strip())


def _parser_pdf_date_bounds() -> tuple[date | None, date | None]:
    """Границы дат для pdf_download (только Parser-API). Пусто = без фильтра."""
    raw_from = os.getenv("PARSER_DOWNLOAD_DATE_FROM", "").strip()
    raw_to = os.getenv("PARSER_DOWNLOAD_DATE_TO", "").strip()
    y_min = os.getenv("PARSER_DOWNLOAD_YEAR_MIN", "").strip()
    y_max = os.getenv("PARSER_DOWNLOAD_YEAR_MAX", "").strip()

    if not raw_from and y_min:
        try:
            raw_from = f"{int(y_min)}-01-01"
        except ValueError:
            pass
    if not raw_to and y_max:
        try:
            raw_to = f"{int(y_max)}-12-31"
        except ValueError:
            pass
    elif not raw_to and y_min and not y_max:
        try:
            raw_to = f"{int(y_min)}-12-31"
        except ValueError:
            pass

    d_from: date | None = None
    d_to: date | None = None
    if raw_from:
        try:
            d_from = datetime.strptime(raw_from[:10], "%Y-%m-%d").date()
        except ValueError:
            pass
    if raw_to:
        try:
            d_to = datetime.strptime(raw_to[:10], "%Y-%m-%d").date()
        except ValueError:
            pass
    return d_from, d_to


KAD_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36"
)


def api_post(path: str, json_payload: dict | None = None, files=None, data=None) -> dict:
    headers = {"X-API-Token": OWNER_TOKEN}
    with httpx.Client(timeout=max(30, COURT_SYNC_TIMEOUT_SEC)) as client:
        response = client.post(f"{API_BASE}{path}", json=json_payload, headers=headers, files=files, data=data)
    response.raise_for_status()
    if response.headers.get("content-type", "").startswith("application/json"):
        return response.json()
    return {}


def claim_job() -> dict | None:
    return api_post("/internal/court-sync/claim").get("job")


def enqueue_nightly_jobs() -> int:
    return int(api_post("/internal/court-sync/nightly-enqueue").get("enqueued", 0))


def report_progress(job_id: int, step: str, message: str) -> None:
    api_post(f"/internal/court-sync/jobs/{job_id}/progress", {"step": step, "message": message})


def complete_job(job_id: int, status: str, report_text: str, result_json: dict | None = None) -> None:
    api_post(
        f"/internal/court-sync/jobs/{job_id}/complete",
        {"status": status, "report_text": report_text, "result_json": result_json or {}},
    )


def register_case_source(job_id: int, case_data: dict) -> int | None:
    payload = {
        "remote_case_id": case_data.get("remote_case_id") or case_data.get("card_url") or "",
        "case_number": case_data.get("case_number", ""),
        "card_url": case_data.get("card_url", ""),
        "title": case_data.get("title", ""),
        "court_name": case_data.get("court_name", ""),
        "participants": case_data.get("participants", []),
        "linked_case_id": None,
    }
    result = api_post(f"/internal/court-sync/jobs/{job_id}/case-source", payload)
    return result.get("case_source_id")


def register_document_source(job_id: int, doc_data: dict) -> int | None:
    result = api_post(
        f"/internal/court-sync/jobs/{job_id}/document-source",
        {
            "remote_document_id": doc_data.get("remote_document_id") or doc_data.get("file_url") or "",
            "case_source_id": doc_data.get("case_source_id"),
            "local_document_id": doc_data.get("local_document_id"),
            "title": doc_data.get("title", ""),
            "filename": doc_data.get("filename", ""),
            "file_url": doc_data.get("file_url", ""),
            "status": doc_data.get("status", "discovered"),
        },
    )
    return result.get("document_source_id")


def ingest_downloaded_file(path: Path) -> dict:
    with path.open("rb") as f:
        return api_post("/documents/ingest", files={"file": (path.name, f, "application/octet-stream")})


def normalize_case_for_match(value: str) -> str:
    """Совпадает с API normalize_arbitr_case_number — для сравнения номера из КАД и из запроса."""
    s = (value or "").replace(" ", "").replace("\n", "").replace("\\", "")
    if len(s) >= 3 and s[0] in ("\u0410", "\u0430"):
        s = "A" + s[1:]
    elif len(s) >= 3 and s[0] in ("A", "a"):
        s = "A" + s[1:]
    return s.lower()


def ensure_case_id(case_number: str) -> int | None:
    try:
        resp = api_post("/internal/court-sync/ensure-case", data={"case_number": case_number})
        return int(resp.get("case_id"))
    except Exception:
        return None


def ingest_downloaded_file_to_case(path: Path, case_id: int | None) -> dict:
    data = {}
    if case_id:
        data["preferred_case_id"] = str(case_id)
    with path.open("rb") as f:
        return api_post(
            "/documents/ingest",
            files={"file": (path.name, f, "application/octet-stream")},
            data=data,
        )


def _fill_search_input(page, label_text: str, value: str) -> bool:
    candidates = [
        f"text={label_text}",
        f"text={label_text[:8]}",
    ]
    for selector in candidates:
        try:
            anchor = page.locator(selector).first
            target = anchor.locator("xpath=following::input[1]").first
            target.fill("")
            target.fill(value)
            return True
        except Exception:
            continue
    try:
        inputs = page.locator("input")
        for idx in range(min(inputs.count(), 6)):
            candidate = inputs.nth(idx)
            placeholder = (candidate.get_attribute("placeholder") or "").lower()
            if label_text.lower()[:5] in placeholder:
                candidate.fill(value)
                return True
        if label_text.lower().startswith("участник"):
            inputs.nth(0).fill(value)
            return True
        if "номер" in label_text.lower() and inputs.count() >= 3:
            inputs.nth(2).fill(value)
            return True
    except Exception:
        return False
    return False


def _normalize_kad_card_url(value: str) -> str:
    raw = (value or "").strip().split("?")[0].rstrip("/")
    if not raw:
        return ""
    if not raw.lower().startswith("http"):
        raw = "https://" + raw.lstrip("/")
    return raw


def parse_direct_card_url(text: str) -> str | None:
    """Если в строке есть ссылка на карточку дела КАД — вернуть нормализованный URL."""
    m = re.search(r"(https?://kad\.arbitr\.ru/Card/[a-fA-F0-9\-]+)", (text or "").strip())
    return _normalize_kad_card_url(m.group(1)) if m else None


def result_list_from_card_url(card_url: str) -> list[dict]:
    card_url = _normalize_kad_card_url(card_url)
    if not card_url or "/Card/" not in card_url:
        return []
    rid = card_url.rstrip("/").split("/")[-1]
    return [
        {
            "remote_case_id": rid,
            "card_url": card_url,
            "case_number": "",
            "title": f"Карточка {rid}",
            "court_name": "",
            "participants": [],
        }
    ]


def _collect_case_results(page) -> list[dict]:
    links = page.locator("a[href*='/Card/']")
    seen: set[str] = set()
    results: list[dict] = []
    for idx in range(min(links.count(), 25)):
        link = links.nth(idx)
        href = link.get_attribute("href") or ""
        text = (link.inner_text() or "").strip()
        if not href:
            continue
        card_url = urljoin("https://kad.arbitr.ru", href)
        if card_url in seen:
            continue
        seen.add(card_url)
        case_number_match = re.search(r"([АA]\d{1,4}-\d{1,7}/\d{2,4}|\d{1,2}-\d{1,7}/\d{2,4})", text)
        results.append(
            {
                "remote_case_id": href.split("/")[-1],
                "card_url": card_url,
                "case_number": case_number_match.group(1) if case_number_match else "",
                "title": text[:255],
                "court_name": "",
                "participants": [],
            }
        )
    return results


def _wait_for_kad_search_results(page, timeout_ms: int) -> None:
    """КАД — SPA; networkidle часто не наступает. Ждём появления ссылок на карточки или запасной таймаут."""
    selector_timeout = min(45_000, timeout_ms)
    try:
        page.wait_for_selector("a[href*='/Card/']", timeout=selector_timeout)
    except PlaywrightTimeoutError:
        try:
            page.wait_for_load_state("load", timeout=min(timeout_ms, 60_000))
        except PlaywrightTimeoutError:
            pass
        page.wait_for_timeout(4000)


def _search_cases_once(query_type: str, query_value: str, job_id: int | None = None) -> list[dict]:
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        nav_timeout = max(60_000, COURT_SYNC_TIMEOUT_SEC * 1000)
        page.goto("https://kad.arbitr.ru/", wait_until="domcontentloaded", timeout=nav_timeout)
        page.wait_for_timeout(2500)
        if query_type == "case_number":
            ok = _fill_search_input(page, "Номер дела", query_value)
        else:
            ok = _fill_search_input(page, "Участник дела", query_value)
        if not ok:
            browser.close()
            raise RuntimeError("Не удалось найти поле поиска на странице КАД.")
        page.get_by_text("Найти").first.click()
        page.wait_for_timeout(2000)
        if job_id is not None:
            report_progress(job_id, "searching", "Жду выдачу КАД (поиск карточек дела)...")
        _wait_for_kad_search_results(page, nav_timeout)
        results = _collect_case_results(page)
        browser.close()
        return results


def search_cases_via_browser(query_type: str, query_value: str, job_id: int | None = None) -> list[dict]:
    if query_type == "card_url":
        return result_list_from_card_url(query_value)
    direct = parse_direct_card_url(query_value)
    if direct:
        return result_list_from_card_url(direct)

    for attempt in range(2):
        try:
            return _search_cases_once(query_type, query_value, job_id=job_id)
        except PlaywrightTimeoutError:
            if attempt == 0:
                time.sleep(3)
                continue
            raise


def _normalize_inn_digits(value: str) -> str:
    return re.sub(r"\D+", "", value or "")


def try_parser_search_cases(query_type: str, query_value: str, job_id: int | None) -> list[dict] | None:
    """Если Parser-API доступен — пробуем поиск/детали без браузера. None = fallback на Playwright."""
    if not COURT_SYNC_USE_PARSER_API:
        return None
    try:
        if query_type == "card_url":
            url = _normalize_kad_card_url(query_value)
            rid = url.rstrip("/").split("/")[-1]
            if not re.fullmatch(r"[a-fA-F0-9\-]+", rid):
                return None
            if job_id is not None:
                report_progress(job_id, "searching", "Parser-API: детали дела по ссылке на карточку…")
            d = parser_details_by_id(rid)
            if d.get("Success") != 1:
                return []
            cases = d.get("Cases") or []
            return [case_dict_from_parser_case(c, card_url_hint=url) for c in cases[:20]]

        if query_type == "case_number":
            qn = re.sub(r"\s+", "", (query_value or "").replace("\\", ""))
            if job_id is not None:
                report_progress(job_id, "searching", "Parser-API: детали по номеру дела…")
            d = parser_details_by_number(qn)
            if d.get("Success") != 1:
                return []
            cases = d.get("Cases") or []
            return [case_dict_from_parser_case(c) for c in cases[:20]]

        if query_type == "inn":
            inn = _normalize_inn_digits(query_value)
            if not inn:
                return None
            if job_id is not None:
                report_progress(job_id, "searching", "Parser-API: поиск дел по ИНН…")
            d = parser_search(inn=inn, inn_type="Any", page=1)
            if d.get("Success") != 1:
                return []
            cases = d.get("Cases") or []
            return [case_dict_from_parser_case(c) for c in cases[:25]]

        return None
    except Exception as exc:
        print(f"[worker] Parser-API search fallback to browser: {exc}")
        return None


def search_cases_for_job(query_type: str, query_value: str, job_id: int | None = None) -> list[dict]:
    parsed = try_parser_search_cases(query_type, query_value, job_id)
    if parsed is not None:
        return parsed
    return search_cases_via_browser(query_type, query_value, job_id=job_id)


def is_kad_junk_url(url: str) -> bool:
    """Статика, капча, шрифты — не судебные документы (иначе «скачиваются» pravocaptcha.css и т.п.)."""
    u = (url or "").lower()
    if not u:
        return True
    junk = (
        "pravocaptcha",
        "captcha",
        "/favicon",
        ".css",
        ".js",
        ".map",
        ".woff",
        ".woff2",
        ".ttf",
        "/fonts/",
        "/bundles/",
        "fingerprint",
        "jquery",
        "bootstrap",
        "metrika",
        "analytics",
        "yastatic",
        "/static/",
        "/scripts/",
        "/content/scripts",
    )
    if any(s in u for s in junk):
        return True
    if re.search(r"\.(png|gif|jpg|jpeg|svg|ico|webp)(\?|$|#)", u):
        return True
    return False


def extract_case_number_from_page(page) -> str | None:
    try:
        html = page.content()
    except Exception:
        return None
    m = re.search(r"([АA]\d{1,4}-\d{1,7}/\d{2,4})", html, flags=re.IGNORECASE)
    if not m:
        return None
    return m.group(1).replace(" ", "").replace("\n", "")


def _href_looks_like_kad_document(href: str) -> bool:
    if not href or href.startswith("#") or href.lower().startswith("javascript:"):
        return False
    if is_kad_junk_url(href):
        return False
    h = href.lower()
    if re.search(r"/card/[a-f0-9\-]{30,}/?$", h) and "pdf" not in h and "document" not in h:
        return False
    # Не использовать общее «kad/» — на домене полно статики; только признаки выдачи/файла дела.
    return any(
        k in h
        for k in (
            "pdf",
            "pdfdocument",
            "getpdf",
            "document",
            "download",
            "viewdocument",
            "attachment",
            "getfile",
            "showdocument",
            "content",
            "/pdf/",
            "electronic",
            "электрон",
            "судебн",
            "определен",
            "постановлен",
            "handler",
            ".pdf",
            ".doc",
            ".docx",
            ".xls",
            ".xlsx",
            ".rtf",
            "aspx",
        )
    )


def _anchor_text_hints_document(text: str) -> bool:
    t = (text or "").lower()
    return any(
        k in t
        for k in (
            "pdf",
            "скач",
            "документ",
            "определ",
            "решени",
            "постанов",
            "ходатай",
            "жалоб",
            "копи",
            "выписк",
        )
    )


def _append_anchor_docs_from_root(root, card_url: str, seen: set[str], docs: list[dict]) -> None:
    """root — Page или Frame."""
    try:
        root.evaluate("window.scrollTo(0, document.body.scrollHeight)")
    except Exception:
        pass
    try:
        anchors = root.locator("a")
        n = min(anchors.count(), 800)
    except Exception:
        return
    for idx in range(n):
        link = anchors.nth(idx)
        try:
            href = link.get_attribute("href") or ""
            text = (link.inner_text() or "").strip()
        except Exception:
            continue
        if not href or href.startswith("#"):
            continue
        if not href.startswith("http") and not href.startswith("/"):
            continue
        if not (_href_looks_like_kad_document(href) or _anchor_text_hints_document(text)):
            continue
        full_url = urljoin(card_url, href)
        if is_kad_junk_url(full_url):
            continue
        if full_url in seen:
            continue
        seen.add(full_url)
        docs.append(
            {
                "remote_document_id": href[:500],
                "title": text[:500],
                "filename": "",
                "file_url": full_url,
            }
        )


def extract_kad_document_urls_from_html(html: str, card_url: str) -> list[dict]:
    """Дополнительно вытаскиваем ссылки из разметки/скриптов (часть UI КАД не в обычных <a>)."""
    seen: set[str] = set()
    out: list[dict] = []
    for m in re.finditer(r"(https://kad\.arbitr\.ru/[^\"\'\s<>]+)", html, flags=re.IGNORECASE):
        u = m.group(1).rstrip("\\.,);")
        if is_kad_junk_url(u):
            continue
        if not _href_looks_like_kad_document(u):
            continue
        if u in seen:
            continue
        seen.add(u)
        out.append({"remote_document_id": u[:500], "title": "", "filename": "", "file_url": u})
    for m in re.finditer(
        r'(?:href|src)=["\'](/[^"\']*(?:[Pp]df|[Dd]ocument|[Dd]ownload|[Cc]ontent|[Ff]ile|[Kk]ad)[^"\']*)["\']',
        html,
    ):
        u = urljoin("https://kad.arbitr.ru", m.group(1))
        if is_kad_junk_url(u):
            continue
        if not _href_looks_like_kad_document(u):
            continue
        if u in seen:
            continue
        seen.add(u)
        out.append({"remote_document_id": u[:500], "title": "", "filename": "", "file_url": u})
    return out


def collect_document_links_from_playwright_page(page, card_url: str) -> list[dict]:
    """Все фреймы (в т.ч. iframe) + вырезка URL из HTML."""
    seen: set[str] = set()
    docs: list[dict] = []
    for frame in page.frames:
        try:
            _append_anchor_docs_from_root(frame, card_url, seen, docs)
        except Exception:
            continue
    try:
        html = page.content()
        for item in extract_kad_document_urls_from_html(html, card_url):
            if item["file_url"] not in seen:
                seen.add(item["file_url"])
                docs.append(item)
    except Exception:
        pass
    return docs


KAD_TAB_LABELS = ("Документы", "Судебные акты", "Электронное дело", "Материалы", "Ход дела")


def merge_popup_pdf_urls(page, card_url: str, nav_ms: int, seen: set[str], docs: list[dict], max_clicks: int = 22) -> None:
    """КАД часто открывает PDF в новой вкладке — перехватываем URL после клика по ссылке."""
    clicks = 0
    for frame in page.frames:
        try:
            anchors = frame.locator("a")
            n = min(anchors.count(), 120)
        except Exception:
            continue
        for i in range(n):
            if clicks >= max_clicks:
                return
            link = anchors.nth(i)
            try:
                href = (link.get_attribute("href") or "").strip()
                target = (link.get_attribute("target") or "").lower()
                text = (link.inner_text() or "").strip()
            except Exception:
                continue
            if not href or href.startswith("#") or "javascript:" in href.lower():
                continue
            if is_kad_junk_url(href):
                continue
            if not (target == "_blank" or _anchor_text_hints_document(text) or _href_looks_like_kad_document(href)):
                continue
            full_url = urljoin(card_url, href)
            if full_url in seen:
                continue
            try:
                with page.expect_popup(timeout=8000) as pop_ev:
                    link.click(timeout=4000)
                popup = pop_ev.value
                popup.wait_for_load_state("domcontentloaded", timeout=nav_ms)
                popup.wait_for_timeout(2000)
                final = (popup.url or "").strip()
                popup.close()
            except Exception:
                continue
            if not final or is_kad_junk_url(final) or final in seen:
                continue
            seen.add(final)
            docs.append(
                {
                    "remote_document_id": final[:500],
                    "title": text[:500] or final,
                    "filename": "",
                    "file_url": final,
                }
            )
            clicks += 1
            page.wait_for_timeout(600)


def open_kad_card_and_collect_docs(page, card_url: str, nav_ms: int) -> list[dict]:
    """По очереди открываем вкладки карточки и собираем ссылки (раньше кликали только по первой удачной)."""
    merged: list[dict] = []
    seen: set[str] = set()
    for label in KAD_TAB_LABELS:
        try:
            page.goto(card_url, wait_until="domcontentloaded", timeout=nav_ms)
            page.wait_for_timeout(2000)
            page.get_by_text(label, exact=False).first.click(timeout=5000)
            page.wait_for_timeout(4000)
            chunk = collect_document_links_from_playwright_page(page, card_url)
            for d in chunk:
                u = d["file_url"]
                if u not in seen:
                    seen.add(u)
                    merged.append(d)
            merge_popup_pdf_urls(page, card_url, nav_ms, seen, merged)
        except Exception:
            continue
    if not merged:
        try:
            page.goto(card_url, wait_until="domcontentloaded", timeout=nav_ms)
            page.wait_for_timeout(5000)
            merged = collect_document_links_from_playwright_page(page, card_url)
            seen = {d["file_url"] for d in merged}
            merge_popup_pdf_urls(page, card_url, nav_ms, seen, merged)
        except Exception:
            merged = []
    return merged


def _extract_pdf_url_from_viewer_html(html: str) -> str | None:
    """Если пришла HTML-страница просмотрщика — пробуем вытащить прямую ссылку на PDF."""
    chunk = html[:300000]
    patterns = (
        r'src="(https://kad\.arbitr\.ru[^"]+\.pdf[^"]*)"',
        r'href="(https://kad\.arbitr\.ru[^"]+\.pdf[^"]*)"',
        r"src='(https://kad\.arbitr\.ru[^']+\.pdf[^']*)'",
        r'"(https://kad\.arbitr\.ru/[Pp]df[^"]+)"',
        r"url\s*:\s*['\"](https://kad\.arbitr\.ru[^'\"]+)['\"]",
    )
    for p in patterns:
        m = re.search(p, chunk, flags=re.IGNORECASE)
        if m and not is_kad_junk_url(m.group(1)):
            return m.group(1)
    return None


def download_document_via_context(context, file_url: str, _depth: int = 0) -> Path:
    """Тот же storage state, что и у страницы КАД — иначе часто 403 без сессии."""
    if is_kad_junk_url(file_url):
        raise RuntimeError("URL отфильтрован как статика/капча, не документ дела")
    if _depth > 3:
        raise RuntimeError("Слишком много переходов по вложенным ссылкам")
    response = context.request.get(
        file_url,
        timeout=max(30_000, COURT_SYNC_TIMEOUT_SEC * 1000),
        headers={"Referer": "https://kad.arbitr.ru/", "Accept": "*/*"},
    )
    if not response.ok:
        raise RuntimeError(f"Не удалось скачать файл: HTTP {response.status}")
    body = response.body()
    ctype = (response.headers.get("content-type") or "").split(";")[0].strip().lower()

    if len(body) >= 4 and body[:4] == b"%PDF":
        filename = file_url.rstrip("/").split("/")[-1] or f"kad-{int(time.time())}.pdf"
        if not filename.lower().endswith(".pdf"):
            filename = f"{filename}.pdf"
        safe_name = re.sub(r"[^\w.\-а-яА-Я]", "_", filename)
        target = Path(tempfile.mkdtemp()) / safe_name
        target.write_bytes(body)
        return target

    if ctype in ("text/css", "text/javascript", "application/javascript", "application/x-javascript"):
        raise RuntimeError(f"Вместо документа пришёл {ctype} (статика)")

    head = body[:120].lower().lstrip()
    if head.startswith(b"<!doctype") or head.startswith(b"<html"):
        if _depth < 3:
            nested = _extract_pdf_url_from_viewer_html(body.decode("utf-8", errors="ignore"))
            if nested and nested != file_url:
                return download_document_via_context(context, nested, _depth + 1)
        raise RuntimeError("Вместо файла пришла HTML без распознанной ссылки на PDF (просмотрщик или капча)")

    filename = ""
    cd = response.headers.get("content-disposition", "")
    match = re.search(r'filename="?([^";]+)"?', cd)
    if match:
        filename = match.group(1)
    if not filename:
        filename = file_url.rstrip("/").split("/")[-1] or f"kad-{int(time.time())}.bin"
    if is_kad_junk_url(filename):
        raise RuntimeError("Имя файла похоже на статику, не на документ")
    fn_low = filename.lower()
    if fn_low.endswith((".css", ".js", ".map", ".woff", ".woff2")):
        raise RuntimeError("Подозрительное расширение файла (не документ дела)")
    safe_name = re.sub(r"[^\w.\-а-яА-Я]", "_", filename)
    target = Path(tempfile.mkdtemp()) / safe_name
    target.write_bytes(body)
    return target


def download_documents_via_parser(
    job_id: int,
    target_cases: list[dict],
    preview_lines: list[str],
    results: list[dict],
    preferred_case_id: int | None,
) -> tuple[int, int, int, list[str]]:
    """Скачивание PDF по URL из ответа Parser-API (pdf_download), без Playwright."""
    downloaded = 0
    discovered = 0
    failures = 0
    lines = preview_lines[:]

    for case_data in target_cases:
        case_source_id = register_case_source(job_id, case_data)
        rid = (case_data.get("remote_case_id") or "").strip()
        num = (case_data.get("case_number") or "").strip()
        card_url = case_data.get("card_url") or ""
        report_progress(
            job_id,
            "opening_case",
            f"Parser-API: запрос деталей дела {num or rid or card_url}",
        )
        try:
            if rid:
                details = parser_details_by_id(rid)
            elif num:
                details = parser_details_by_number(re.sub(r"\s+", "", num.replace("\\", "")))
            else:
                lines.append(f"- Нет CaseId/номера для {card_url}, пропуск.")
                failures += 1
                continue
        except Exception as exc:
            failures += 1
            lines.append(f"- Parser-API details: {exc}")
            continue

        if details.get("Success") != 1:
            failures += 1
            lines.append(f"- Parser-API: Success != 1 для {num or rid}")
            continue

        entries = extract_kad_pdf_url_entries_with_dates(details)
        d_lo, d_hi = _parser_pdf_date_bounds()
        urls, skipped_no_date = filter_pdf_urls_by_date_range(entries, d_lo, d_hi)
        if d_lo or d_hi:
            lines.append(
                f"- Фильтр PDF по датам событий: с {d_lo or '—'} по {d_hi or '—'}; "
                f"всего ссылок {len(entries)}, после фильтра {len(urls)}, "
                f"без даты события (отброшено) {skipped_no_date}."
            )
        discovered += len(urls)
        if not urls:
            if entries and (d_lo or d_hi):
                lines.append(
                    f"- У дела {num or rid} ни один PDF не попал в выбранный период "
                    f"(или у событий нет даты — см. отчёт выше)."
                )
            else:
                lines.append(
                    f"- У дела {num or rid} по Parser-API не найдено PDF-ссылок в карточке "
                    f"(возможна структура без PdfDocument в ответе)."
                )
            continue

        effective_preferred_id = preferred_case_id
        if not effective_preferred_id and num:
            cid = ensure_case_id(num)
            if cid:
                effective_preferred_id = cid

        for doc_url in urls[:COURT_SYNC_MAX_DOCS_PER_RUN]:
            try:
                report_progress(job_id, "downloading", f"Parser-API pdf_download: {doc_url[:120]}…")
                raw = parser_pdf_download(doc_url)
                fn = doc_url.rstrip("/").split("/")[-1] or f"kad-{int(time.time())}.pdf"
                if not fn.lower().endswith(".pdf"):
                    fn = f"{fn}.pdf"
                safe_name = re.sub(r"[^\w.\-а-яА-Я]", "_", fn)
                target = Path(tempfile.mkdtemp()) / safe_name
                target.write_bytes(raw)
                ingest_result = ingest_downloaded_file_to_case(target, effective_preferred_id)
                local_document = ingest_result.get("document") or {}
                doc = {
                    "remote_document_id": doc_url[:500],
                    "case_source_id": case_source_id,
                    "local_document_id": local_document.get("id"),
                    "title": fn,
                    "filename": local_document.get("filename") or target.name,
                    "file_url": doc_url,
                    "status": "downloaded",
                }
                register_document_source(job_id, doc)
                downloaded += 1
            except Exception as exc:
                failures += 1
                register_document_source(
                    job_id,
                    {
                        "remote_document_id": doc_url[:500],
                        "case_source_id": case_source_id,
                        "title": doc_url[:200],
                        "filename": "",
                        "file_url": doc_url,
                        "status": "failed",
                    },
                )
                lines.append(f"- Не удалось скачать через Parser-API {doc_url[:100]}: {exc}")
            time.sleep(max(1, COURT_SYNC_DELAY_SEC))

    return downloaded, discovered, failures, lines


def process_job(job: dict) -> None:
    job_id = int(job["id"])
    query_type = str(job["query_type"])
    query_value = str(job["query_value"])
    run_mode = str(job["run_mode"])
    report_progress(job_id, "searching", f'Ищу в КАД: {query_type}="{query_value}"')
    try:
        results = search_cases_for_job(query_type, query_value, job_id=job_id)
    except PlaywrightTimeoutError:
        complete_job(job_id, "needs_manual_step", "КАД не ответил вовремя. Нужен повторный запуск или ручная проверка.")
        return
    except Exception as exc:
        complete_job(job_id, "failed", f"Ошибка поиска в КАД: {exc}")
        return

    if not results:
        msg = f'По запросу {query_type}="{query_value}" дела не найдены в выдаче КАД.'
        if run_mode == "download":
            complete_job(
                job_id,
                "needs_manual_step",
                msg + " Проверьте номер дела на сайте kad.arbitr.ru или откройте карточку по прямой ссылке.",
                {"cases_found": 0},
            )
        else:
            complete_job(job_id, "done", msg, {"cases_found": 0})
        return

    preview_lines = [f'Найдено дел: {len(results)} по запросу {query_type}="{query_value}".']
    for item in results[:10]:
        preview_lines.append(f'- {item.get("case_number") or "без номера"} | {item.get("title") or item.get("card_url")}')

    if run_mode == "preview":
        for item in results[:20]:
            register_case_source(job_id, item)
        complete_job(job_id, "done", "\n".join(preview_lines), {"cases_found": len(results)})
        return

    target_cases = results
    if query_type == "case_number":
        preferred_case_id = ensure_case_id(query_value)
        qn = normalize_case_for_match(query_value)
        exact = [
            item
            for item in results
            if normalize_case_for_match(item.get("case_number", "")) == qn
        ]
        if exact:
            target_cases = exact
        else:
            target_cases = results[:1]
    else:
        preferred_case_id = None
        target_cases = results[:10]

    downloaded = 0
    discovered = 0
    failures = 0
    lines = preview_lines[:]

    if COURT_SYNC_USE_PARSER_API and run_mode == "download":
        downloaded, discovered, failures, lines = download_documents_via_parser(
            job_id, target_cases, preview_lines, results, preferred_case_id
        )
        lines.append(
            f"Итог: найдено дел {len(results)}, найдено документов {discovered}, "
            f"скачано {downloaded}, ошибок {failures} (режим Parser-API)."
        )
        if run_mode != "preview" and downloaded == 0:
            lines.append(
                "Автоскачивание через Parser-API не принесло файлов. "
                "Проверьте лимит ключа, статус сервиса arbitr или отключите COURT_SYNC_USE_PARSER_API для режима браузера."
            )
            final_status = "needs_manual_step"
        else:
            final_status = "done" if failures == 0 else "needs_manual_step"
        complete_job(
            job_id,
            final_status,
            "\n".join(lines),
            {
                "cases_found": len(results),
                "documents_found": discovered,
                "downloaded": downloaded,
                "failures": failures,
                "backend": "parser_api",
            },
        )
        return

    nav_ms = max(60_000, COURT_SYNC_TIMEOUT_SEC * 1000)
    for case_data in target_cases:
        case_source_id = register_case_source(job_id, case_data)
        card_url = case_data["card_url"]
        report_progress(job_id, "opening_case", f"Открываю карточку (одна сессия для страницы и скачивания): {card_url}")
        effective_preferred_id = preferred_case_id
        with sync_playwright() as pw:
            browser = pw.chromium.launch(
                headless=True,
                args=["--disable-blink-features=AutomationControlled"],
            )
            context = browser.new_context(
                accept_downloads=True,
                user_agent=KAD_USER_AGENT,
                locale="ru-RU",
                viewport={"width": 1280, "height": 900},
            )
            page = context.new_page()
            try:
                page.goto(card_url, wait_until="domcontentloaded", timeout=nav_ms)
                page.wait_for_timeout(2000)
                case_hint = extract_case_number_from_page(page)
                if case_hint and not effective_preferred_id:
                    cid = ensure_case_id(case_hint)
                    if cid:
                        effective_preferred_id = cid
                docs = open_kad_card_and_collect_docs(page, card_url, nav_ms)
            except Exception as exc:
                failures += 1
                lines.append(f'- Не удалось открыть карточку {case_data.get("case_number") or ""}: {exc}')
                browser.close()
                continue
            discovered += len(docs)
            if not docs:
                lines.append(
                    f'- У дела {case_data.get("case_number") or card_url} документы не найдены автоматически '
                    f'(возможны капча, другая вёрстка КАД или документы только в «Электронном деле»).'
                )
                browser.close()
                continue
            for doc in docs[:COURT_SYNC_MAX_DOCS_PER_RUN]:
                try:
                    report_progress(job_id, "downloading", f'Скачиваю: {doc.get("title") or doc.get("file_url")}')
                    path = download_document_via_context(context, doc["file_url"])
                    ingest_result = ingest_downloaded_file_to_case(path, effective_preferred_id)
                    local_document = ingest_result.get("document") or {}
                    doc["case_source_id"] = case_source_id
                    doc["local_document_id"] = local_document.get("id")
                    doc["filename"] = local_document.get("filename") or path.name
                    doc["status"] = "downloaded"
                    register_document_source(job_id, doc)
                    downloaded += 1
                except Exception as exc:
                    failures += 1
                    register_document_source(
                        job_id,
                        {
                            "remote_document_id": doc.get("remote_document_id") or doc.get("file_url"),
                            "case_source_id": case_source_id,
                            "title": doc.get("title", ""),
                            "filename": doc.get("filename", ""),
                            "file_url": doc.get("file_url", ""),
                            "status": "failed",
                        },
                    )
                    lines.append(f'- Не удалось скачать {doc.get("title") or doc.get("file_url")}: {exc}')
                time.sleep(max(1, COURT_SYNC_DELAY_SEC))
            browser.close()

    lines.append(f"Итог: найдено дел {len(results)}, найдено документов {discovered}, скачано {downloaded}, ошибок {failures}.")
    if run_mode != "preview" and downloaded == 0:
        lines.append("Автоскачивание не принесло файлов. Скорее всего, КАД требует ручной шаг (капча/подтверждение) или структура документов не распознана.")
        final_status = "needs_manual_step"
    else:
        final_status = "done" if failures == 0 else "needs_manual_step"
    complete_job(
        job_id,
        final_status,
        "\n".join(lines),
        {"cases_found": len(results), "documents_found": discovered, "downloaded": downloaded, "failures": failures},
    )


def main() -> None:
    env = os.getenv("APP_ENV", "development")
    print(f"Worker started in {env} mode.")
    print(f"COURT_SYNC_USE_PARSER_API={COURT_SYNC_USE_PARSER_API} (скачивание без Playwright, если true и задан PARSER_API_KEY).")
    last_nightly_date = None
    while True:
        try:
            now = datetime.utcnow()
            if COURT_SYNC_ENABLED and now.hour >= COURT_SYNC_NIGHT_HOUR and last_nightly_date != now.date():
                enqueued = enqueue_nightly_jobs()
                print(f"Nightly enqueue completed: {enqueued}")
                last_nightly_date = now.date()
            job = claim_job()
            if not job:
                time.sleep(10)
                continue
            process_job(job)
        except Exception as exc:
            print(f"Worker loop error: {exc}")
            time.sleep(15)


if __name__ == "__main__":
    main()
