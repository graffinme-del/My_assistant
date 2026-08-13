"""Разбор заметок о заседании: не путать пункты (п. 1.2) с датой следующего заседания."""

from __future__ import annotations

import re
from datetime import date

# Явные признаки протокола/переноса заседания — не общие слова вроде «судья» / «доказательств».
_HEARING_MARKERS = (
    "заседан",
    "отлож",
    "слушани",
    "приобщ",
    "залуч",
    "назначен срок",
)

_DATE_RE = re.compile(r"(\d{1,2})\.(\d{1,2})(?:\.(\d{2,4}))?")
_CLAUSE_PREFIX_RE = re.compile(
    r"(?:^|[^\wа-яё])(?:п(?:п)?|пункт[а-яё]*)\.?\s*$",
    flags=re.IGNORECASE,
)


def looks_like_hearing_note(text: str) -> bool:
    """True только при явных маркерах заседания — не по любой паре цифр «1.2»."""
    t = (text or "").lower()
    if not t.strip():
        return False
    return any(k in t for k in _HEARING_MARKERS)


def _is_clause_number(text: str, match_start: int) -> bool:
    prefix = text[max(0, match_start - 12) : match_start]
    return bool(_CLAUSE_PREFIX_RE.search(prefix))


def _parse_match(match: re.Match[str], *, allow_yearless: bool) -> date | None:
    day = int(match.group(1))
    month = int(match.group(2))
    year_raw = match.group(3)
    if year_raw is None and not allow_yearless:
        return None
    year = int(year_raw) if year_raw else date.today().year
    if year < 100:
        year += 2000
    try:
        return date(year, month, day)
    except ValueError:
        return None


def _near_hearing_marker(text: str, start: int, end: int, *, window: int = 48) -> bool:
    lo = max(0, start - window)
    hi = min(len(text), end + window)
    blob = text[lo:hi].lower()
    return any(k in blob for k in _HEARING_MARKERS)


def extract_hearing_date(text: str) -> date | None:
    """
    Дата следующего заседания.

    Предпочитает полные даты с годом (20.09.2026). Пункты вроде «п. 1.2» игнорируются.
    Даты без года принимаются только рядом с маркером заседания.
    """
    raw = text or ""
    dated: list[date] = []
    yearless: list[date] = []
    for match in _DATE_RE.finditer(raw):
        if _is_clause_number(raw, match.start()):
            continue
        if match.group(3):
            parsed = _parse_match(match, allow_yearless=False)
            if parsed:
                dated.append(parsed)
            continue
        if not _near_hearing_marker(raw, match.start(), match.end()):
            continue
        parsed = _parse_match(match, allow_yearless=True)
        if parsed:
            yearless.append(parsed)
    if dated:
        return dated[-1]
    if yearless:
        return yearless[-1]
    return None


def apply_hearing_date_to_case(case: object, text: str) -> date | None:
    """Ставит next_hearing_date только если из текста извлечена календарная дата заседания."""
    extracted = extract_hearing_date(text)
    if extracted is not None:
        case.next_hearing_date = extracted  # type: ignore[attr-defined]
    return extracted
