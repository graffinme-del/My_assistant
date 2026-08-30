"""Parse document ids from chat without treating relative time as an id."""

from __future__ import annotations

import re

# «3 дня», «2 недели назад», «5 часов», «1.5 дня», «10 минут»
_RELATIVE_TIME_QTY = re.compile(
    r"\b\d{1,4}(?:[.,]\d{1,2})?\s+"
    r"(?:"
    r"дн(?:ей|я|ём|е)?|день|суток|"
    r"недел[яиью]|"
    r"час(?:а|ов|у)?|"
    r"минут[аыу]?|"
    r"секунд[аыу]?|"
    r"месяц(?:а|ев|у)?|"
    r"год(?:а|ов|у)?|лет"
    r")\b",
    re.IGNORECASE,
)


def mask_relative_time_quantities(text: str) -> str:
    """Replace «N дней/недель/часов…» so the number cannot be parsed as a document id."""
    return _RELATIVE_TIME_QTY.sub(" ", text or "")


def looks_like_relative_time_scoped_document_request(text: str) -> bool:
    """True when the user scoped the request to a relative period (not an explicit id)."""
    return bool(_RELATIVE_TIME_QTY.search(text or ""))


def parse_document_ids_for_delete_command(text: str) -> list[int]:
    """Ids from [123], doc:123, «документ 123». «3 дня назад» is not an id."""
    raw = text or ""
    ids = [int(x) for x in re.findall(r"\[(\d+)\]", raw)]
    ids.extend(int(x) for x in re.findall(r"(?i)\bdoc[.:]?\s*(\d+)\b", raw))
    if ids:
        return sorted(set(ids))
    safe = mask_relative_time_quantities(raw)
    m = re.search(
        r"(?:документы?|файлы?)(?:\s+(?:с\s+)?id|\s+№|\s+#)?\s*[:.]?\s*([\d\s,;и]+)",
        safe,
        flags=re.IGNORECASE,
    )
    if m:
        found = {int(x) for x in re.findall(r"\d+", m.group(1))}
        if found:
            return sorted(found)
    m2 = re.search(r"(?:документ|файл)\s*(?:№|#)?\s*(\d+)\b", safe, flags=re.IGNORECASE)
    if m2:
        return [int(m2.group(1))]
    return []


def parse_document_ids_for_move_command(text: str) -> list[int]:
    """Ids for «перенеси документ N …». Same relative-time masking as delete."""
    raw = text or ""
    ids = [int(x) for x in re.findall(r"\[(\d+)\]", raw)]
    if ids:
        return ids
    safe = mask_relative_time_quantities(raw)
    return [int(x) for x in re.findall(r"(?:документ|файл)\s+(\d+)", safe, flags=re.IGNORECASE)]
