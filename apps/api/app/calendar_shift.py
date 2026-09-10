"""Shift-class chat scope: do not treat «за смену» / «ночные документы» as a folder wipe."""

from __future__ import annotations

import re

# Noun after a time preposition: «за смену», «по сменам», «на смене».
# Trailing (?![а-яё]) is applied at the call site so «сменить» does not match.
_SHIFT_NOUN = r"(?:смен(?:а|ы|е|у|ой|ою|ах|ам|ами)?)"

# «ночная/дневная/утренняя/вечерняя смена»
_SHIFT_ADJ = (
    r"(?:(?:ночн(?:ой|ая|ое|ые|ого|ому|ым|ом|ую|ой|ых|ыми))"
    r"|(?:дневн(?:ой|ая|ое|ые|ого|ому|ым|ом|ую|ой|ых|ыми))"
    r"|(?:утренн(?:ий|яя|ее|ие|его|ему|им|ем|юю|ей|их|ими))"
    r"|(?:вечерн(?:ий|яя|ее|ие|его|ему|им|ем|юю|ей|их|ими)))"
)

# Time-of-day noun: «за ночь», «по ночам», «ночью».
_NIGHT_NOUN = r"(?:ноч(?:ь|и|ью|ей|ам|ами|ах))"

_DEMONSTRATIVE = (
    r"(?:это|эти|этих|этими|этот|этой|этом|эта|эту|"
    r"прошл\w{0,4}|текущ\w{0,4}|данн\w{0,4}|сво\w{0,4})\s+"
)

# Wrap the demonstrative: `{_DEMONSTRATIVE}?` would make only the trailing `\s+` optional.
_PREP_SHIFT = re.compile(
    rf"(?:за|на|в|во|по)\s+(?:{_DEMONSTRATIVE})?(?:(?<![а-яё]){_SHIFT_ADJ}\s+)?(?<![а-яё]){_SHIFT_NOUN}(?![а-яё])",
    re.IGNORECASE,
)

_PREP_NIGHT = re.compile(
    rf"(?:за|на|в|во|по)\s+(?:{_DEMONSTRATIVE})?{_NIGHT_NOUN}(?![а-яё])",
    re.IGNORECASE,
)

_DURING_SHIFT = re.compile(
    rf"во\s+время\s+(?:{_DEMONSTRATIVE})?(?:{_SHIFT_ADJ}\s+)?{_SHIFT_NOUN}(?![а-яё])",
    re.IGNORECASE,
)

_DEMONSTRATIVE_SHIFT = re.compile(
    rf"(?:эти|этих|этими|этот|этого|этом|эта|эту|этой|"
    r"прошлые|прошлых|прошлый|прошлая|прошлую|"
    r"текущие|текущих|текущий|текущая|текущую|"
    r"данные|данных)\s+"
    rf"(?:{_SHIFT_ADJ}\s+)?{_SHIFT_NOUN}(?![а-яё])",
    re.IGNORECASE,
)

_WORD_ORDINAL = (
    r"(?:перв(?:ая|ую|ой|ый)|втор(?:ая|ую|ой|ый)|"
    r"трет(?:ья|ью|ьей|ий)|четв[её]рт(?:ая|ую|ой|ый))"
)

_ORDINAL_SHIFT_WORD = re.compile(
    rf"(?:за|в|во|на|по)\s+{_WORD_ORDINAL}\s+{_SHIFT_NOUN}(?![а-яё])"
    rf"|\b{_WORD_ORDINAL}\s+{_SHIFT_NOUN}(?![а-яё])",
    re.IGNORECASE,
)

# «1-й смены», «2-ю смену», «1 смены» — not a document id.
_ORDINAL_SHIFT_NUM = re.compile(
    r"\b\d{1,2}(?:-?[йеяою])?\s*смен",
    re.IGNORECASE,
)

_NIGHT_ADV = re.compile(r"(?<![а-яё])ночью(?![а-яё])", re.IGNORECASE)

# «ночные документы» / «документы ночные» — collocation, not a folder titled «Ночь».
_TIME_OF_DAY_ADJ = (
    r"(?:(?:ночн(?:ой|ая|ое|ые|ого|ому|ым|ом|ую|ой|ых|ыми))"
    r"|(?:дневн(?:ой|ая|ое|ые|ого|ому|ым|ом|ую|ой|ых|ыми))"
    r"|(?:утренн(?:ий|яя|ее|ие|его|ему|им|ем|юю|ей|их|ими))"
    r"|(?:вечерн(?:ий|яя|ее|ие|его|ему|им|ем|юю|ей|их|ими))"
    r"|(?:сменн(?:ый|ая|ое|ые|ого|ому|ым|ом|ую|ой|ых|ыми)))"
)

_TIME_OF_DAY_ADJ_DOCS = re.compile(
    rf"(?:(?<![а-яё]){_TIME_OF_DAY_ADJ}\s+(?:документ|файл)\w*"
    rf"|(?:документ|файл)\w*\s+(?<![а-яё]){_TIME_OF_DAY_ADJ})(?![а-яё])",
    re.IGNORECASE,
)

DELETE_REFUSED_SHIFT = (
    "Не удаляю файлы по смене вроде «за смену» / «за ночную смену» / "
    "«ночные документы» / «1-й смены» — это не номер документа и не команда очистить всю папку. "
    "Укажите id: «удали документ 214» или «удали документы [12] [18]». "
    "Чтобы очистить открытую папку целиком, напишите «удали все документы в этой папке» "
    "без смены и ночных/дневных документов."
)

MOVE_REFUSED_SHIFT = (
    "Не переношу все файлы папки по смене вроде «за смену» / "
    "«за ночную смену» / «ночные документы». "
    "Укажите id: «перенеси документ 214 в дело …». "
    "Чтобы перенести всю открытую папку, напишите без смены: "
    "«перенеси все документы в папку …»."
)


def mask_shift_ordinals(text: str) -> str:
    """Replace «1-й смены» so the leading digit cannot be parsed as a document id."""
    return _ORDINAL_SHIFT_NUM.sub(" ", text or "")


def looks_like_shift_scoped_document_request(text: str) -> bool:
    """True when the user scoped files to a work shift or night/day-shift files."""
    raw = text or ""
    if (
        _PREP_SHIFT.search(raw)
        or _PREP_NIGHT.search(raw)
        or _DURING_SHIFT.search(raw)
        or _DEMONSTRATIVE_SHIFT.search(raw)
        or _ORDINAL_SHIFT_WORD.search(raw)
        or _ORDINAL_SHIFT_NUM.search(raw)
        or _NIGHT_ADV.search(raw)
        or _TIME_OF_DAY_ADJ_DOCS.search(raw)
    ):
        return True
    return False


def shift_blocks_bulk_document_mutation(
    text: str, *, explicit_document_ids: list[int] | None = None
) -> bool:
    """Refuse folder-wide delete/move when a shift scope is present and no explicit [id] was given.

    Chat used to treat «удали все документы за смену в этой папке» as wipe-the-folder because
    «все документы» matched wants_all and the shift phrase was ignored. «удали документы
    1-й смены» took the first digit as a document id.
    """
    if explicit_document_ids:
        return False
    return looks_like_shift_scoped_document_request(text)
