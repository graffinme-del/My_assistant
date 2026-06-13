"""
Parser-API в worker: те же методы, что в apps/api/app/parser_api_client.py,
но настройки только из окружения (без импорта FastAPI-приложения).
"""

from __future__ import annotations

import base64
import json
import os
import re
from datetime import date, datetime
from typing import Any

import httpx

DEFAULT_BASE = "https://parser-api.com/parser/arbitr_api"


def _base_url() -> str:
    return (os.getenv("PARSER_API_BASE_URL") or DEFAULT_BASE).rstrip("/")


def _api_key() -> str:
    key = (os.getenv("PARSER_API_KEY") or "").strip()
    if not key:
        raise ValueError("PARSER_API_KEY не задан в окружении")
    return key


def _timeout_sec() -> float:
    raw = (os.getenv("PARSER_API_TIMEOUT_SEC") or "120").strip()
    try:
        return float(raw)
    except ValueError:
        return 120.0


def _request(endpoint: str, params: dict[str, Any]) -> dict[str, Any]:
    url = f"{_base_url()}/{endpoint}"
    q = {"key": _api_key(), **{k: v for k, v in params.items() if v is not None}}
    with httpx.Client(timeout=_timeout_sec()) as client:
        r = client.get(url, params=q)
        try:
            r.raise_for_status()
        except httpx.HTTPStatusError as exc:
            # Не светим key из query-string в тексте исключения.
            raise RuntimeError(f"Parser-API {endpoint}: HTTP {exc.response.status_code}") from None
        return r.json()


def parser_details_by_number(case_number: str) -> dict[str, Any]:
    return _request("details_by_number", {"CaseNumber": case_number})


def parser_details_by_id(case_id: str) -> dict[str, Any]:
    return _request("details_by_id", {"CaseId": case_id})


def parser_search(
    *,
    inn: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    court: str | None = None,
    inn_type: str = "Any",
    case_type: str | None = None,
    page: int | None = None,
) -> dict[str, Any]:
    params: dict[str, Any] = {"InnType": inn_type}
    if inn:
        params["Inn"] = inn
    if date_from:
        params["DateFrom"] = date_from
    if date_to:
        params["DateTo"] = date_to
    if court:
        params["Court"] = court
    if case_type:
        params["CaseType"] = case_type
    if page is not None:
        params["Page"] = page
    return _request("search", params)


def parser_pdf_download(pdf_url: str) -> bytes:
    data = _request("pdf_download", {"url": pdf_url})
    if data.get("Success") != 1:
        err = data.get("error") or data.get("Error")
        if not err:
            err = json.dumps(data, ensure_ascii=False)[:900]
        raise RuntimeError(f"Parser-API pdf_download: {err}")
    b64 = data.get("pdfContent")
    if not b64:
        raise RuntimeError("Parser-API: pdfContent пуст")
    return base64.b64decode(b64)


def _parse_event_date(raw: str | None) -> date | None:
    """Дата события из JSON Parser-API (часто YYYY-MM-DD, иногда DD.MM.YYYY в DisplayDate)."""
    if not raw or not isinstance(raw, str):
        return None
    s = raw.strip()
    m = re.search(r"(\d{4}-\d{2}-\d{2})", s)
    if m:
        try:
            return datetime.strptime(m.group(1), "%Y-%m-%d").date()
        except ValueError:
            pass
    m = re.search(r"(\d{2}\.\d{2}\.\d{4})", s)
    if m:
        try:
            return datetime.strptime(m.group(1), "%d.%m.%Y").date()
        except ValueError:
            pass
    return None


def _looks_like_kad_material_url(url: str) -> bool:
    """Эвристика без импорта worker: любые ссылки kad.arbitr.ru на материалы/PDF."""
    h = (url or "").strip()
    low = h.lower()
    if "kad.arbitr.ru" not in low or not low.startswith("http"):
        return False
    if re.search(r"\.(png|jpe?g|gif|svg|css|js|woff2?|map)(\?|$|#)", low):
        return False
    tail = low.split("kad.arbitr.ru", 1)[-1].split("#")[0].split("?")[0]
    staticbits = ("scripts", "/bundles/", "/fonts/", "content/themes")
    if any(s in tail for s in staticbits):
        return False
    if ".pdf" in low or tail.endswith(".pdf"):
        return True
    docish = (
        "pdfdocument",
        "/document/pdf",
        "/document/view",
        "/document/content",
        "/kad/document",
        "/kad/file",
        "/file/",
        "contentdisposition=attachment",
        "disposition=attachment",
        "disposition=",
        "attachment",
        "download",
        "kad/pdfdocument",
        "/kad/pdf",
    )
    return any(bit in tail for bit in docish)


def _walk_parse_json_collect_kad_urls(
    root: Any, *, sink: dict[str, None], limit_nodes: int = 80_000
) -> None:
    stack: list[Any] = [root]
    n = 0
    while stack and n < limit_nodes:
        n += 1
        obj = stack.pop()
        if isinstance(obj, str):
            s = obj.strip()
            if s.startswith("http") and "kad.arbitr.ru" in s and _looks_like_kad_material_url(s):
                sink.setdefault(s.split("#")[0], None)
            continue
        if isinstance(obj, dict):
            stack.extend(obj.values())
        elif isinstance(obj, list):
            stack.extend(obj)


def extract_kad_pdf_url_entries_with_dates(data: dict[str, Any]) -> list[tuple[str, date | None]]:
    """Пары (url, дата документа по событию; для File инстанции — по макс. дате событий)."""
    out: list[tuple[str, date | None]] = []
    seen: set[str] = set()

    def add(u: str | None, d: date | None) -> None:
        if not u or not isinstance(u, str) or not u.startswith("http"):
            return
        if not _looks_like_kad_material_url(u):
            return
        if u in seen:
            return
        seen.add(u)
        out.append((u, d))

    for case in data.get("Cases") or []:
        for inst in case.get("CaseInstances") or []:
            event_dates: list[date] = []
            for ev in inst.get("InstanceEvents") or []:
                dt_raw = ev.get("Date") or ev.get("PublishDate") or ev.get("DisplayDate")
                ev_d = _parse_event_date(dt_raw if isinstance(dt_raw, str) else None)
                if ev_d:
                    event_dates.append(ev_d)
                ev_file = ev.get("File")
                if isinstance(ev_file, str):
                    add(ev_file, ev_d)
                elif isinstance(ev_file, dict):
                    raw_fu = (
                        ev_file.get("URL")
                        or ev_file.get("Url")
                        or ev_file.get("Href")
                        or ev_file.get("Link")
                        or ""
                    )
                    add(str(raw_fu).strip() or None, ev_d)
                for key in ("FileUrl", "PdfUrl", "DocumentUrl"):
                    vu = ev.get(key)
                    if isinstance(vu, str) and vu.strip():
                        add(vu.strip(), ev_d)

            ref_inst: date | None = max(event_dates) if event_dates else None

            f = inst.get("File")
            if isinstance(f, dict):
                add(f.get("URL") or f.get("Url"), ref_inst)
            elif isinstance(f, str):
                add(f, ref_inst)

            for doc in (
                list(inst.get("Documents") or [])
                + list(inst.get("CaseDocuments") or [])
                + list(inst.get("UploadedDocuments") or [])
            ):
                if not isinstance(doc, dict):
                    continue
                d_raw = (
                    doc.get("Date")
                    or doc.get("PublishDate")
                    or doc.get("DisplayDate")
                    or doc.get("EventDate")
                )
                dd = _parse_event_date(d_raw if isinstance(d_raw, str) else None)
                df = doc.get("File")
                if isinstance(df, dict):
                    add(df.get("URL") or df.get("Url"), dd or ref_inst)
                elif isinstance(df, str):
                    add(df, dd or ref_inst)
                du = doc.get("Url") or doc.get("URL") or doc.get("Link")
                add(du if isinstance(du, str) else None, dd or ref_inst)

    extra: dict[str, None] = {}
    _walk_parse_json_collect_kad_urls(data, sink=extra)
    for u in extra:
        if u not in seen:
            seen.add(u)
            out.append((u, None))
    return out


def extract_kad_pdf_urls_from_details(data: dict[str, Any]) -> list[str]:
    return [u for u, _ in extract_kad_pdf_url_entries_with_dates(data)]


def filter_pdf_urls_by_date_range(
    entries: list[tuple[str, date | None]],
    date_from: date | None,
    date_to: date | None,
) -> tuple[list[str], int]:
    """
    Оставляет URL, у которых дата попадает в [date_from; date_to].
    Если задан фильтр, а у URL нет даты, оставляет URL: Parser-API часто
    возвращает найденные в JSON PDF без даты события, и отбрасывание таких
    ссылок приводит к потере материалов.
    Возвращает (urls, included_no_date_count).
    """
    if date_from is None and date_to is None:
        return [u for u, _ in entries], 0

    skipped = 0
    out: list[str] = []
    seen: set[str] = set()
    lo = date_from or date.min
    hi = date_to or date.max

    for u, d in entries:
        if u in seen:
            continue
        if d is None:
            skipped += 1
            seen.add(u)
            out.append(u)
            continue
        if d < lo or d > hi:
            continue
        seen.add(u)
        out.append(u)
    return out, skipped


def case_dict_from_parser_case(case: dict[str, Any], card_url_hint: str | None = None) -> dict[str, Any]:
    cid = (case.get("CaseId") or "").strip()
    num = (case.get("CaseNumber") or "").strip()
    court = ""
    for inst in case.get("CaseInstances") or []:
        c = inst.get("Court") or {}
        if isinstance(c, dict) and c.get("Name"):
            court = str(c["Name"])
            break
    card_url = card_url_hint or (f"https://kad.arbitr.ru/Card/{cid}" if cid else "")
    title = num or (f"Дело {cid[:8]}…" if len(cid) > 8 else f"Дело {cid}")
    return {
        "remote_case_id": cid,
        "card_url": card_url,
        "case_number": num,
        "title": title,
        "court_name": court,
        "participants": [],
    }
