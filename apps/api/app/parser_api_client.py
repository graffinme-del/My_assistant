"""
Клиент Parser-API (kad.arbitr.ru).

Документация (официально у провайдера):
- https://parser-api.com/kad-arbitr-ru#documentation
- https://parser-api.com/documentation/arbitr-api.txt
- https://parser-api.com/documentation/openapi/kad-arbitr-openapi.yaml

База методов arbitr_api: https://parser-api.com/parser/arbitr_api/...
Лимит и расход (JSON): https://parser-api.com/stat/?key=<ключ>
Статус сервисов: https://parser-api.com/status/ | https://parser-api.com/status/?format=json
Телеграм-бот учёта/уведомлений: https://t.me/parser_api_bot

Ключ только в переменной PARSER_API_KEY (.env), не коммитить.
"""

from __future__ import annotations

import base64
import json
import logging
from typing import Any

import httpx

from .config import settings

logger = logging.getLogger(__name__)

DEFAULT_BASE = "https://parser-api.com/parser/arbitr_api"
STAT_URL = "https://parser-api.com/stat/"
STATUS_URL = "https://parser-api.com/status/"


def _base_url() -> str:
    return (getattr(settings, "parser_api_base_url", None) or DEFAULT_BASE).rstrip("/")


def _api_key() -> str:
    key = (getattr(settings, "parser_api_key", None) or "").strip()
    if not key:
        raise ValueError("PARSER_API_KEY не задан в окружении (.env)")
    return key


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
    """Поиск дел (параметры как в доке Parser-API)."""
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


def parser_details_by_number(case_number: str) -> dict[str, Any]:
    """Детальная информация по номеру дела."""
    return _request("details_by_number", {"CaseNumber": case_number})


def parser_details_by_id(case_id: str) -> dict[str, Any]:
    """Детальная информация по UUID дела (CaseId)."""
    return _request("details_by_id", {"CaseId": case_id})


def parser_pdf_download(pdf_url: str) -> bytes:
    """
    Скачивание PDF по полному URL с kad.arbitr.ru (как в доке — параметр url).
    Возвращает бинарное содержимое (после base64 из ответа).
    """
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


def _request(endpoint: str, params: dict[str, Any]) -> dict[str, Any]:
    url = f"{_base_url()}/{endpoint}"
    q = {"key": _api_key(), **{k: v for k, v in params.items() if v is not None}}
    timeout = float(settings.parser_api_timeout_sec or 120)
    with httpx.Client(timeout=timeout) as client:
        r = client.get(url, params=q)
        r.raise_for_status()
        return r.json()


def parser_usage_stat() -> dict[str, Any]:
    """Текущий лимит и расход запросов (JSON по ключу).

    Провайдер иногда отдаёт массив (например [] для нового ключа) — оборачиваем в dict,
    чтобы FastAPI не падал на аннотации ответа.
    """
    with httpx.Client(timeout=30.0) as client:
        r = client.get(STAT_URL, params={"key": _api_key()})
        r.raise_for_status()
        data = r.json()
    if isinstance(data, dict):
        return data
    return {"stat": data}


def parser_service_status_json() -> dict[str, Any]:
    """Статус сервисов Parser-API (без ключа)."""
    with httpx.Client(timeout=15.0) as client:
        r = client.get(STATUS_URL, params={"format": "json"})
        r.raise_for_status()
        return r.json()


def extract_kad_pdf_urls_from_details(data: dict[str, Any]) -> list[str]:
    """Собирает URL на PdfDocument с kad.arbitr.ru из ответа details_*."""
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
