"""Parse document ids from chat without treating clock times or slash/ISO dates as ids."""

from __future__ import annotations

import re

# 15:00, 9:05, 15:00:01
_CLOCK_TIME = re.compile(r"\b\d{1,2}:\d{2}(?::\d{2})?\b")

# 15/03/2026, 15/03 — same D/M[/Y] form as ru_date_range._RE_DMY
_SLASH_DATE = re.compile(r"\b\d{1,2}/\d{1,2}(?:/\d{2,4})?\b")

# 2026-03-15
_ISO_DATE = re.compile(r"\b\d{4}-\d{1,2}-\d{1,2}\b")

# 15-03-2026 (day-month-year with hyphens). Not 15-18 (id range).
_HYPHEN_DMY = re.compile(r"\b\d{1,2}-\d{1,2}-\d{2,4}\b")

# 15 числа, 15-го числа, 15-е число
_DAY_CHISLA = re.compile(
    r"\b\d{1,2}(?:-го|-е|-й|-я)?\s+числ[аеуо]\b",
    re.IGNORECASE,
)

# 15-го (genitive ordinal used as a calendar day when the month is omitted)
_GENITIVE_ORDINAL_DAY = re.compile(r"\b\d{1,2}-го\b", re.IGNORECASE)


def mask_clock_and_slash_iso_date_tokens(text: str) -> str:
    """Replace clock / slash / ISO / «N числа» tokens so they cannot be parsed as document ids."""
    s = _CLOCK_TIME.sub(" ", text or "")
    s = _ISO_DATE.sub(" ", s)
    s = _SLASH_DATE.sub(" ", s)
    s = _HYPHEN_DMY.sub(" ", s)
    s = _DAY_CHISLA.sub(" ", s)
    s = _GENITIVE_ORDINAL_DAY.sub(" ", s)
    return s


def looks_like_clock_or_slash_iso_date_scoped_document_request(text: str) -> bool:
    """True when the user scoped the request to a clock time or slash/ISO/«N числа» date."""
    raw = text or ""
    return bool(
        _CLOCK_TIME.search(raw)
        or _ISO_DATE.search(raw)
        or _SLASH_DATE.search(raw)
        or _HYPHEN_DMY.search(raw)
        or _DAY_CHISLA.search(raw)
        or _GENITIVE_ORDINAL_DAY.search(raw)
    )


def parse_document_ids_for_delete_command(text: str) -> list[int]:
    """Ids from [123], doc:123, «документ 123». «15:00» / «15/03/2026» / «15 числа» are not ids."""
    raw = text or ""
    ids = [int(x) for x in re.findall(r"\[(\d+)\]", raw)]
    ids.extend(int(x) for x in re.findall(r"(?i)\bdoc[.:]?\s*(\d+)\b", raw))
    if ids:
        return sorted(set(ids))
    safe = mask_clock_and_slash_iso_date_tokens(raw)
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
    """Ids for «перенеси документ N …». Same clock/date masking as delete."""
    raw = text or ""
    ids = [int(x) for x in re.findall(r"\[(\d+)\]", raw)]
    if ids:
        return ids
    safe = mask_clock_and_slash_iso_date_tokens(raw)
    return [int(x) for x in re.findall(r"(?:документ|файл)\s+(\d+)", safe, flags=re.IGNORECASE)]
