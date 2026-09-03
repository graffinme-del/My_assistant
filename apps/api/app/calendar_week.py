"""Week-scoped chat: do not treat «эту неделю» / weekday / «1-й недели» as a folder wipe or document id."""

from __future__ import annotations

import re

# эту/текущую/прошлую/предыдущую неделю, этой недели, на этой неделе
_DEICTIC_WEEK = re.compile(
    r"(?:эт(?:а|у|ой)|текущ(?:ая|ую|ей)|прошл(?:ая|ую|ой)|предыдущ(?:ая|ую|ей))\s+"
    r"недел(?:я|и|ю|е|ей)"
    r"|(?:за|в|во|на)\s+"
    r"(?:эт(?:у|ой)|текущ(?:ую|ей)|прошл(?:ую|ой)|предыдущ(?:ую|ей))\s+"
    r"недел(?:я|и|ю|е|ей)",
    re.IGNORECASE,
)

_ORDINAL_WEEK_WORD = (
    r"(?:перв(?:ая|ую|ой|ый)|втор(?:ая|ую|ой|ый)|"
    r"трет(?:ья|ью|ьей|ий)|четв[её]рт(?:ая|ую|ой|ый))"
)

# «первая неделя», «за вторую неделю»
_ORDINAL_WEEK_WORD_SCOPED = re.compile(
    rf"(?:за|в|во|на)\s+{_ORDINAL_WEEK_WORD}\s+недел"
    rf"|\b{_ORDINAL_WEEK_WORD}\s+недел",
    re.IGNORECASE,
)

# «1-й недели», «за 2-ю неделю» — hyphen ordinal is not «N недель» (that is PR #67).
_ORDINAL_WEEK_NUM = re.compile(
    r"\b\d{1,2}(?:-?[йеяою])\s*недел",
    re.IGNORECASE,
)

_WEEKDAY = (
    r"(?:понедельник(?:а|у|ом|е)?|вторник(?:а|у|ом|е)?|"
    r"сред(?:а|у|ы|е|ой)|четверг(?:а|у|ом|е)?|"
    r"пятниц(?:а|у|ы|е|ой)|суббот(?:а|у|ы|е|ой)|"
    r"воскресень(?:е|я|ю|ем|и))"
)

# Require a preposition so a surname like «Среда» is not treated as a weekday.
_WEEKDAY_SCOPED = re.compile(
    rf"(?:за|в|во|на)\s+{_WEEKDAY}(?![а-яё])",
    re.IGNORECASE,
)

_WEEKEND_SCOPED = re.compile(
    r"(?:за|в|во|на)\s+выходн(?:ые|ых|ыми|ой|ую)?(?![а-яё])"
    r"|(?:документы?|файлы?)\s+выходн",
    re.IGNORECASE,
)

DELETE_REFUSED_WEEK = (
    "Не удаляю файлы по неделе вроде «за эту неделю» / «1-й недели» / «за понедельник» — "
    "это не номер документа и не команда очистить всю папку. "
    "Укажите id: «удали документ 214» или «удали документы [12] [18]». "
    "Чтобы очистить открытую папку целиком, напишите «удали все документы в этой папке» "
    "без указания недели."
)

MOVE_REFUSED_WEEK = (
    "Не переношу все файлы папки по неделе вроде «за эту неделю» / «1-й недели». "
    "Укажите id: «перенеси документ 214 в дело …». "
    "Чтобы перенести всю открытую папку, напишите без недели: "
    "«перенеси все документы в папку …»."
)


def mask_week_ordinals(text: str) -> str:
    """Replace «1-й недели» so the leading digit cannot be parsed as a document id."""
    return _ORDINAL_WEEK_NUM.sub(" ", text or "")


def looks_like_week_scoped_document_request(text: str) -> bool:
    """True when the user scoped files to this/last week, an ordinal week, a weekday, or the weekend."""
    raw = text or ""
    if (
        _DEICTIC_WEEK.search(raw)
        or _ORDINAL_WEEK_WORD_SCOPED.search(raw)
        or _ORDINAL_WEEK_NUM.search(raw)
        or _WEEKDAY_SCOPED.search(raw)
        or _WEEKEND_SCOPED.search(raw)
    ):
        return True
    return False


def week_blocks_bulk_document_mutation(
    text: str, *, explicit_document_ids: list[int] | None = None
) -> bool:
    """Refuse folder-wide delete/move when a week scope is present and no explicit [id] was given.

    Chat used to treat «удали все документы за эту неделю в этой папке» as wipe-the-folder
    because «все документы» matched wants_all and the week was ignored. «удали документы
    1-й недели» took the first digit as a document id.
    """
    if explicit_document_ids:
        return False
    return looks_like_week_scoped_document_request(text)


def parse_document_ids_for_delete_command(text: str) -> list[int]:
    """Ids from [123], doc:123, «документ 123». «1-й недели» is not an id."""
    raw = text or ""
    ids = [int(x) for x in re.findall(r"\[(\d+)\]", raw)]
    ids.extend(int(x) for x in re.findall(r"(?i)\bdoc[.:]?\s*(\d+)\b", raw))
    if ids:
        return sorted(set(ids))
    safe = mask_week_ordinals(raw)
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
    """Ids for «перенеси документ N …». Same week-ordinal masking as delete."""
    raw = text or ""
    ids = [int(x) for x in re.findall(r"\[(\d+)\]", raw)]
    if ids:
        return ids
    safe = mask_week_ordinals(raw)
    return [int(x) for x in re.findall(r"(?:документ|файл)\s+(\d+)", safe, flags=re.IGNORECASE)]
