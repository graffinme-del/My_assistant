"""Guarantee / suretyship / acceptance (гарантия / поручительство / акцепт) chat scope.

Do not treat «за гарантию» / «за гарантийное письмо» / «за поручительство» /
«за акцепт» as a folder wipe, and do not treat «1-й гарантии» /
«1-го поручительства» / «1-го акцепта» as document id 1.

A folder titled «Гарантия», «Поручительство», or «Акцепт» does not match.
«без гарантии», «гарантировать», «акцептовать», and «поручение» do not match.
Bare «письмо» remains the correspondence guard. «Договор» remains the contract guard.
"""

from __future__ import annotations

import re

# «гарантия». Longer endings first. «гарантировать» / «гарантийный» do not match:
# the stem must end on a non-letter.
_GUARANTEE = r"гаранти(?:ями|ях|ям|ею|ей|ю|я|и|й|е)"

# «поручительство». Empty ending is the genitive plural «поручительств».
# «поручение» and «поручитель» do not contain this stem.
_SURETY = r"поручительств(?:ами|ах|ам|ом|у|о|а|е)?"

# «акцепт». «акцептовать» / «акцептован» do not match.
_ACCEPTANCE = r"акцепт(?:ами|ах|ам|ов|ом|а|у|е|ы)?"

_GUARANTEE_ADJ = r"гарантий(?:н(?:ыми|ый|ая|ое|ые|ого|ому|ым|ом|ую|ой|ых))"
_SURETY_ADJ = r"поручительск(?:ими|ий|ая|ое|ие|ого|ому|им|ом|ую|ой|их)"
_ACCEPT_ADJ = r"акцепт(?:н(?:ыми|ый|ая|ое|ые|ого|ому|ым|ом|ую|ой|ых))"
_ADJ = rf"(?:{_GUARANTEE_ADJ}|{_SURETY_ADJ}|{_ACCEPT_ADJ})"

_NOTE = r"записк(?:ою|ами|ах|ам|ой|ок|а|у|и|е)"
_LETTER = r"(?:письм(?:ами|ах|ам|ом|о|а|у|е)|писем)"
# «гарантийное письмо» is the instrument name, not every letter.
_PAPER = rf"{_GUARANTEE_ADJ}\s+(?:{_LETTER}|{_NOTE})"

_TARGET = rf"(?:{_PAPER}|{_SURETY}|{_GUARANTEE}|{_ACCEPTANCE})"

_DEMONSTRATIVE = (
    r"(?:этими|этих|этот|этого|этому|этой|этом|эта|эту|эти|это|"
    r"прошл\w{0,4}|текущ\w{0,4}|данн\w{0,4}|сво\w{0,4})\s+"
)

_WORD_ORDINAL = (
    r"(?:перв(?:ое|ого|ому|ым|ом|ая|ую|ой|ый|ые|ых|ыми)|втор(?:ое|ого|ому|ым|ом|ая|ую|ой|ый|ые|ых|ыми)|"
    r"трет(?:ье|ьего|ьему|ьим|ьем|ья|ью|ьей|ий|ьи|ьих|ьими)|четв[её]рт(?:ое|ого|ому|ым|ом|ая|ую|ой|ый|ые|ых|ыми))"
)

# One qualifier word: «банковская гарантия», «нотариальное поручительство».
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

# «1-й гарантии», «1-го поручительства», «1-го акцепта».
# Two digits so ids like 214 stay ids. (?!\d) so a longer number is not sliced.
_ORDINAL_NUM = re.compile(
    rf"\b\d{{1,2}}(?!\d)(?:-?{_ORDINAL_SUFFIX})?\s*(?:{_QUAL}){{0,2}}(?<![а-яё]){_TARGET}(?![а-яё])",
    re.IGNORECASE,
)

# «документы гарантии» — genitive scope, not a folder titled «Гарантия».
_DOCS = re.compile(
    rf"(?:документ|файл)\w*\s+(?:{_QUAL}){{0,3}}(?<![а-яё]){_TARGET}(?![а-яё])",
    re.IGNORECASE,
)

# «гарантийные документы» / «документы акцептные».
_ADJ_DOCS = re.compile(
    rf"(?:(?<![а-яё]){_ADJ}\s+(?:документ|файл)\w*|(?:документ|файл)\w*\s+(?<![а-яё]){_ADJ})(?![а-яё])",
    re.IGNORECASE,
)

DELETE_REFUSED_REPLY = (
    "Не удаляю файлы по виду «гарантия» / «поручительство» / «акцепт» "
    "вроде «за гарантию» / «за гарантийное письмо» / «за поручительство» / «за акцепт» / "
    "«1-й гарантии» / «1-го поручительства» / «1-го акцепта» — "
    "это не номер документа и не команда очистить всю папку. "
    "Укажите id: «удали документ 214» или «удали документы [12] [18]». "
    "Чтобы очистить открытую папку целиком, напишите «удали все документы в этой папке» "
    "без этих слов."
)

MOVE_REFUSED_REPLY = (
    "Не переношу все файлы папки по виду «гарантия» / «поручительство» / «акцепт» "
    "вроде «за гарантию» / «за гарантийное письмо» / «за поручительство» / «за акцепт». "
    "Укажите id: «перенеси документ 214 в дело …». "
    "Чтобы перенести всю открытую папку, напишите без этих слов: "
    "«перенеси все документы в папку …»."
)


def mask_guarantee_ordinals(text: str) -> str:
    """Replace «1-й гарантии» so the digit is not a document id."""
    return _ORDINAL_NUM.sub(" ", text or "")


def looks_like_guarantee_scoped_document_request(text: str) -> bool:
    """True when the user scoped files to a гарантия / поручительство / акцепт."""
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


def guarantee_blocks_bulk_document_mutation(
    text: str, *, explicit_document_ids: list[int] | None = None
) -> bool:
    """Refuse folder-wide delete/move when a guarantee scope is present.

    Chat treated «удали все документы за гарантию в этой папке» as
    wipe-the-folder because «все документы» matched wants_all and the
    document-type phrase was ignored. «удали документы 1-й гарантии»
    took the first digit as a document id. The same path hits
    «поручительство» and «акцепт».
    """
    if explicit_document_ids:
        return False
    return looks_like_guarantee_scoped_document_request(text)
