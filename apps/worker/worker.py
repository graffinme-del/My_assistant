import os
import re
import tempfile
import time
from datetime import datetime
from pathlib import Path
from urllib.parse import urljoin

import httpx
from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
from playwright.sync_api import sync_playwright


API_BASE = os.getenv("WORKER_API_BASE", "http://api:8000").rstrip("/")
OWNER_TOKEN = os.getenv("OWNER_TOKEN", "owner-dev-token")
COURT_SYNC_ENABLED = os.getenv("COURT_SYNC_ENABLED", "true").lower() == "true"
COURT_SYNC_NIGHT_HOUR = int(os.getenv("COURT_SYNC_NIGHT_HOUR", "2"))
COURT_SYNC_MAX_DOCS_PER_RUN = int(os.getenv("COURT_SYNC_MAX_DOCS_PER_RUN", "200"))
COURT_SYNC_DELAY_SEC = int(os.getenv("COURT_SYNC_DELAY_SEC", "5"))
COURT_SYNC_TIMEOUT_SEC = int(os.getenv("COURT_SYNC_TIMEOUT_SEC", "120"))


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
    try:
        page.wait_for_selector("a[href*='/Card/']", timeout=timeout_ms)
    except PlaywrightTimeoutError:
        try:
            page.wait_for_load_state("load", timeout=min(timeout_ms, 60_000))
        except PlaywrightTimeoutError:
            pass
        page.wait_for_timeout(4000)


def _search_cases_once(query_type: str, query_value: str) -> list[dict]:
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
        _wait_for_kad_search_results(page, nav_timeout)
        results = _collect_case_results(page)
        browser.close()
        return results


def search_cases_via_browser(query_type: str, query_value: str) -> list[dict]:
    if query_type == "card_url":
        return result_list_from_card_url(query_value)
    direct = parse_direct_card_url(query_value)
    if direct:
        return result_list_from_card_url(direct)

    for attempt in range(2):
        try:
            return _search_cases_once(query_type, query_value)
        except PlaywrightTimeoutError:
            if attempt == 0:
                time.sleep(3)
                continue
            raise


def collect_case_documents(card_url: str) -> list[dict]:
    nav_ms = max(60_000, COURT_SYNC_TIMEOUT_SEC * 1000)
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(accept_downloads=True)
        page = context.new_page()
        page.goto(card_url, wait_until="domcontentloaded", timeout=nav_ms)
        page.wait_for_timeout(3500)
        for tab_label in ["Документы", "Судебные акты", "Электронное дело"]:
            try:
                page.get_by_text(tab_label, exact=False).first.click(timeout=2500)
                page.wait_for_timeout(2500)
                break
            except Exception:
                continue
        anchors = page.locator("a")
        docs: list[dict] = []
        seen: set[str] = set()
        for idx in range(min(anchors.count(), 300)):
            link = anchors.nth(idx)
            href = link.get_attribute("href") or ""
            text = (link.inner_text() or "").strip()
            href_l = href.lower()
            if not href or href in seen:
                continue
            if not any(token in href_l for token in ["/card/", "pdf", "document", "download", "/documents/"]):
                if not any(token in text.lower() for token in ["pdf", "скач", "документ", "файл"]):
                    continue
            seen.add(href)
            docs.append(
                {
                    "remote_document_id": href,
                    "title": text[:500],
                    "filename": "",
                    "file_url": urljoin(card_url, href),
                }
            )
        browser.close()
        return docs


def download_document(file_url: str) -> Path:
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(accept_downloads=True)
        response = context.request.get(file_url, timeout=COURT_SYNC_TIMEOUT_SEC * 1000)
        if not response.ok:
            browser.close()
            raise RuntimeError(f"Не удалось скачать файл: HTTP {response.status}")
        filename = ""
        cd = response.headers.get("content-disposition", "")
        match = re.search(r'filename="?([^";]+)"?', cd)
        if match:
            filename = match.group(1)
        if not filename:
            filename = file_url.rstrip("/").split("/")[-1] or f"kad-{int(time.time())}.bin"
        safe_name = re.sub(r"[^\w.\-а-яА-Я]", "_", filename)
        target = Path(tempfile.mkdtemp()) / safe_name
        target.write_bytes(response.body())
        browser.close()
        return target


def process_job(job: dict) -> None:
    job_id = int(job["id"])
    query_type = str(job["query_type"])
    query_value = str(job["query_value"])
    run_mode = str(job["run_mode"])
    report_progress(job_id, "searching", f'Ищу в КАД: {query_type}="{query_value}"')
    try:
        results = search_cases_via_browser(query_type, query_value)
    except PlaywrightTimeoutError:
        complete_job(job_id, "needs_manual_step", "КАД не ответил вовремя. Нужен повторный запуск или ручная проверка.")
        return
    except Exception as exc:
        complete_job(job_id, "failed", f"Ошибка поиска в КАД: {exc}")
        return

    if not results:
        complete_job(job_id, "done", f'По запросу {query_type}="{query_value}" дела не найдены.', {"cases_found": 0})
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
        exact = [item for item in results if item.get("case_number", "").replace(" ", "").lower() == query_value.lower()]
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
    for case_data in target_cases:
        case_source_id = register_case_source(job_id, case_data)
        report_progress(job_id, "opening_case", f'Открываю карточку: {case_data.get("card_url")}')
        try:
            docs = collect_case_documents(case_data["card_url"])
        except Exception as exc:
            failures += 1
            lines.append(f'- Не удалось открыть документы дела {case_data.get("case_number")}: {exc}')
            continue
        discovered += len(docs)
        if not docs:
            lines.append(f'- У дела {case_data.get("case_number") or case_data.get("card_url")} документы не найдены автоматически.')
            continue
        for doc in docs[:COURT_SYNC_MAX_DOCS_PER_RUN]:
            try:
                report_progress(job_id, "downloading", f'Скачиваю: {doc.get("title") or doc.get("file_url")}')
                path = download_document(doc["file_url"])
                ingest_result = ingest_downloaded_file_to_case(path, preferred_case_id)
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
