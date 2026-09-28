"""Evidence («доказательство») chat scope.

Do not treat «за доказательства» / «с доказательствами» / «по доказательствам»
as a folder wipe, and do not treat «1-го доказательства» as document id 1.

«Приложение» is a different noun (separate guard). «Доказательный» and
«доказательственный» without a document/file word do not match the noun slot.
"""

from __future__ import annotations

import re

# «доказательство», «доказательства», «доказательством», «доказательствами»,
# «доказательств», «доказательствах». Longer endings come first.
# Trailing (?![а-яё]) is applied at the call site so «доказательственный»
# does not steal the noun slot (its «е» is not a case ending here).
_EVIDENCE = r"доказательств(?:ами|ах|ам|ом|ов|у|е|а|о)?"

_DEMONSTRATIVE = (
    r"(?:этими|этих|этот|этого|этому|этой|этом|эта|эту|эти|это|"
    r"прошл\w{0,4}|текущ\w{0,4}|данн\w{0,4}|сво\w{0,4})\s+"
)

_WORD_ORDINAL = (
    r"(?:перв(?:ое|ого|ому|ым|ом|ая|ую|ой|ый|ые|ых|ыми)|втор(?:ое|ого|ому|ым|ом|ая|ую|ой|ый|ые|ых|ыми)|"
    r"трет(?:ье|ьего|ьему|ьим|ьем|ья|ью|ьей|ий|ьи|ьих|ьими)|четв[её]рт(?:ое|ого|ому|ым|ом|ая|ую|ой|ый|ые|ых|ыми))"
)

# One qualifier word: «письменные доказательства», «вещественные доказательства».
_ADJ_WORD = (
    r"(?:[а-яё]{3,}-)?[а-яё]{3,}(?:ый|ий|ой|ая|яя|ое|ее|ые|ие|ого|его|ому|ему|ым|им|ом|ем|ую|юю|ых|их|ыми|ими)"
)

_QUAL = rf"(?:{_DEMONSTRATIVE}|{_WORD_ORDINAL}\s+|{_ADJ_WORD}\s+)"

# «с/со» is idiomatic («документы с доказательствами»). «во» before «в», «со» before «с».
_PREP = re.compile(
    rf"(?<![а-яё])(?:за|на|во|по|со|в|с)\s+(?:{_QUAL}){{0,3}}(?<![а-яё]){_EVIDENCE}(?![а-яё])",
    re.IGNORECASE,
)

_DURING = re.compile(
    rf"во\s+время\s+(?:{_QUAL}){{0,3}}(?<![а-яё]){_EVIDENCE}(?![а-яё])",
    re.IGNORECASE,
)

_DEMONSTRATIVE_SCOPE = re.compile(
    rf"(?:этими|этих|этот|этого|этому|этой|этом|эта|эту|эти|"
    r"прошлые|прошлых|прошлый|прошлого|прошлая|прошлую|прошлое|"
    r"текущие|текущих|текущий|текущего|текущая|текущую|текущее|"
    r"данные|данных|данного)\s+"
    rf"(?:{_QUAL}){{0,2}}(?<![а-яё]){_EVIDENCE}(?![а-яё])",
    re.IGNORECASE,
)

_ORDINAL_WORD = re.compile(
    rf"(?:за|в|во|на|по|с|со)\s+{_WORD_ORDINAL}\s+(?:{_QUAL}){{0,2}}(?<![а-яё]){_EVIDENCE}(?![а-яё])"
    rf"|\b{_WORD_ORDINAL}\s+(?:{_QUAL}){{0,2}}(?<![а-яё]){_EVIDENCE}(?![а-яё])",
    re.IGNORECASE,
)

# «1-го доказательства», «1-е доказательство». Two digits so ids like 214 stay ids.
_ORDINAL_NUM = re.compile(
    rf"\b\d{{1,2}}(?:-?(?:го|му|ой|ую|й|е|я|ю|о|м|х|ем))?\s*(?:{_QUAL}){{0,2}}(?<![а-яё]){_EVIDENCE}(?![а-яё])",
    re.IGNORECASE,
)

# «документы доказательства» — genitive scope, not a folder titled «Доказательства».
_DOCS = re.compile(
    rf"(?:документ|файл)\w*\s+(?:{_QUAL}){{0,3}}(?<![а-яё]){_EVIDENCE}(?![а-яё])",
    re.IGNORECASE,
)

# «доказательственные документы» / «документы доказательственные».
_EVIDENCE_ADJ = r"доказательственн(?:ый|ая|ое|ые|ого|ому|ым|ом|ую|ой|ых|ыми)"
_ADJ_DOCS = re.compile(
    rf"(?:{_EVIDENCE_ADJ}\s+(?:документ|файл)\w*|(?:документ|файл)\w*\s+{_EVIDENCE_ADJ})(?![а-яё])",
    re.IGNORECASE,
)

DELETE_REFUSED_EVIDENCE = (
    "Не удаляю файлы по доказательствам "
    "вроде «за доказательства» / «с доказательствами» / «по доказательствам» / "
    "«1-го доказательства» — это не номер документа и не команда очистить всю папку. "
    "Укажите id: «удали документ 214» или «удали документы [12] [18]». "
    "Чтобы очистить открытую папку целиком, напишите «удали все документы в этой папке» "
    "без слова «доказательства»."
)

MOVE_REFUSED_EVIDENCE = (
    "Не переношу все файлы папки по доказательствам "
    "вроде «за доказательства» / «с доказательствами» / «по доказательствам». "
    "Укажите id: «перенеси документ 214 в дело …». "
    "Чтобы перенести всю открытую папку, напишите без слова «доказательства»: "
    "«перенеси все документы в папку …»."
)


def mask_evidence_ordinals(text: str) -> str:
    """Replace «1-го доказательства» so the leading digit cannot be parsed as a document id."""
    return _ORDINAL_NUM.sub(" ", text or "")


def looks_like_evidence_scoped_document_request(text: str) -> bool:
    """True when the user scoped files to доказательства."""
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


def evidence_blocks_bulk_document_mutation(
    text: str, *, explicit_document_ids: list[int] | None = None
) -> bool:
    """Refuse folder-wide delete/move when an evidence scope is present.

    Chat treated «удали все документы за доказательства в этой папке» as wipe-the-folder
    because «все документы» matched wants_all and the document-type phrase was ignored.
    «удали документы 1-го доказательства» took the first digit as a document id.
    """
    if explicit_document_ids:
        return False
    return looks_like_evidence_scoped_document_request(text)
