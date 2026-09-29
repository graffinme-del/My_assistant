"""Calculation («расчет» / «перерасчет») chat scope.

Do not treat «за расчет» / «с расчетом» / «по расчету» / «за перерасчет»
as a folder wipe, and do not treat «1-го расчета» as document id 1.

«Расчетный счет» is a bank-account phrase and does not match. A folder titled
«Расчет» does not match. «Требование», «пояснение», «лицензия», and
«свидетельство» are different nouns.
"""

from __future__ import annotations

import re

# «расчет», «расчета», «расчету», «расчетом», «расчете», «расчеты», «расчетов»,
# «расчетам», «расчетами», «расчетах», plus «перерасчет…» and «ё» spellings.
# Longer endings come first. Trailing (?![а-яё]) is applied at the call site
# so «расчетный» does not steal the noun slot.
_CALCULATION = r"(?:пере)?расч[её]т(?:ами|ах|ам|ом|ов|у|е|а|ы)?"

_DEMONSTRATIVE = (
    r"(?:этими|этих|этот|этого|этому|этой|этом|эта|эту|эти|это|"
    r"прошл\w{0,4}|текущ\w{0,4}|данн\w{0,4}|сво\w{0,4})\s+"
)

_WORD_ORDINAL = (
    r"(?:перв(?:ое|ого|ому|ым|ом|ая|ую|ой|ый|ые|ых|ыми)|втор(?:ое|ого|ому|ым|ом|ая|ую|ой|ый|ые|ых|ыми)|"
    r"трет(?:ье|ьего|ьему|ьим|ьем|ья|ью|ьей|ий|ьи|ьих|ьими)|четв[её]рт(?:ое|ого|ому|ым|ом|ая|ую|ой|ый|ые|ых|ыми))"
)

# One qualifier word: «подробный расчет», «уточненный расчет».
_ADJ_WORD = (
    r"(?:[а-яё]{3,}-)?[а-яё]{3,}(?:ый|ий|ой|ая|яя|ое|ее|ые|ие|ого|его|ому|ему|ым|им|ом|ем|ую|юю|ых|их|ыми|ими)"
)

_QUAL = rf"(?:{_DEMONSTRATIVE}|{_WORD_ORDINAL}\s+|{_ADJ_WORD}\s+)"

# «с/со» is idiomatic («документы с расчетом»). «во» before «в», «со» before «с».
_PREP = re.compile(
    rf"(?<![а-яё])(?:за|на|во|по|со|в|с)\s+(?:{_QUAL}){{0,3}}(?<![а-яё]){_CALCULATION}(?![а-яё])",
    re.IGNORECASE,
)

_DURING = re.compile(
    rf"во\s+время\s+(?:{_QUAL}){{0,3}}(?<![а-яё]){_CALCULATION}(?![а-яё])",
    re.IGNORECASE,
)

_DEMONSTRATIVE_SCOPE = re.compile(
    rf"(?:этими|этих|этот|этого|этому|этой|этом|эта|эту|эти|"
    r"прошлые|прошлых|прошлый|прошлого|прошлая|прошлую|прошлое|"
    r"текущие|текущих|текущий|текущего|текущая|текущую|текущее|"
    r"данные|данных|данного)\s+"
    rf"(?:{_QUAL}){{0,2}}(?<![а-яё]){_CALCULATION}(?![а-яё])",
    re.IGNORECASE,
)

_ORDINAL_WORD = re.compile(
    rf"(?:за|в|во|на|по|с|со)\s+{_WORD_ORDINAL}\s+(?:{_QUAL}){{0,2}}(?<![а-яё]){_CALCULATION}(?![а-яё])"
    rf"|\b{_WORD_ORDINAL}\s+(?:{_QUAL}){{0,2}}(?<![а-яё]){_CALCULATION}(?![а-яё])",
    re.IGNORECASE,
)

# «1-го расчета», «1-й расчет». Two digits so ids like 214 stay ids.
_ORDINAL_NUM = re.compile(
    rf"\b\d{{1,2}}(?:-?(?:го|му|ой|ую|й|е|я|ю|о|м|х|ем))?\s*(?:{_QUAL}){{0,2}}(?<![а-яё]){_CALCULATION}(?![а-яё])",
    re.IGNORECASE,
)

# «документы расчета» — genitive scope, not a folder titled «Расчет».
_DOCS = re.compile(
    rf"(?:документ|файл)\w*\s+(?:{_QUAL}){{0,3}}(?<![а-яё]){_CALCULATION}(?![а-яё])",
    re.IGNORECASE,
)

# «расчетные документы» / «документы расчетные». Not «расчетный счет».
_CALCULATION_ADJ = r"(?:пере)?расч[её]тн(?:ый|ая|ое|ые|ого|ому|ым|ом|ую|ой|ых|ыми)"
_ADJ_DOCS = re.compile(
    rf"(?:{_CALCULATION_ADJ}\s+(?:документ|файл)\w*|(?:документ|файл)\w*\s+{_CALCULATION_ADJ})(?![а-яё])",
    re.IGNORECASE,
)

DELETE_REFUSED_CALCULATION = (
    "Не удаляю файлы по расчёту "
    "вроде «за расчет» / «за перерасчет» / «с расчетом» / «по расчету» / "
    "«1-го расчета» — это не номер документа и не команда очистить всю папку. "
    "Укажите id: «удали документ 214» или «удали документы [12] [18]». "
    "Чтобы очистить открытую папку целиком, напишите «удали все документы в этой папке» "
    "без слова «расчет»."
)

MOVE_REFUSED_CALCULATION = (
    "Не переношу все файлы папки по расчёту "
    "вроде «за расчет» / «за перерасчет» / «с расчетом» / «по расчету». "
    "Укажите id: «перенеси документ 214 в дело …». "
    "Чтобы перенести всю открытую папку, напишите без слова «расчет»: "
    "«перенеси все документы в папку …»."
)


def mask_calculation_ordinals(text: str) -> str:
    """Replace «1-го расчета» so the leading digit cannot be parsed as a document id."""
    return _ORDINAL_NUM.sub(" ", text or "")


def looks_like_calculation_scoped_document_request(text: str) -> bool:
    """True when the user scoped files to a расчет / перерасчет."""
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


def calculation_blocks_bulk_document_mutation(
    text: str, *, explicit_document_ids: list[int] | None = None
) -> bool:
    """Refuse folder-wide delete/move when a calculation scope is present.

    Chat treated «удали все документы за расчет в этой папке» as wipe-the-folder
    because «все документы» matched wants_all and the document-type phrase was ignored.
    «удали документы 1-го расчета» took the first digit as a document id.
    """
    if explicit_document_ids:
        return False
    return looks_like_calculation_scoped_document_request(text)
