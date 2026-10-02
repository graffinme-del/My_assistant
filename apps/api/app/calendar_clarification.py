"""Clarification (разъяснение) chat scope.

Do not treat «за разъяснение» / «с разъяснениями» / «по разъяснению» /
«за разъяснительное письмо» as a folder wipe, and do not treat
«1-го разъяснения» as document id 1.

A folder titled «Разъяснение» does not match. «без разъяснений» and a bare
«дай разъяснение» do not match. «Пояснение» / «объяснение» remain a separate guard.
"""

from __future__ import annotations

import re

# «разъяснение» and case forms. Same neuter -ение declension as «пояснение».
# «пояснение» and «объяснение» are different nouns and are not matched.
_NOUN_END = r"(?:ями|ях|ям|ем|й|ю|я|и|е)"
_CLAR = rf"разъяснени{_NOUN_END}"

# «разъяснительное письмо» / «разъяснительная записка».
_CLAR_ADJ = r"разъяснительн(?:ыми|ый|ая|ое|ые|ого|ому|ым|ом|ую|ой|ых)"
_NOTE = r"записк(?:ою|ами|ах|ам|ой|ок|а|у|и|е)"
_LETTER = r"(?:письм(?:ами|ах|ам|ом|о|а|у|е)|писем)"
_CLAR_PAPER = rf"{_CLAR_ADJ}\s+(?:{_LETTER}|{_NOTE})"

_TARGET = rf"(?:{_CLAR_PAPER}|{_CLAR})"

_DEMONSTRATIVE = (
    r"(?:этими|этих|этот|этого|этому|этой|этом|эта|эту|эти|это|"
    r"прошл\w{0,4}|текущ\w{0,4}|данн\w{0,4}|сво\w{0,4})\s+"
)

_WORD_ORDINAL = (
    r"(?:перв(?:ое|ого|ому|ым|ом|ая|ую|ой|ый|ые|ых|ыми)|втор(?:ое|ого|ому|ым|ом|ая|ую|ой|ый|ые|ых|ыми)|"
    r"трет(?:ье|ьего|ьему|ьим|ьем|ья|ью|ьей|ий|ьи|ьих|ьими)|четв[её]рт(?:ое|ого|ому|ым|ом|ая|ую|ой|ый|ые|ых|ыми))"
)

# One qualifier word: «письменное разъяснение», «дополнительное разъяснение».
_ADJ_WORD = (
    r"(?:[а-яё]{3,}-)?[а-яё]{3,}(?:ыми|ими|ый|ий|ой|ая|яя|ое|ее|ые|ие|ого|его|ому|ему|ым|им|ом|ем|ую|юю|ых|их)"
)

_QUAL = rf"(?:{_DEMONSTRATIVE}|{_WORD_ORDINAL}\s+|{_ADJ_WORD}\s+)"

_ORDINAL_SUFFIX = r"(?:го|му|ой|ую|й|е|я|ю|о|м|х|ем)"

# «с/со» is idiomatic («документы с разъяснениями»).
# «во» before «в», «со» before «с».
_PREP = re.compile(
    rf"(?<![а-яё])(?:за|на|во|по|со|в|с)\s+(?:{_QUAL}){{0,3}}(?<![а-яё]){_TARGET}(?![а-яё])",
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
    rf"(?:за|в|во|на|по|с|со)\s+{_WORD_ORDINAL}\s+(?:{_QUAL}){{0,2}}(?<![а-яё]){_TARGET}(?![а-яё])"
    rf"|\b{_WORD_ORDINAL}\s+(?:{_QUAL}){{0,2}}(?<![а-яё]){_TARGET}(?![а-яё])",
    re.IGNORECASE,
)

# «1-го разъяснения», «1-е разъяснение», «2-го разъяснительного письма».
# Two digits so ids like 214 stay ids. (?!\d) so a longer number is not sliced.
_ORDINAL_NUM = re.compile(
    rf"\b\d{{1,2}}(?!\d)(?:-?{_ORDINAL_SUFFIX})?\s*(?:{_QUAL}){{0,2}}(?<![а-яё]){_TARGET}(?![а-яё])",
    re.IGNORECASE,
)

# «документы разъяснения» — genitive scope, not a folder titled «Разъяснение».
_DOCS = re.compile(
    rf"(?:документ|файл)\w*\s+(?:{_QUAL}){{0,3}}(?<![а-яё]){_TARGET}(?![а-яё])",
    re.IGNORECASE,
)

# «разъяснительные документы» / «документы разъяснительные».
_ADJ_DOCS = re.compile(
    rf"(?:{_CLAR_ADJ}\s+(?:документ|файл)\w*|(?:документ|файл)\w*\s+{_CLAR_ADJ})(?![а-яё])",
    re.IGNORECASE,
)

DELETE_REFUSED_CLARIFICATION = (
    "Не удаляю файлы по виду «разъяснение» "
    "вроде «за разъяснение» / «с разъяснениями» / «по разъяснению» / "
    "«за разъяснительное письмо» / «1-го разъяснения» — "
    "это не номер документа и не команда очистить всю папку. "
    "Укажите id: «удали документ 214» или «удали документы [12] [18]». "
    "Чтобы очистить открытую папку целиком, напишите «удали все документы в этой папке» "
    "без этих слов."
)

MOVE_REFUSED_CLARIFICATION = (
    "Не переношу все файлы папки по виду «разъяснение» "
    "вроде «за разъяснение» / «с разъяснениями» / «по разъяснению» / "
    "«за разъяснительное письмо». "
    "Укажите id: «перенеси документ 214 в дело …». "
    "Чтобы перенести всю открытую папку, напишите без этих слов: "
    "«перенеси все документы в папку …»."
)


def mask_clarification_ordinals(text: str) -> str:
    """Replace «1-го разъяснения» so the digit is not a document id."""
    return _ORDINAL_NUM.sub(" ", text or "")


def looks_like_clarification_scoped_document_request(text: str) -> bool:
    """True when the user scoped files to a разъяснение."""
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


def clarification_blocks_bulk_document_mutation(
    text: str, *, explicit_document_ids: list[int] | None = None
) -> bool:
    """Refuse folder-wide delete/move when a разъяснение scope is present.

    Chat treated «удали все документы за разъяснение в этой папке» as
    wipe-the-folder because «все документы» matched wants_all and the
    document-type phrase was ignored. «удали документы 1-го разъяснения»
    took the first digit as a document id.
    """
    if explicit_document_ids:
        return False
    return looks_like_clarification_scoped_document_request(text)
