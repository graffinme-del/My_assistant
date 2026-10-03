"""Inquiry (запрос / адвокатский запрос) chat scope.

Do not treat «за запрос» / «по запросу» / «с запросом» / «на запрос» /
«за адвокатский запрос» as a folder wipe, and do not treat
«1-го запроса» as document id 1.

A folder titled «Запрос» does not match. «без запросов» and a bare
«дай запрос» / «запросить» do not match. «Разъяснение» and «пояснение»
remain separate guards.
"""

from __future__ import annotations

import re

# «запрос» and case forms. Masculine: запрос, запроса, запросу, запросом,
# запросе, запросы, запросов, запросам, запросами, запросах.
# Longer endings first so «запросами» is not cut at «а».
_INQ = r"запрос(?:ами|ах|ам|ов|ом|а|у|е|ы)?"

# «запросное письмо» / «запросная записка» — rare, but «запросные документы» is the adjective.
_INQ_ADJ = r"запросн(?:ыми|ый|ая|ое|ые|ого|ому|ым|ом|ую|ой|ых)"
_NOTE = r"записк(?:ою|ами|ах|ам|ой|ок|а|у|и|е)"
_LETTER = r"(?:письм(?:ами|ах|ам|ом|о|а|у|е)|писем)"
_INQ_PAPER = rf"{_INQ_ADJ}\s+(?:{_LETTER}|{_NOTE})"

_TARGET = rf"(?:{_INQ_PAPER}|{_INQ})"

_DEMONSTRATIVE = (
    r"(?:этими|этих|этот|этого|этому|этой|этом|эта|эту|эти|это|"
    r"прошл\w{0,4}|текущ\w{0,4}|данн\w{0,4}|сво\w{0,4})\s+"
)

_WORD_ORDINAL = (
    r"(?:перв(?:ое|ого|ому|ым|ом|ая|ую|ой|ый|ые|ых|ыми)|втор(?:ое|ого|ому|ым|ом|ая|ую|ой|ый|ые|ых|ыми)|"
    r"трет(?:ье|ьего|ьему|ьим|ьем|ья|ью|ьей|ий|ьи|ьих|ьими)|четв[её]рт(?:ое|ого|ому|ым|ом|ая|ую|ой|ый|ые|ых|ыми))"
)

# One qualifier word: «адвокатский запрос», «судебный запрос», «письменный запрос».
_ADJ_WORD = (
    r"(?:[а-яё]{3,}-)?[а-яё]{3,}(?:ыми|ими|ый|ий|ой|ая|яя|ое|ее|ые|ие|ого|его|ому|ему|ым|им|ом|ем|ую|юю|ых|их)"
)

_QUAL = rf"(?:{_DEMONSTRATIVE}|{_WORD_ORDINAL}\s+|{_ADJ_WORD}\s+)"

_ORDINAL_SUFFIX = r"(?:го|му|ой|ую|й|е|я|ю|о|м|х|ем)"

# «с/со» is idiomatic («документы с запросом»). «во» before «в», «со» before «с».
_PREP = re.compile(
    rf"(?<![а-яё])(?:за|на|во|по|со|из|в|с)\s+(?:{_QUAL}){{0,3}}(?<![а-яё]){_TARGET}(?![а-яё])",
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
    rf"(?:за|в|во|на|по|с|со|из)\s+{_WORD_ORDINAL}\s+(?:{_QUAL}){{0,2}}(?<![а-яё]){_TARGET}(?![а-яё])"
    rf"|\b{_WORD_ORDINAL}\s+(?:{_QUAL}){{0,2}}(?<![а-яё]){_TARGET}(?![а-яё])",
    re.IGNORECASE,
)

# «1-го запроса», «1-й запрос», «2-го адвокатского запроса».
# Two digits so ids like 214 stay ids. (?!\d) so a longer number is not sliced.
_ORDINAL_NUM = re.compile(
    rf"\b\d{{1,2}}(?!\d)(?:-?{_ORDINAL_SUFFIX})?\s*(?:{_QUAL}){{0,2}}(?<![а-яё]){_TARGET}(?![а-яё])",
    re.IGNORECASE,
)

# «документы запроса» — genitive scope, not a folder titled «Запрос».
_DOCS = re.compile(
    rf"(?:документ|файл)\w*\s+(?:{_QUAL}){{0,3}}(?<![а-яё]){_TARGET}(?![а-яё])",
    re.IGNORECASE,
)

# «запросные документы» / «документы запросные».
_ADJ_DOCS = re.compile(
    rf"(?:{_INQ_ADJ}\s+(?:документ|файл)\w*|(?:документ|файл)\w*\s+{_INQ_ADJ})(?![а-яё])",
    re.IGNORECASE,
)

DELETE_REFUSED_INQUIRY = (
    "Не удаляю файлы по виду «запрос» "
    "вроде «за запрос» / «по запросу» / «с запросом» / «на запрос» / "
    "«за адвокатский запрос» / «1-го запроса» — "
    "это не номер документа и не команда очистить всю папку. "
    "Укажите id: «удали документ 214» или «удали документы [12] [18]». "
    "Чтобы очистить открытую папку целиком, напишите «удали все документы в этой папке» "
    "без этих слов."
)

MOVE_REFUSED_INQUIRY = (
    "Не переношу все файлы папки по виду «запрос» "
    "вроде «за запрос» / «по запросу» / «с запросом» / «на запрос» / "
    "«за адвокатский запрос». "
    "Укажите id: «перенеси документ 214 в дело …». "
    "Чтобы перенести всю открытую папку, напишите без этих слов: "
    "«перенеси все документы в папку …»."
)


def mask_inquiry_ordinals(text: str) -> str:
    """Replace «1-го запроса» so the digit is not a document id."""
    return _ORDINAL_NUM.sub(" ", text or "")


def looks_like_inquiry_scoped_document_request(text: str) -> bool:
    """True when the user scoped files to a запрос / адвокатский запрос."""
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


def inquiry_blocks_bulk_document_mutation(
    text: str, *, explicit_document_ids: list[int] | None = None
) -> bool:
    """Refuse folder-wide delete/move when a запрос scope is present.

    Chat treated «удали все документы за запрос в этой папке» as
    wipe-the-folder because «все документы» matched wants_all and the
    document-type phrase was ignored. «удали документы 1-го запроса»
    took the first digit as a document id.
    """
    if explicit_document_ids:
        return False
    return looks_like_inquiry_scoped_document_request(text)
