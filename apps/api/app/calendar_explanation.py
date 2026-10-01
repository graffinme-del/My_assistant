"""Explanation / license / certificate chat scope.

Do not treat «за пояснение» / «с пояснениями» / «за пояснительную записку» /
«за лицензию» / «по лицензии» / «за свидетельство» / «со свидетельством» as a
folder wipe, and do not treat «1-го пояснения», «1-й лицензии», or
«1-го свидетельства» as document id 1.

A folder titled «Пояснение», «Лицензия», or «Свидетельство» does not match.
«без пояснений» and a bare «дай пояснение» do not match. «Требование» remains
a separate guard.
"""

from __future__ import annotations

import re

# «пояснение» and case forms. Same neuter -ение declension as «требование».
_NOUN_END = r"(?:ями|ях|ям|ем|й|ю|я|и|е)"
_EXPL = rf"пояснени{_NOUN_END}"

# «лицензия», «лицензии», «лицензию», «лицензией», «лицензиею», «лицензий»,
# «лицензиям», «лицензиями», «лицензиях», and the compound «гослицензия».
# Not «лицензионный» / «лицензиат».
_LICENSE = r"(?:гос)?лицензи(?:ями|ях|ям|ею|ей|ю|я|и|й)"

# «свидетельство» and case forms, including genitive plural «свидетельств».
# Not «свидетель» and not «свидетельствовать».
_CERT = r"свидетельств(?:ами|ах|ам|ом|а|у|е|о)?"

_NOUN = rf"(?:{_EXPL}|{_LICENSE}|{_CERT})"

# «пояснительная записка» is the document name users type instead of «пояснение».
_EXPL_ADJ = r"пояснительн(?:ыми|ый|ая|ое|ые|ого|ому|ым|ом|ую|ой|ых)"
_NOTE = r"записк(?:ою|ами|ах|ам|ой|ок|а|у|и|е)"
_EXPL_NOTE = rf"{_EXPL_ADJ}\s+{_NOTE}"

_LIC_ADJ = r"лицензионн(?:ыми|ый|ая|ое|ые|ого|ому|ым|ом|ую|ой|ых)"
_CERT_ADJ = r"свидетельск(?:ими|ий|ая|ое|ие|ого|ому|им|ом|ую|ой|их)"
_PAPER_ADJ = rf"(?:{_EXPL_ADJ}|{_LIC_ADJ}|{_CERT_ADJ})"

_TARGET = rf"(?:{_EXPL_NOTE}|{_NOUN})"

_DEMONSTRATIVE = (
    r"(?:этими|этих|этот|этого|этому|этой|этом|эта|эту|эти|это|"
    r"прошл\w{0,4}|текущ\w{0,4}|данн\w{0,4}|сво\w{0,4})\s+"
)

_WORD_ORDINAL = (
    r"(?:перв(?:ое|ого|ому|ым|ом|ая|ую|ой|ый|ые|ых|ыми)|втор(?:ое|ого|ому|ым|ом|ая|ую|ой|ый|ые|ых|ыми)|"
    r"трет(?:ье|ьего|ьему|ьим|ьем|ья|ью|ьей|ий|ьи|ьих|ьими)|четв[её]рт(?:ое|ого|ому|ым|ом|ая|ую|ой|ый|ые|ых|ыми))"
)

# One qualifier word: «письменные пояснения», «дополнительная лицензия».
_ADJ_WORD = (
    r"(?:[а-яё]{3,}-)?[а-яё]{3,}(?:ыми|ими|ый|ий|ой|ая|яя|ое|ее|ые|ие|ого|его|ому|ему|ым|им|ом|ем|ую|юю|ых|их)"
)

_QUAL = rf"(?:{_DEMONSTRATIVE}|{_WORD_ORDINAL}\s+|{_ADJ_WORD}\s+)"

_ORDINAL_SUFFIX = r"(?:го|му|ой|ую|й|е|я|ю|о|м|х|ем)"

# «с/со» is idiomatic («документы с пояснениями», «со свидетельством»).
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

# «1-го пояснения», «1-й лицензии», «1-е свидетельство», «1-й пояснительной записки».
# Two digits so ids like 214 stay ids. (?!\d) so a longer number is not sliced.
_ORDINAL_NUM = re.compile(
    rf"\b\d{{1,2}}(?!\d)(?:-?{_ORDINAL_SUFFIX})?\s*(?:{_QUAL}){{0,2}}(?<![а-яё]){_TARGET}(?![а-яё])",
    re.IGNORECASE,
)

# «документы пояснения» — genitive scope, not a folder titled «Пояснение».
_DOCS = re.compile(
    rf"(?:документ|файл)\w*\s+(?:{_QUAL}){{0,3}}(?<![а-яё]){_TARGET}(?![а-яё])",
    re.IGNORECASE,
)

# «пояснительные документы» / «лицензионные документы» / «документы свидетельские».
_ADJ_DOCS = re.compile(
    rf"(?:{_PAPER_ADJ}\s+(?:документ|файл)\w*|(?:документ|файл)\w*\s+{_PAPER_ADJ})(?![а-яё])",
    re.IGNORECASE,
)

DELETE_REFUSED_EXPLANATION = (
    "Не удаляю файлы по виду «пояснение», «лицензия» или «свидетельство» "
    "вроде «за пояснение» / «с пояснениями» / «за пояснительную записку» / "
    "«за лицензию» / «по лицензии» / «за свидетельство» / «со свидетельством» / "
    "«1-го пояснения» / «1-й лицензии» / «1-го свидетельства» — "
    "это не номер документа и не команда очистить всю папку. "
    "Укажите id: «удали документ 214» или «удали документы [12] [18]». "
    "Чтобы очистить открытую папку целиком, напишите «удали все документы в этой папке» "
    "без этих слов."
)

MOVE_REFUSED_EXPLANATION = (
    "Не переношу все файлы папки по виду «пояснение», «лицензия» или «свидетельство» "
    "вроде «за пояснение» / «с пояснениями» / «за пояснительную записку» / "
    "«за лицензию» / «за свидетельство». "
    "Укажите id: «перенеси документ 214 в дело …». "
    "Чтобы перенести всю открытую папку, напишите без этих слов: "
    "«перенеси все документы в папку …»."
)


def mask_explanation_ordinals(text: str) -> str:
    """Replace «1-го пояснения» / «1-й лицензии» / «1-го свидетельства» so the digit is not a document id."""
    return _ORDINAL_NUM.sub(" ", text or "")


def looks_like_explanation_scoped_document_request(text: str) -> bool:
    """True when the user scoped files to a пояснение, лицензия, or свидетельство."""
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


def explanation_blocks_bulk_document_mutation(
    text: str, *, explicit_document_ids: list[int] | None = None
) -> bool:
    """Refuse folder-wide delete/move when an explanation, license, or certificate scope is present.

    Chat treated «удали все документы за пояснение в этой папке» (and the same
    sentence with «лицензию» or «свидетельство») as wipe-the-folder because
    «все документы» matched wants_all and the document-type phrase was ignored.
    «удали документы 1-го пояснения» took the first digit as a document id.
    """
    if explicit_document_ids:
        return False
    return looks_like_explanation_scoped_document_request(text)
