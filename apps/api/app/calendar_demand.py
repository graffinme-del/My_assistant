"""Demand («требование» / «истребование») chat scope.

Do not treat «за требование» / «с требованием» / «по требованию» /
«за истребование» / «за реестр требований» as a folder wipe, and do not treat
«1-го требования» as document id 1.

A folder titled «Требование» does not match. «Пояснение», «лицензия», and
«свидетельство» are different nouns. «Расчет» remains a separate guard.
"""

from __future__ import annotations

import re

# «требование», «требования», «требованию», «требованием», «требовании»,
# «требований», «требованиям», «требованиями», «требованиях».
# «истребование» is «ис» + «требование», not an «и» prefix, so it is its own alternative.
# Longer endings come first. «истребован…» is listed first so it is not left unmatched.
_NOUN_END = r"(?:ями|ях|ям|ем|й|ю|я|и|е)"
_DEMAND = rf"(?:истребовани{_NOUN_END}|требовани{_NOUN_END})"

# «реестр требований кредиторов» and case forms of «реестр».
_REGISTER = r"реестр(?:ами|ах|ам|ов|ом|а|у|е)?"

_DEMONSTRATIVE = (
    r"(?:этими|этих|этот|этого|этому|этой|этом|эта|эту|эти|это|"
    r"прошл\w{0,4}|текущ\w{0,4}|данн\w{0,4}|сво\w{0,4})\s+"
)

_WORD_ORDINAL = (
    r"(?:перв(?:ое|ого|ому|ым|ом|ая|ую|ой|ый|ые|ых|ыми)|втор(?:ое|ого|ому|ым|ом|ая|ую|ой|ый|ые|ых|ыми)|"
    r"трет(?:ье|ьего|ьему|ьим|ьем|ья|ью|ьей|ий|ьи|ьих|ьими)|четв[её]рт(?:ое|ого|ому|ым|ом|ая|ую|ой|ый|ые|ых|ыми))"
)

# One qualifier word: «встречное требование», «исковое требование».
_ADJ_WORD = (
    r"(?:[а-яё]{3,}-)?[а-яё]{3,}(?:ый|ий|ой|ая|яя|ое|ее|ые|ие|ого|его|ому|ему|ым|им|ом|ем|ую|юю|ых|их|ыми|ими)"
)

_QUAL = rf"(?:{_DEMONSTRATIVE}|{_WORD_ORDINAL}\s+|{_ADJ_WORD}\s+|{_REGISTER}\s+)"

# «с/со» is idiomatic («документы с требованием»). «во» before «в», «со» before «с».
_PREP = re.compile(
    rf"(?<![а-яё])(?:за|на|во|по|со|в|с)\s+(?:{_QUAL}){{0,3}}(?<![а-яё]){_DEMAND}(?![а-яё])",
    re.IGNORECASE,
)

_DURING = re.compile(
    rf"во\s+время\s+(?:{_QUAL}){{0,3}}(?<![а-яё]){_DEMAND}(?![а-яё])",
    re.IGNORECASE,
)

_DEMONSTRATIVE_SCOPE = re.compile(
    rf"(?:этими|этих|этот|этого|этому|этой|этом|эта|эту|эти|"
    r"прошлые|прошлых|прошлый|прошлого|прошлая|прошлую|прошлое|"
    r"текущие|текущих|текущий|текущего|текущая|текущую|текущее|"
    r"данные|данных|данного)\s+"
    rf"(?:{_QUAL}){{0,2}}(?<![а-яё]){_DEMAND}(?![а-яё])",
    re.IGNORECASE,
)

_ORDINAL_WORD = re.compile(
    rf"(?:за|в|во|на|по|с|со)\s+{_WORD_ORDINAL}\s+(?:{_QUAL}){{0,2}}(?<![а-яё]){_DEMAND}(?![а-яё])"
    rf"|\b{_WORD_ORDINAL}\s+(?:{_QUAL}){{0,2}}(?<![а-яё]){_DEMAND}(?![а-яё])",
    re.IGNORECASE,
)

# «1-го требования», «1-е требование». Two digits so ids like 214 stay ids.
_ORDINAL_NUM = re.compile(
    rf"\b\d{{1,2}}(?:-?(?:го|му|ой|ую|й|е|я|ю|о|м|х|ем))?\s*(?:{_QUAL}){{0,2}}(?<![а-яё]){_DEMAND}(?![а-яё])",
    re.IGNORECASE,
)

# «документы требования» — genitive scope, not a folder titled «Требование».
_DOCS = re.compile(
    rf"(?:документ|файл)\w*\s+(?:{_QUAL}){{0,3}}(?<![а-яё]){_DEMAND}(?![а-яё])",
    re.IGNORECASE,
)

# «требовательные документы» / «документы требовательные».
_DEMAND_ADJ = r"требовательн(?:ый|ая|ое|ые|ого|ому|ым|ом|ую|ой|ых|ыми)"
_ADJ_DOCS = re.compile(
    rf"(?:{_DEMAND_ADJ}\s+(?:документ|файл)\w*|(?:документ|файл)\w*\s+{_DEMAND_ADJ})(?![а-яё])",
    re.IGNORECASE,
)

DELETE_REFUSED_DEMAND = (
    "Не удаляю файлы по виду «требование» "
    "вроде «за требование» / «за истребование» / «с требованием» / «по требованию» / "
    "«за реестр требований» / «1-го требования» — это не номер документа и не команда очистить всю папку. "
    "Укажите id: «удали документ 214» или «удали документы [12] [18]». "
    "Чтобы очистить открытую папку целиком, напишите «удали все документы в этой папке» "
    "без слова «требование»."
)

MOVE_REFUSED_DEMAND = (
    "Не переношу все файлы папки по виду «требование» "
    "вроде «за требование» / «за истребование» / «с требованием» / «по требованию» / "
    "«за реестр требований». "
    "Укажите id: «перенеси документ 214 в дело …». "
    "Чтобы перенести всю открытую папку, напишите без слова «требование»: "
    "«перенеси все документы в папку …»."
)


def mask_demand_ordinals(text: str) -> str:
    """Replace «1-го требования» so the leading digit cannot be parsed as a document id."""
    return _ORDINAL_NUM.sub(" ", text or "")


def looks_like_demand_scoped_document_request(text: str) -> bool:
    """True when the user scoped files to a требование / истребование."""
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


def demand_blocks_bulk_document_mutation(
    text: str, *, explicit_document_ids: list[int] | None = None
) -> bool:
    """Refuse folder-wide delete/move when a demand scope is present.

    Chat treated «удали все документы за требование в этой папке» as wipe-the-folder
    because «все документы» matched wants_all and the document-type phrase was ignored.
    «удали документы 1-го требования» took the first digit as a document id.
    """
    if explicit_document_ids:
        return False
    return looks_like_demand_scoped_document_request(text)
