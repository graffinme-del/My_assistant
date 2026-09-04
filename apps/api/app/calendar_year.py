"""Calendar-year chat scope: do not treat «2025 год» as a folder wipe or document id."""

from __future__ import annotations

import re

# Four-digit years in the range people actually mean as a calendar year.
_YEAR_4 = r"(?:19|20)\d{2}"
_YEAR_WORD = r"(?:год(?:а|у)?|г\.?)"

# «2025 год», «2025 года», «2025 г.», «2025г»
_YEAR_WITH_WORD = re.compile(
    rf"{_YEAR_4}\s*{_YEAR_WORD}(?![а-яё])",
    re.IGNORECASE,
)

# «за 2025», «в 2025», «с 2024» — not the «/2025» tail of a case number.
_PREP_YEAR = re.compile(
    rf"(?:за|в|во|с)\s+{_YEAR_4}(?!\s*/)",
    re.IGNORECASE,
)

# «с 2024 по 2026», «с 2024 г. по 2026 г.»
_YEAR_RANGE = re.compile(
    rf"с\s+{_YEAR_4}(?:\s*{_YEAR_WORD})?\s+по\s+{_YEAR_4}",
    re.IGNORECASE,
)

# Filing-style two-digit year: «25 года», «25 год» (not bare «25»).
_SHORT_YEAR = re.compile(
    r"\b\d{2}\s+год(?:а|у)?(?![а-яё])",
    re.IGNORECASE,
)

# Strip these before reading «документ N» so «2025 года» is not id 2025.
_YEAR_MASK = re.compile(
    rf"с\s+{_YEAR_4}(?:\s*{_YEAR_WORD})?\s+по\s+{_YEAR_4}"
    rf"|{_YEAR_4}\s*{_YEAR_WORD}(?![а-яё])"
    rf"|(?:за|в|во|с)\s+{_YEAR_4}(?!\s*/)"
    rf"|\b\d{{2}}\s+год(?:а|у)?(?![а-яё])",
    re.IGNORECASE,
)

DELETE_REFUSED_YEAR = (
    "Не удаляю файлы по календарному году вроде «за 2025 год» / «2025 года» — "
    "это не номер документа и не команда очистить всю папку. "
    "Укажите id: «удали документ 214» или «удали документы [12] [18]». "
    "Чтобы очистить открытую папку целиком, напишите «удали все документы в этой папке» "
    "без года."
)

MOVE_REFUSED_YEAR = (
    "Не переношу все файлы папки по календарному году вроде «за 2025 год» / «2025 года». "
    "Укажите id: «перенеси документ 214 в дело …». "
    "Чтобы перенести всю открытую папку, напишите без года: "
    "«перенеси все документы в папку …»."
)


def mask_calendar_years(text: str) -> str:
    """Replace «2025 года» / «за 2025» so they cannot be parsed as document ids."""
    return _YEAR_MASK.sub(" ", text or "")


def looks_like_year_scoped_document_request(text: str) -> bool:
    """True when the user scoped files to a calendar year or year range."""
    raw = text or ""
    if _YEAR_RANGE.search(raw) or _YEAR_WITH_WORD.search(raw) or _PREP_YEAR.search(raw) or _SHORT_YEAR.search(raw):
        return True
    return False


def year_blocks_bulk_document_mutation(
    text: str, *, explicit_document_ids: list[int] | None = None
) -> bool:
    """Refuse folder-wide delete/move when a calendar year is present and no explicit [id] was given.

    Chat used to treat «удали все документы за 2025 год в этой папке» as wipe-the-folder because
    «все документы» matched wants_all and the year was ignored. «удали документы 2025 года»
    took 2025 as a document id.
    """
    if explicit_document_ids:
        return False
    return looks_like_year_scoped_document_request(text)


def parse_document_ids_for_delete_command(text: str) -> list[int]:
    """Ids from [123], doc:123, «документ 123». «2025 года» is not an id."""
    raw = text or ""
    ids = [int(x) for x in re.findall(r"\[(\d+)\]", raw)]
    ids.extend(int(x) for x in re.findall(r"(?i)\bdoc[.:]?\s*(\d+)\b", raw))
    if ids:
        return sorted(set(ids))
    safe = mask_calendar_years(raw)
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
    """Ids for «перенеси документ N …». Same year masking as delete."""
    raw = text or ""
    ids = [int(x) for x in re.findall(r"\[(\d+)\]", raw)]
    if ids:
        return ids
    safe = mask_calendar_years(raw)
    return [int(x) for x in re.findall(r"(?:документ|файл)\s+(\d+)", safe, flags=re.IGNORECASE)]
