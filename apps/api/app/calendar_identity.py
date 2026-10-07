"""Insurance policy / passport (полис / паспорт) chat scope.

Do not treat «за полис» / «за паспорт» / «за загранпаспорт» as a folder
wipe, and do not treat «1-го полиса» / «1-го паспорта» as document id 1.

A folder titled «Полис» or «Паспорт» does not match.
«без полиса», «без паспорта», «полистать», and «паспортизация» do not match.
Bare «ОСАГО» / «ПТС» are not this guard. «Штраф» remains a separate guard.
"""

from __future__ import annotations

import re

# «полис». Longer endings first. «полистать» does not match: the stem must
# end on a non-letter, and «полистать» continues with «т».
_POLICY = r"полис(?:ами|ах|ам|ов|ом|а|у|е|ы)?"

# «паспорт», «загранпаспорт», «техпаспорт». «паспортизация» does not match.
_PASSPORT = r"(?:(?:загран|тех)-?)?паспорт(?:ами|ах|ам|ов|ом|а|у|е|ы)?"

_POLICY_ADJ = r"полисн(?:ыми|ый|ая|ое|ые|ого|ому|ым|ом|ую|ой|ых)"
_PASSPORT_ADJ = r"паспортн(?:ыми|ый|ая|ое|ые|ого|ому|ым|ом|ую|ой|ых)"

_TARGET = rf"(?:{_PASSPORT}|{_POLICY})"
_ADJ = rf"(?:{_PASSPORT_ADJ}|{_POLICY_ADJ})"

_DEMONSTRATIVE = (
    r"(?:этими|этих|этот|этого|этому|этой|этом|эта|эту|эти|это|"
    r"прошл\w{0,4}|текущ\w{0,4}|данн\w{0,4}|сво\w{0,4})\s+"
)

_WORD_ORDINAL = (
    r"(?:перв(?:ое|ого|ому|ым|ом|ая|ую|ой|ый|ые|ых|ыми)|втор(?:ое|ого|ому|ым|ом|ая|ую|ой|ый|ые|ых|ыми)|"
    r"трет(?:ье|ьего|ьему|ьим|ьем|ья|ью|ьей|ий|ьи|ьих|ьими)|четв[её]рт(?:ое|ого|ому|ым|ом|ая|ую|ой|ый|ые|ых|ыми))"
)

# One qualifier word: «страховой полис», «технический паспорт», «заграничный паспорт».
_ADJ_WORD = (
    r"(?:[а-яё]{3,}-)?[а-яё]{3,}(?:ыми|ими|ый|ий|ой|ая|яя|ое|ее|ые|ие|ого|его|ому|ему|ым|им|ом|ем|ую|юю|ых|их)"
)

_QUAL = rf"(?:{_DEMONSTRATIVE}|{_WORD_ORDINAL}\s+|{_ADJ_WORD}\s+)"

_ORDINAL_SUFFIX = r"(?:го|му|ой|ую|й|е|я|ю|о|м|х|ем)"

_PREP = re.compile(
    rf"(?<![а-яё])(?:об|во|со|за|на|по|из|в|с|о)\s+(?:{_QUAL}){{0,3}}(?<![а-яё]){_TARGET}(?![а-яё])",
    re.IGNORECASE,
)

_DURING = re.compile(
    rf"во\s+время\s+(?:{_QUAL}){{0,3}}(?<![а-яё]){_TARGET}(?![а-яё])",
    re.IGNORECASE,
)

_DEMONSTRATIVE_SCOPE = re.compile(
    rf"(?:этими|этих|этот|этого|этому|этой|этом|эта|эту|эти|"
    r"прошлые|прошлых|прошлый|прошлого|прошлая|прошлую|прошлое|"
    r"текущие|текущих|текущий|текущего|текущая|текущую|текущее|"
    r"данные|данных|данного)\s+"
    rf"(?:{_QUAL}){{0,2}}(?<![а-яё]){_TARGET}(?![а-яё])",
    re.IGNORECASE,
)

_ORDINAL_WORD = re.compile(
    rf"(?:об|за|в|во|на|по|с|со|из|о)\s+{_WORD_ORDINAL}\s+(?:{_QUAL}){{0,2}}(?<![а-яё]){_TARGET}(?![а-яё])"
    rf"|\b{_WORD_ORDINAL}\s+(?:{_QUAL}){{0,2}}(?<![а-яё]){_TARGET}(?![а-яё])",
    re.IGNORECASE,
)

# «1-го полиса», «1-го паспорта», «1-й загранпаспорт».
# Two digits so ids like 214 stay ids. (?!\d) so a longer number is not sliced.
_ORDINAL_NUM = re.compile(
    rf"\b\d{{1,2}}(?!\d)(?:-?{_ORDINAL_SUFFIX})?\s*(?:{_QUAL}){{0,2}}(?<![а-яё]){_TARGET}(?![а-яё])",
    re.IGNORECASE,
)

# «документы полиса» — genitive scope, not a folder titled «Полис».
_DOCS = re.compile(
    rf"(?:документ|файл)\w*\s+(?:{_QUAL}){{0,3}}(?<![а-яё]){_TARGET}(?![а-яё])",
    re.IGNORECASE,
)

# «полисные документы» / «документы паспортные».
_ADJ_DOCS = re.compile(
    rf"(?:(?<![а-яё]){_ADJ}\s+(?:документ|файл)\w*|(?:документ|файл)\w*\s+(?<![а-яё]){_ADJ})(?![а-яё])",
    re.IGNORECASE,
)

DELETE_REFUSED_REPLY = (
    "Не удаляю файлы по виду «полис» / «паспорт» "
    "вроде «за полис» / «за паспорт» / «за загранпаспорт» / "
    "«1-го полиса» / «1-го паспорта» — "
    "это не номер документа и не команда очистить всю папку. "
    "Укажите id: «удали документ 214» или «удали документы [12] [18]». "
    "Чтобы очистить открытую папку целиком, напишите «удали все документы в этой папке» "
    "без этих слов."
)

MOVE_REFUSED_REPLY = (
    "Не переношу все файлы папки по виду «полис» / «паспорт» "
    "вроде «за полис» / «за паспорт» / «за загранпаспорт». "
    "Укажите id: «перенеси документ 214 в дело …». "
    "Чтобы перенести всю открытую папку, напишите без этих слов: "
    "«перенеси все документы в папку …»."
)


def mask_identity_ordinals(text: str) -> str:
    """Replace «1-го полиса» / «1-го паспорта» so the digit is not a document id."""
    return _ORDINAL_NUM.sub(" ", text or "")


def looks_like_identity_scoped_document_request(text: str) -> bool:
    """True when the user scoped files to a полис / паспорт."""
    raw = text or ""
    if (
        _PREP.search(raw)
        or _DURING.search(raw)
        or _DEMONSTRATIVE_SCOPE.search(raw)
        or _ORDINAL_WORD.search(raw)
        or _ORDINAL_NUM.search(raw)
        or _DOCS.search(raw)
        or _ADJ_DOCS.search(raw)
    ):
        return True
    return False


def identity_blocks_bulk_document_mutation(
    text: str, *, explicit_document_ids: list[int] | None = None
) -> bool:
    """Refuse folder-wide delete/move when a policy or passport scope is present.

    Chat treated «удали все документы за полис в этой папке» as
    wipe-the-folder because «все документы» matched wants_all and the
    document-type phrase was ignored. «удали документы 1-го полиса»
    took the first digit as a document id. The same path hits «паспорт».
    """
    if explicit_document_ids:
        return False
    return looks_like_identity_scoped_document_request(text)
