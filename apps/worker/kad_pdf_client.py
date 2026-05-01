"""Кад (kad.arbitr.ru): скачивание PDF через вьювер /Document/Pdf/ с полями stamp token+hash.

Поля одноразовые — живут только в памяти на время запроса, не пишем их в журналы задач."""

from __future__ import annotations

import json
import re
from urllib.parse import quote_plus

KAD_ORIGIN = "https://kad.arbitr.ru"


def is_kad_document_pdf_viewer_url(url: str) -> bool:
    u = (url or "").lower()
    return "kad.arbitr.ru" in u and "/document/pdf/" in u


_TOKEN_RE = re.compile(r'"token"\s*:\s*"(\d{4,})"', re.IGNORECASE)
_HASH_RE = re.compile(r'"hash"\s*:\s*"([a-f0-9]{8,})"', re.IGNORECASE)


def extract_kad_pdf_stamp_fields(html: str) -> tuple[str, str] | None:
    """
    Выдираем token/hash из HTML вьюверa (до POST на тот же URL).
    """
    if not html:
        return None
    mt = _TOKEN_RE.search(html)
    mh = _HASH_RE.search(html)
    if mt and mh:
        return mt.group(1), mh.group(1)
    return None


def _encode_kad_pdf_stamp_body(token: str, hash_hex: str) -> bytes:
    """
    telo как в браузере: один url-encoded JSON + '=' (value пустое), content-type www-form-urlencoded.
    """
    s = quote_plus(json.dumps({"token": token, "hash": hash_hex}, separators=(",", ":"), ensure_ascii=False)) + "="
    return s.encode("utf-8")


def download_kad_document_pdf_via_api(
    api,
    viewer_url: str,
    *,
    referer: str,
    timeout_ms: int = 180_000,
    _depth: int = 0,
) -> tuple[bytes, str]:
    """
    GET по viewer_url → PDF или HTML c token/hash → POST → PDF.
    api: Playwright ``BrowserContext.request`` (APIRequestContext).
    Возвращает (bytes, имя файла из URL или заголовка content-disposition).
    """
    if _depth > 4:
        raise RuntimeError("Слишком много переходов при разборе вьюверa КАД")
    vu = viewer_url.strip()
    if not vu:
        raise RuntimeError("Пустой URL документа КАД")
    headers = {"Referer": referer.strip() if referer else f"{KAD_ORIGIN}/", "Accept": "*/*"}
    r = api.get(vu, timeout=timeout_ms, headers=headers)
    if not r.ok:
        raise RuntimeError(f"КАД: GET вьювер: HTTP {r.status}")
    body = r.body()
    ct = (r.headers.get("content-type") or "").split(";")[0].strip().lower()
    if len(body) >= 4 and body[:4] == b"%PDF":
        return body, _filename_from_pdf_response(vu, r.headers)

    htmlish = ct.startswith("text/html") or body[:100].strip().startswith(b"<")
    if not htmlish:
        raise RuntimeError(f"КАД: ожидали PDF/HTML вьювер, пришёл {ct or '?'} ({len(body)} байт)")

    html = body.decode("utf-8", errors="ignore")
    fields = extract_kad_pdf_stamp_fields(html)
    if not fields:
        raise RuntimeError("КАД: в HTML вьюверa не найдены token/hash для штампованной выдачи")

    token, stamp_hash = fields
    post_headers = {
        **headers,
        "Content-Type": "application/x-www-form-urlencoded",
        "Origin": KAD_ORIGIN,
    }
    r2 = api.post(
        vu,
        headers=post_headers,
        data=_encode_kad_pdf_stamp_body(token, stamp_hash),
        timeout=timeout_ms,
    )
    if not r2.ok:
        raise RuntimeError(f"КАД: POST stamped PDF: HTTP {r2.status}")
    bin2 = r2.body()
    ct2 = (r2.headers.get("content-type") or "").split(";")[0].strip().lower()
    if ct2.endswith("pdf") or len(bin2) >= 4 and bin2[:4] == b"%PDF":
        return bin2, _filename_from_pdf_response(vu, r2.headers)
    nested = _extract_embedded_pdf_url(bin2.decode("utf-8", errors="ignore"))
    if nested and nested != vu:
        return download_kad_document_pdf_via_api(api, nested, referer=vu, timeout_ms=timeout_ms, _depth=_depth + 1)
    raise RuntimeError("КАД: после POST вместо PDF пришёл неожиданный ответ")


def _filename_from_pdf_response(viewer_url: str, header_map: dict) -> str:
    cd = header_map.get("content-disposition", "")
    match = re.search(r'filename="?([^";]+)"?', cd, flags=re.IGNORECASE)
    if match:
        return match.group(1).strip()
    slug = viewer_url.split("/Document/Pdf/")[-1].split("/")[-1].split("?")[0].strip()
    if slug.lower().endswith(".pdf"):
        return slug
    return "document.pdf"


def _extract_embedded_pdf_url(html: str) -> str | None:
    for p in (
        r'src="(https://kad\.arbitr\.ru[^"]+\.pdf[^"]*)"',
        r'href="(https://kad\.arbitr\.ru[^"]+\.pdf[^"]*)"',
    ):
        m = re.search(p, html, flags=re.IGNORECASE)
        if m:
            return m.group(1)
    return None


def kad_search_instances_body(case_numbers: list[str], *, page: int = 1, count: int = 25) -> dict:
    """
    Структура тела POST /Kad/SearchInstances из trace (можно использовать в прямых API в будущем).
    Требует сессионные cookie и antifraud (wasm) как в браузере.
    """
    nums = [(n or "").strip() for n in case_numbers if (n or "").strip()]
    return {
        "Page": page,
        "Count": count,
        "Courts": [],
        "DateFrom": None,
        "DateTo": None,
        "Sides": [],
        "Judges": [],
        "CaseNumbers": nums,
        "WithVKSInstances": False,
    }
