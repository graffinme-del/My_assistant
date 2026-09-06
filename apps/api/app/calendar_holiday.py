"""Holiday/vacation chat scope: do not treat «за праздники» as a folder wipe."""

from __future__ import annotations

import re

# Nouns after a time preposition: «за праздники», «на каникулах», «в праздник».
_HOLIDAY_NOUN = (
    r"(?:праздник(?:а|у|ом|е|и|ов|ам|ами|ах)?"
    r"|каникул(?:ы|ам|ами|ах)?)"
)

# Adjectives: «праздничные документы», «каникулярные файлы», «новогодние документы».
_HOLIDAY_ADJ = (
    r"(?:праздничн(?:ый|ая|ое|ые|ого|ому|ым|ом|ую|ой|ых|ыми)"
    r"|каникулярн(?:ый|ая|ое|ые|ого|ому|ым|ом|ую|ой|ых|ыми)"
    r"|новогодн(?:ий|яя|ее|ие|его|ему|им|ем|ую|ей|их|ими))"
)

_DEMONSTRATIVE = r"(?:это|эти|этих|этими|этот|этой|этом|прошл\w{0,4}|текущ\w{0,4}|данн\w{0,4})\s+"

# «за праздники», «за эти каникулы», «на каникулах», «в праздник».
# Wrap the demonstrative: `{_DEMONSTRATIVE}?` would make only the trailing `\s+` optional.
_PREP_HOLIDAY = re.compile(
    rf"(?:за|на|в|во)\s+(?:{_DEMONSTRATIVE})?{_HOLIDAY_NOUN}(?![а-яё])",
    re.IGNORECASE,
)

# «во время праздников», «во время каникул».
_DURING_HOLIDAY = re.compile(
    rf"во\s+время\s+(?:{_DEMONSTRATIVE})?{_HOLIDAY_NOUN}(?![а-яё])",
    re.IGNORECASE,
)

# «за новый год», «на новый год», «под новый год» — not numeric «за 2025 год» (#72).
_NEW_YEAR = re.compile(
    rf"(?:за|на|под|в|во)\s+(?:{_DEMONSTRATIVE})?новы(?:й|м|е)\s+год(?:а|у)?(?![а-яё])",
    re.IGNORECASE,
)

# «эти праздники», «прошлые каникулы» without a preposition.
_DEMONSTRATIVE_NOUN = re.compile(
    rf"(?:эти|этих|этими|прошлые|прошлых|текущие|текущих|данные|данных)\s+{_HOLIDAY_NOUN}(?![а-яё])",
    re.IGNORECASE,
)

_ADJ = re.compile(
    rf"(?<![а-яё]){_HOLIDAY_ADJ}(?![а-яё])",
    re.IGNORECASE,
)

DELETE_REFUSED_HOLIDAY = (
    "Не удаляю файлы по праздникам или каникулам вроде «за праздники» / «на каникулах» / "
    "«праздничные документы» — это не номер документа и не команда очистить всю папку. "
    "Укажите id: «удали документ 214» или «удали документы [12] [18]». "
    "Чтобы очистить открытую папку целиком, напишите «удали все документы в этой папке» "
    "без праздников и каникул."
)

MOVE_REFUSED_HOLIDAY = (
    "Не переношу все файлы папки по праздникам или каникулам вроде «за праздники» / "
    "«на каникулах» / «праздничные документы». "
    "Укажите id: «перенеси документ 214 в дело …». "
    "Чтобы перенести всю открытую папку, напишите без праздников: "
    "«перенеси все документы в папку …»."
)


def looks_like_holiday_scoped_document_request(text: str) -> bool:
    """True when the user scoped files to holidays or vacation."""
    raw = text or ""
    if (
        _PREP_HOLIDAY.search(raw)
        or _DURING_HOLIDAY.search(raw)
        or _NEW_YEAR.search(raw)
        or _DEMONSTRATIVE_NOUN.search(raw)
        or _ADJ.search(raw)
    ):
        return True
    return False


def holiday_blocks_bulk_document_mutation(
    text: str, *, explicit_document_ids: list[int] | None = None
) -> bool:
    """Refuse folder-wide delete/move when a holiday/vacation scope is present and no explicit [id] was given.

    Chat used to treat «удали все документы за праздники в этой папке» as wipe-the-folder because
    «все документы» matched wants_all and the holiday was ignored.
    """
    if explicit_document_ids:
        return False
    return looks_like_holiday_scoped_document_request(text)
