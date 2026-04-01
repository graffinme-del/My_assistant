from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass
class CourtSearchRequest:
    query_type: str
    query_value: str
    run_mode: str = "preview"


def normalize_query_value(value: str) -> str:
    return re.sub(r"\s+", " ", (value or "").strip())


def normalize_case_number(value: str) -> str:
    return normalize_query_value(value).replace(" ", "").replace("\\", "")


def normalize_inn(value: str) -> str:
    return re.sub(r"\D+", "", value or "")


def normalize_ogrn(value: str) -> str:
    return re.sub(r"\D+", "", value or "")


def parse_court_search_request(text: str) -> CourtSearchRequest | None:
    raw = normalize_query_value(text)
    lowered = raw.lower()

    m_case = re.search(r"(?:дел[ауо]?|дела)\s+([АA]\d{1,4}-\d{1,7}/\d{2,4}|\d{1,2}-\d{1,7}/\d{2,4})", raw, flags=re.IGNORECASE)
    if any(marker in lowered for marker in ["скачай документы дела", "найди дело", "поставь на отслеживание дело"]) and m_case:
        return CourtSearchRequest(query_type="case_number", query_value=normalize_case_number(m_case.group(1)))

    m_inn = re.search(r"\bинн\b[:\s]*([\d\s]{10,15})", lowered, flags=re.IGNORECASE)
    if m_inn:
        return CourtSearchRequest(query_type="inn", query_value=normalize_inn(m_inn.group(1)))

    m_ogrn = re.search(r"\bогрн\b[:\s]*([\d\s]{12,18})", lowered, flags=re.IGNORECASE)
    if m_ogrn:
        return CourtSearchRequest(query_type="ogrn", query_value=normalize_ogrn(m_ogrn.group(1)))

    org_markers = [
        "по организации",
        "организацию",
        "организации",
        "компанию",
        "по компании",
        "поставь на отслеживание организацию",
    ]
    if any(marker in lowered for marker in org_markers):
        candidate = raw
        for marker in org_markers:
            idx = lowered.find(marker)
            if idx >= 0:
                candidate = raw[idx + len(marker):].strip(" :.-\"«»")
                break
        if candidate:
            return CourtSearchRequest(query_type="organization_name", query_value=candidate)
    return None


def looks_like_court_search_command(text: str) -> bool:
    lowered = text.lower()
    return any(
        marker in lowered
        for marker in [
            "скачай документы дела",
            "найди дела по",
            "найди дело",
            "поставь на отслеживание дело",
            "поставь на отслеживание инн",
            "поставь на отслеживание огрн",
            "поставь на отслеживание организацию",
            "статус синхронизации",
            "что нового скачано за ночь",
        ]
    )
