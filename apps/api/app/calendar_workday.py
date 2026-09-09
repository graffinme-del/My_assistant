"""Workday-class chat scope: do not treat «за будни» / «за рабочие дни» as a folder wipe."""

from __future__ import annotations

import re

# Noun after a time preposition: «за будни», «по будням», «на буднях».
_BUDNY_NOUN = r"(?:будн(?:и|ей|ям|ями|ях|я|ю|ем)?)"

# «будние документы» — weekday files, not a folder titled «Будни».
_BUDNY_ADJ = (
    r"(?:будн(?:ий|яя|ее|ие|его|ему|им|ем|юю|ей|их|ими))"
)

# «рабочие дни» / «будний день» — not «рабочие документы» (working files).
_WORKDAY_ADJ = (
    r"(?:(?:рабоч(?:ий|ая|ее|ие|его|ему|им|ем|ую|ей|их|ими))"
    r"|(?:будн(?:ий|яя|ее|ие|его|ему|им|ем|юю|ей|их|ими)))"
)
_DAY_NOUN = r"(?:день|дня|дню|днём|днем|дне|дни|дней|дням|днями|днях)"

# «в рабочее время», «за рабочие часы».
_WORK_TIME = (
    r"(?:рабоч(?:ее|его|ем|им)\s+(?:время|времени|временем)"
    r"|рабоч(?:ие|их|ими|им)\s+час(?:ы|ов|ам|ами|ах)?)"
)

_DEMONSTRATIVE = r"(?:это|эти|этих|этими|этот|этой|этом|прошл\w{0,4}|текущ\w{0,4}|данн\w{0,4}|сво\w{0,4})\s+"

# Wrap the demonstrative: `{_DEMONSTRATIVE}?` would make only the trailing `\s+` optional.
_PREP_BUDNY = re.compile(
    rf"(?:за|на|в|во|по)\s+(?:{_DEMONSTRATIVE})?{_BUDNY_NOUN}(?![а-яё])",
    re.IGNORECASE,
)

_PREP_WORKDAY = re.compile(
    rf"(?:за|на|в|во|по)\s+(?:{_DEMONSTRATIVE})?{_WORKDAY_ADJ}\s+{_DAY_NOUN}(?![а-яё])",
    re.IGNORECASE,
)

_PREP_WORK_TIME = re.compile(
    rf"(?:за|на|в|во|по)\s+(?:{_DEMONSTRATIVE})?{_WORK_TIME}(?![а-яё])",
    re.IGNORECASE,
)

_DURING_WORKDAY = re.compile(
    rf"во\s+время\s+(?:{_DEMONSTRATIVE})?"
    rf"(?:{_BUDNY_NOUN}|{_WORKDAY_ADJ}\s+{_DAY_NOUN}|{_WORK_TIME})(?![а-яё])",
    re.IGNORECASE,
)

_DEMONSTRATIVE_WORKDAY = re.compile(
    rf"(?:эти|этих|этими|этот|этого|этом|прошлые|прошлых|прошлый|текущие|текущих|текущий|данные|данных)\s+"
    rf"(?:{_BUDNY_NOUN}|{_WORKDAY_ADJ}\s+{_DAY_NOUN}|{_WORK_TIME})(?![а-яё])",
    re.IGNORECASE,
)

# «будние документы» / «документы будние» — collocation, not a folder title.
_BUDNY_ADJ_DOCS = re.compile(
    rf"(?:{_BUDNY_ADJ}\s+(?:документ|файл)\w*|(?:документ|файл)\w*\s+{_BUDNY_ADJ})(?![а-яё])",
    re.IGNORECASE,
)

DELETE_REFUSED_WORKDAY = (
    "Не удаляю файлы по будням или рабочим дням вроде «за будни» / «за рабочие дни» / "
    "«в рабочее время» / «будние документы» — это не номер документа и не команда очистить всю папку. "
    "Укажите id: «удали документ 214» или «удали документы [12] [18]». "
    "Чтобы очистить открытую папку целиком, напишите «удали все документы в этой папке» "
    "без будней и рабочих дней."
)

MOVE_REFUSED_WORKDAY = (
    "Не переношу все файлы папки по будням или рабочим дням вроде «за будни» / "
    "«за рабочие дни» / «в рабочее время» / «будние документы». "
    "Укажите id: «перенеси документ 214 в дело …». "
    "Чтобы перенести всю открытую папку, напишите без будней и рабочих дней: "
    "«перенеси все документы в папку …»."
)


def looks_like_workday_scoped_document_request(text: str) -> bool:
    """True when the user scoped files to weekdays / working days / work hours."""
    raw = text or ""
    if (
        _PREP_BUDNY.search(raw)
        or _PREP_WORKDAY.search(raw)
        or _PREP_WORK_TIME.search(raw)
        or _DURING_WORKDAY.search(raw)
        or _DEMONSTRATIVE_WORKDAY.search(raw)
        or _BUDNY_ADJ_DOCS.search(raw)
    ):
        return True
    return False


def workday_blocks_bulk_document_mutation(
    text: str, *, explicit_document_ids: list[int] | None = None
) -> bool:
    """Refuse folder-wide delete/move when a workday scope is present and no explicit [id] was given.

    Chat used to treat «удали все документы за будни в этой папке» as wipe-the-folder because
    «все документы» matched wants_all and the weekday phrase was ignored.
    """
    if explicit_document_ids:
        return False
    return looks_like_workday_scoped_document_request(text)
