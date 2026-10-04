"""Reply / refusal / consent (ответ / отказ / согласие) chat scope.

Do not treat «за ответ» / «по отказу» / «с согласием» / «за несогласие»
as a folder wipe, and do not treat «1-го ответа» / «1-го отказа» /
«1-го согласия» as document id 1.

A folder titled «Ответ», «Отказ», or «Согласие» does not match.
«без ответа», «дай ответ», «ответчик», «соглашение», and «отзыв»
do not match. «Запрос» remains a separate guard.
"""

from __future__ import annotations

import re

# «ответ». Longer endings first so «ответами» is not cut at «а».
# «ответчик» / «ответственность» / «соответствие» do not match: the stem
# must end on a non-letter, and a preceding letter blocks the lookbehind.
_REPLY = r"ответ(?:ами|ах|ам|ов|ом|а|у|е|ы)?"

# «отказ». «отказаться» / «отказал» do not match.
_REFUSAL = r"отказ(?:ами|ах|ам|ов|ом|а|у|е|ы)?"

# «согласие» / «несогласие». «соглашение» / «согласование» / «согласно» do not match.
_CONSENT = r"(?:не)?согласи(?:ями|ях|ям|ем|е|я|ю|й|и)"

_REPLY_ADJ = r"ответн(?:ыми|ый|ая|ое|ые|ого|ому|ым|ом|ую|ой|ых)"
_REFUSAL_ADJ = r"отказн(?:ыми|ой|ая|ое|ые|ого|ому|ым|ом|ую|ых)"
_CONSENT_ADJ = r"согласительн(?:ыми|ый|ая|ое|ые|ого|ому|ым|ом|ую|ой|ых)"
_ADJ = rf"(?:{_REPLY_ADJ}|{_REFUSAL_ADJ}|{_CONSENT_ADJ})"

_NOTE = r"записк(?:ою|ами|ах|ам|ой|ок|а|у|и|е)"
_LETTER = r"(?:письм(?:ами|ах|ам|ом|о|а|у|е)|писем)"
_PAPER = rf"{_ADJ}\s+(?:{_LETTER}|{_NOTE})"

_TARGET = rf"(?:{_PAPER}|{_CONSENT}|{_REPLY}|{_REFUSAL})"

_DEMONSTRATIVE = (
    r"(?:этими|этих|этот|этого|этому|этой|этом|эта|эту|эти|это|"
    r"прошл\w{0,4}|текущ\w{0,4}|данн\w{0,4}|сво\w{0,4})\s+"
)

_WORD_ORDINAL = (
    r"(?:перв(?:ое|ого|ому|ым|ом|ая|ую|ой|ый|ые|ых|ыми)|втор(?:ое|ого|ому|ым|ом|ая|ую|ой|ый|ые|ых|ыми)|"
    r"трет(?:ье|ьего|ьему|ьим|ьем|ья|ью|ьей|ий|ьи|ьих|ьими)|четв[её]рт(?:ое|ого|ому|ым|ом|ая|ую|ой|ый|ые|ых|ыми))"
)

# One qualifier word: «письменный ответ», «мотивированный отказ», «нотариальное согласие».
_ADJ_WORD = (
    r"(?:[а-яё]{3,}-)?[а-яё]{3,}(?:ыми|ими|ый|ий|ой|ая|яя|ое|ее|ые|ие|ого|его|ому|ему|ым|им|ом|ем|ую|юю|ых|их)"
)

_QUAL = rf"(?:{_DEMONSTRATIVE}|{_WORD_ORDINAL}\s+|{_ADJ_WORD}\s+)"

_ORDINAL_SUFFIX = r"(?:го|му|ой|ую|й|е|я|ю|о|м|х|ем)"

# «об» / «во» / «со» before the shorter forms. «о» is the preposition in «об отказе».
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

# «1-го ответа», «1-й отказ», «2-е согласие».
# Two digits so ids like 214 stay ids. (?!\d) so a longer number is not sliced.
_ORDINAL_NUM = re.compile(
    rf"\b\d{{1,2}}(?!\d)(?:-?{_ORDINAL_SUFFIX})?\s*(?:{_QUAL}){{0,2}}(?<![а-яё]){_TARGET}(?![а-яё])",
    re.IGNORECASE,
)

# «документы ответа» — genitive scope, not a folder titled «Ответ».
_DOCS = re.compile(
    rf"(?:документ|файл)\w*\s+(?:{_QUAL}){{0,3}}(?<![а-яё]){_TARGET}(?![а-яё])",
    re.IGNORECASE,
)

# «ответные документы» / «документы отказные» / «согласительные документы».
_ADJ_DOCS = re.compile(
    rf"(?:{_ADJ}\s+(?:документ|файл)\w*|(?:документ|файл)\w*\s+{_ADJ})(?![а-яё])",
    re.IGNORECASE,
)

DELETE_REFUSED_REPLY = (
    "Не удаляю файлы по виду «ответ» / «отказ» / «согласие» "
    "вроде «за ответ» / «по отказу» / «с согласием» / «за несогласие» / "
    "«1-го ответа» / «1-го отказа» / «1-го согласия» — "
    "это не номер документа и не команда очистить всю папку. "
    "Укажите id: «удали документ 214» или «удали документы [12] [18]». "
    "Чтобы очистить открытую папку целиком, напишите «удали все документы в этой папке» "
    "без этих слов."
)

MOVE_REFUSED_REPLY = (
    "Не переношу все файлы папки по виду «ответ» / «отказ» / «согласие» "
    "вроде «за ответ» / «по отказу» / «с согласием» / «за несогласие». "
    "Укажите id: «перенеси документ 214 в дело …». "
    "Чтобы перенести всю открытую папку, напишите без этих слов: "
    "«перенеси все документы в папку …»."
)


def mask_reply_ordinals(text: str) -> str:
    """Replace «1-го ответа» so the digit is not a document id."""
    return _ORDINAL_NUM.sub(" ", text or "")


def looks_like_reply_scoped_document_request(text: str) -> bool:
    """True when the user scoped files to an ответ / отказ / согласие."""
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


def reply_blocks_bulk_document_mutation(
    text: str, *, explicit_document_ids: list[int] | None = None
) -> bool:
    """Refuse folder-wide delete/move when an ответ / отказ / согласие scope is present.

    Chat treated «удали все документы за ответ в этой папке» as
    wipe-the-folder because «все документы» matched wants_all and the
    document-type phrase was ignored. «удали документы 1-го ответа»
    took the first digit as a document id. The same path hits «отказ»
    and «согласие».
    """
    if explicit_document_ids:
        return False
    return looks_like_reply_scoped_document_request(text)
