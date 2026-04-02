"""
Parser-API в worker: те же методы, что в apps/api/app/parser_api_client.py,
но настройки только из окружения (без импорта FastAPI-приложения).
"""

from __future__ import annotations

import base64
import os
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
        r.raise_for_status()
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
        err = data.get("error") or data.get("Error") or "unknown"
        raise RuntimeError(f"Parser-API pdf_download: {err}")
    b64 = data.get("pdfContent")
    if not b64:
        raise RuntimeError("Parser-API: pdfContent пуст")
    return base64.b64decode(b64)


def extract_kad_pdf_urls_from_details(data: dict[str, Any]) -> list[str]:
    urls: list[str] = []
    seen: set[str] = set()

    def add(u: str | None) -> None:
        if not u or not isinstance(u, str) or not u.startswith("http"):
            return
        if u in seen:
            return
        seen.add(u)
        urls.append(u)

    for case in data.get("Cases") or []:
        for inst in case.get("CaseInstances") or []:
            f = inst.get("File")
            if isinstance(f, dict):
                add(f.get("URL"))
            elif isinstance(f, str):
                add(f)
            for ev in inst.get("InstanceEvents") or []:
                add(ev.get("File") if isinstance(ev.get("File"), str) else None)
    return urls


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
