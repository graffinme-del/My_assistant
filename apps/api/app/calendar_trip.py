"""Business-trip / overtime chat scope: do not treat «за командировку» / «сверхурочные документы» as a folder wipe."""

from __future__ import annotations

import re

# Noun after a time preposition: «за командировку», «на сверхурочных», «по переработкам».
# Trailing (?![а-яё]) is applied at the call site so «командировочный» does not steal the noun slot.
_TRIP_NOUN = (
    r"(?:командировк(?:а|и|е|у|ой|ою|ах|ам|ами)?"
    r"|сверхурочн(?:ые|ых|ыми|ым|ый|ая|ое|ую|ой|ого|ому|ом)(?:\s+работ\w*)?"
    r"|переработк(?:а|и|е|у|ой|ою|ах|ам|ами)?)"
)

_TRIP_ADJ = (
    r"(?:(?:командировочн(?:ый|ая|ое|ые|ого|ому|ым|ом|ую|ой|ых|ыми))"
    r"|(?:сверхурочн(?:ый|ая|ое|ые|ого|ому|ым|ом|ую|ой|ых|ыми))"
    r"|(?:служебн(?:ый|ая|ое|ые|ого|ому|ым|ом|ую|ой|ых|ыми)))"
)

_DEMONSTRATIVE = (
    r"(?:это|эти|этих|этими|этот|этой|этом|эта|эту|"
    r"прошл\w{0,4}|текущ\w{0,4}|данн\w{0,4}|сво\w{0,4})\s+"
)

# Wrap the demonstrative: `{_DEMONSTRATIVE}?` would make only the trailing `\s+` optional.
_PREP_TRIP = re.compile(
    rf"(?:за|на|в|во|по)\s+(?:{_DEMONSTRATIVE})?(?:(?<![а-яё]){_TRIP_ADJ}\s+)?(?<![а-яё]){_TRIP_NOUN}(?![а-яё])",
    re.IGNORECASE,
)

_DURING_TRIP = re.compile(
    rf"во\s+время\s+(?:{_DEMONSTRATIVE})?(?:{_TRIP_ADJ}\s+)?{_TRIP_NOUN}(?![а-яё])",
    re.IGNORECASE,
)

_DEMONSTRATIVE_TRIP = re.compile(
    rf"(?:эти|этих|этими|этот|этого|этом|эта|эту|этой|"
    r"прошлые|прошлых|прошлый|прошлая|прошлую|прошлое|"
    r"текущие|текущих|текущий|текущая|текущую|текущее|"
    r"данные|данных)\s+"
    rf"(?:{_TRIP_ADJ}\s+)?{_TRIP_NOUN}(?![а-яё])",
    re.IGNORECASE,
)

_WORD_ORDINAL = (
    r"(?:перв(?:ое|ого|ому|ым|ом|ая|ую|ой|ый|ые|ых|ыми)|втор(?:ое|ого|ому|ым|ом|ая|ую|ой|ый|ые|ых|ыми)|"
    r"трет(?:ье|ьего|ьему|ьим|ьем|ья|ью|ьей|ий|ьи|ьих|ьими)|четв[её]рт(?:ое|ого|ому|ым|ом|ая|ую|ой|ый|ые|ых|ыми))"
)

_ORDINAL_TRIP_WORD = re.compile(
    rf"(?:за|в|во|на|по)\s+{_WORD_ORDINAL}\s+{_TRIP_NOUN}(?![а-яё])"
    rf"|\b{_WORD_ORDINAL}\s+{_TRIP_NOUN}(?![а-яё])",
    re.IGNORECASE,
)

# «1-й командировки», «1-х сверхурочных», «1 переработки» — not a document id.
_ORDINAL_TRIP_NUM = re.compile(
    r"\b\d{1,2}(?:-?(?:го|му|ой|ую|й|е|я|ю|о|м|х))?\s*(?:командировк|сверхурочн|переработк)",
    re.IGNORECASE,
)

# «командировочные документы» / «документы сверхурочные» — collocation, not a folder titled «Командировка».
_TRIP_ADJ_DOCS = re.compile(
    rf"(?:(?<![а-яё]){_TRIP_ADJ}\s+(?:документ|файл)\w*"
    rf"|(?:документ|файл)\w*\s+(?<![а-яё]){_TRIP_ADJ})(?![а-яё])",
    re.IGNORECASE,
)

DELETE_REFUSED_TRIP = (
    "Не удаляю файлы по командировке/сверхурочным вроде «за командировку» / «за сверхурочные» / "
    "«командировочные документы» / «1-й командировки» — это не номер документа и не команда очистить всю папку. "
    "Укажите id: «удали документ 214» или «удали документы [12] [18]». "
    "Чтобы очистить открытую папку целиком, напишите «удали все документы в этой папке» "
    "без командировки и сверхурочных документов."
)

MOVE_REFUSED_TRIP = (
    "Не переношу все файлы папки по командировке/сверхурочным вроде «за командировку» / "
    "«за сверхурочные» / «командировочные документы». "
    "Укажите id: «перенеси документ 214 в дело …». "
    "Чтобы перенести всю открытую папку, напишите без командировки: "
    "«перенеси все документы в папку …»."
)


def mask_trip_ordinals(text: str) -> str:
    """Replace «1-й командировки» so the leading digit cannot be parsed as a document id."""
    return _ORDINAL_TRIP_NUM.sub(" ", text or "")


def looks_like_trip_scoped_document_request(text: str) -> bool:
    """True when the user scoped files to a business trip or overtime period."""
    raw = text or ""
    if (
        _PREP_TRIP.search(raw)
        or _DURING_TRIP.search(raw)
        or _DEMONSTRATIVE_TRIP.search(raw)
        or _ORDINAL_TRIP_WORD.search(raw)
        or _ORDINAL_TRIP_NUM.search(raw)
        or _TRIP_ADJ_DOCS.search(raw)
    ):
        return True
    return False


def trip_blocks_bulk_document_mutation(
    text: str, *, explicit_document_ids: list[int] | None = None
) -> bool:
    """Refuse folder-wide delete/move when a trip/overtime scope is present and no explicit [id] was given.

    Chat used to treat «удали все документы за командировку в этой папке» as wipe-the-folder because
    «все документы» matched wants_all and the trip phrase was ignored. «удали документы
    1-й командировки» took the first digit as a document id.
    """
    if explicit_document_ids:
        return False
    return looks_like_trip_scoped_document_request(text)
