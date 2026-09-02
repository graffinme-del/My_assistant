"""Month / quarter chat scope: do not treat «март» or «1 квартал» as a folder wipe or document id."""

from __future__ import annotations

import re

# Russian month stems (nom/gen/prep) so «за март» is a period, not a folder wipe.
_RU_MONTH = (
    r"(?:январ(?:ь|я|е|ём|ем)|феврал(?:ь|я|е|ём|ем)|март(?:а|е|ом)?|"
    r"апрел(?:ь|я|е|ем)|ма(?:й|я|е|ем)|июн(?:ь|я|е|ем)|июл(?:ь|я|е|ем)|"
    r"август(?:а|е|ом)?|сентябр(?:ь|я|е|ём|ем)|октябр(?:ь|я|е|ём|ем)|"
    r"ноябр(?:ь|я|е|ём|ем)|декабр(?:ь|я|е|ём|ем))(?![а-яё])"
)

# «за март», «в январе», «за май 2025», «март 2025», «документы марта»
_MONTH_SCOPED = re.compile(
    rf"(?:за|в|во)\s+{_RU_MONTH}"
    rf"|{_RU_MONTH}\s+(?:\d{{4}}|месяц(?:а|е)?)"
    rf"|(?:документы?|файлы?)\s+{_RU_MONTH}",
    re.IGNORECASE,
)

# «за этот месяц», «в этом квартале», «документы этого месяца», «за месяц» / «за год»
_THIS_PERIOD = re.compile(
    r"(?:эт(?:от|ом|у|им|ого)|текущ(?:ий|ем|его|ую|им))\s+"
    r"(?:месяц(?:а|е)?|год(?:а|у)?|квартал(?:а|е)?)"
    r"|(?:за|в|во)\s+(?:месяц(?:а|е)?|год(?:а|у)?|квартал(?:а|е)?)(?![а-яё])",
    re.IGNORECASE,
)

_QUARTER_WORD = (
    r"(?:квартал(?:а|е|у|ом)?|кв\.)"
)
_QUARTER_ORDINAL_WORD = (
    r"(?:перв(?:ый|ого|ом|ое)|втор(?:ой|ого|ом|ое)|"
    r"трет(?:ий|ьего|ьем|ье)|четв[её]рт(?:ый|ого|ом|ое))"
)

# «за 1 квартал», «во 2 квартале», «1-й квартал», «первый квартал», «1 полугодия»
_QUARTER_SCOPED = re.compile(
    rf"(?:за|в|во)\s+(?:[1-4]|[IV]{{1,3}}|{_QUARTER_ORDINAL_WORD})\s*{_QUARTER_WORD}"
    rf"|\b[1-4](?:-?[йеяо])?\s*{_QUARTER_WORD}"
    rf"|\b{_QUARTER_ORDINAL_WORD}\s+квартал"
    rf"|\b[12](?:-?[йеяо])?\s*полугод(?:ие|ия|ии|ием)"
    rf"|\b(?:перв(?:ое|ого)|втор(?:ое|ого))\s+полугод",
    re.IGNORECASE,
)

# Strip these before reading «документ N» so «1 квартала» is not id 1.
_QUARTER_ORDINAL_MASK = re.compile(
    rf"\b[1-4](?:-?[йеяо])?\s*{_QUARTER_WORD}"
    rf"|\b[12](?:-?[йеяо])?\s*полугод(?:ие|ия|ии|ием)",
    re.IGNORECASE,
)

DELETE_REFUSED_MONTH_QUARTER = (
    "Не удаляю файлы по месяцу или кварталу вроде «за март» / «1 квартала» — "
    "это не номер документа и не команда очистить всю папку. "
    "Укажите id: «удали документ 214» или «удали документы [12] [18]». "
    "Чтобы очистить открытую папку целиком, напишите «удали все документы в этой папке» "
    "без месяца и квартала."
)

MOVE_REFUSED_MONTH_QUARTER = (
    "Не переношу все файлы папки по месяцу или кварталу вроде «за март» / «1 квартала». "
    "Укажите id: «перенеси документ 214 в дело …». "
    "Чтобы перенести всю открытую папку, напишите без месяца и квартала: "
    "«перенеси все документы в папку …»."
)


def mask_quarter_halfyear_ordinals(text: str) -> str:
    """Replace «1 квартал» / «2 полугодия» so they cannot be parsed as document ids."""
    return _QUARTER_ORDINAL_MASK.sub(" ", text or "")


def looks_like_month_or_quarter_scoped_document_request(text: str) -> bool:
    """True when the user scoped files to a calendar month, quarter, half-year, or «этот месяц»."""
    raw = text or ""
    if _MONTH_SCOPED.search(raw) or _THIS_PERIOD.search(raw) or _QUARTER_SCOPED.search(raw):
        return True
    return False


def month_or_quarter_blocks_bulk_document_mutation(
    text: str, *, explicit_document_ids: list[int] | None = None
) -> bool:
    """Refuse folder-wide delete/move when a month/quarter is present and no explicit [id] was given.

    Chat used to treat «удали все документы за март в этой папке» as wipe-the-folder because
    «все документы» matched wants_all and the month was ignored. «удали документы 1 квартала»
    took the first digit as a document id.
    """
    if explicit_document_ids:
        return False
    return looks_like_month_or_quarter_scoped_document_request(text)


def parse_document_ids_for_delete_command(text: str) -> list[int]:
    """Ids from [123], doc:123, «документ 123». «1 квартала» is not an id."""
    raw = text or ""
    ids = [int(x) for x in re.findall(r"\[(\d+)\]", raw)]
    ids.extend(int(x) for x in re.findall(r"(?i)\bdoc[.:]?\s*(\d+)\b", raw))
    if ids:
        return sorted(set(ids))
    safe = mask_quarter_halfyear_ordinals(raw)
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
    """Ids for «перенеси документ N …». Same quarter masking as delete."""
    raw = text or ""
    ids = [int(x) for x in re.findall(r"\[(\d+)\]", raw)]
    if ids:
        return ids
    safe = mask_quarter_halfyear_ordinals(raw)
    return [int(x) for x in re.findall(r"(?:документ|файл)\s+(\d+)", safe, flags=re.IGNORECASE)]
