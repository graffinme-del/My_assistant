"""Parse document ids from chat without treating calendar dates as ids."""

from __future__ import annotations

import re

# 12.05, 12.05.2026, 1.2 — day.month[.year] / clause-like D.M tokens.
_DATE_OR_DOTTED_NUM = re.compile(r"\b\d{1,2}\.\d{1,2}(?:\.\d{2,4})?\b")

_RU_MONTH = (
    r"(?:январ(?:ь|я|е|ём|ем)|феврал(?:ь|я|е|ём|ем)|март(?:а|е|ом)?|"
    r"апрел(?:ь|я|е|ем)|ма(?:й|я|е|ем)|июн(?:ь|я|е|ем)|июл(?:ь|я|е|ем)|"
    r"август(?:а|е|ом)?|сентябр(?:ь|я|е|ём|ем)|октябр(?:ь|я|е|ём|ем)|"
    r"ноябр(?:ь|я|е|ём|ем)|декабр(?:ь|я|е|ём|ем))"
)

# 1 мая, 12 мая 2026, 1-го мая 2026 г.
_WRITTEN_RU_DATE = re.compile(
    rf"\b\d{{1,2}}(?:-го|-е)?\s+{_RU_MONTH}(?:\s+\d{{2,4}})?(?:\s*г\.?)?",
    re.IGNORECASE,
)

# «2026 года», «2026 год», «2026 г.»
_YEAR_WORD = re.compile(r"\b\d{4}\s*(?:год(?:а|у)?|г\.)", re.IGNORECASE)


def mask_date_like_tokens(text: str) -> str:
    """Replace calendar tokens so they cannot be parsed as document ids."""
    s = _DATE_OR_DOTTED_NUM.sub(" ", text or "")
    s = _WRITTEN_RU_DATE.sub(" ", s)
    s = _YEAR_WORD.sub(" ", s)
    return s


def parse_document_ids_for_delete_command(text: str) -> list[int]:
    """Ids from [123], doc:123, «документ 123». Dates like 1 мая / 12.05.2026 are not ids."""
    raw = text or ""
    ids = [int(x) for x in re.findall(r"\[(\d+)\]", raw)]
    ids.extend(int(x) for x in re.findall(r"(?i)\bdoc[.:]?\s*(\d+)\b", raw))
    if ids:
        return sorted(set(ids))
    safe = mask_date_like_tokens(raw)
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
    """Ids for «перенеси документ N …». Same date masking as delete."""
    raw = text or ""
    ids = [int(x) for x in re.findall(r"\[(\d+)\]", raw)]
    if ids:
        return ids
    safe = mask_date_like_tokens(raw)
    return [int(x) for x in re.findall(r"(?:документ|файл)\s+(\d+)", safe, flags=re.IGNORECASE)]
