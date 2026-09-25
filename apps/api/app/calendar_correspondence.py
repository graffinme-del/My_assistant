"""Letter / notice / summons chat scope.

Do not treat «за письмо» / «за уведомление» / «за извещение» / «за повестку»
as a folder wipe, and do not treat «1-го письма» as document id 1.
"""

from __future__ import annotations

import re

# «письмо» (all cases, including irregular «писем»), then уведомление / извещение / повестка.
# Trailing (?![а-яё]) is applied at the call site so «письменный», «уведомить»,
# «известить», and «повесть» do not match.
_CORR_NOUN = (
    r"(?:письм(?:ами|ах|ам|ом|у|е|о|а)|писем"
    r"|уведомлени(?:ями|ях|ям|ем|ю|я|и|й|е)"
    r"|извещени(?:ями|ях|ям|ем|ю|я|и|й|е)"
    r"|повестк(?:ами|ах|ам|ою|ой|ок|а|у|е|и))"
)

_DEMONSTRATIVE = (
    r"(?:этими|этих|этот|этого|этому|этой|этом|эта|эту|эти|это|"
    r"прошл\w{0,4}|текущ\w{0,4}|данн\w{0,4}|сво\w{0,4})\s+"
)

_WORD_ORDINAL = (
    r"(?:перв(?:ое|ого|ому|ым|ом|ая|ую|ой|ый|ые|ых|ыми)|втор(?:ое|ого|ому|ым|ом|ая|ую|ой|ый|ые|ых|ыми)|"
    r"трет(?:ье|ьего|ьему|ьим|ьем|ья|ью|ьей|ий|ьи|ьих|ьими)|четв[её]рт(?:ое|ого|ому|ым|ом|ая|ую|ой|ый|ые|ых|ыми))"
)

# One qualifier word: «гарантийное письмо», «судебная повестка», «почтовое уведомление».
_ADJ_WORD = (
    r"[а-яё]{3,}(?:ый|ий|ой|ая|яя|ое|ее|ые|ие|ого|его|ому|ему|ым|им|ом|ем|ую|юю|ых|их|ыми|ими)"
)

_QUAL = rf"(?:{_DEMONSTRATIVE}|{_WORD_ORDINAL}\s+|{_ADJ_WORD}\s+)"

_PREP_CORR = re.compile(
    rf"(?<![а-яё])(?:за|на|в|во|по)\s+(?:{_QUAL}){{0,3}}(?<![а-яё]){_CORR_NOUN}(?![а-яё])",
    re.IGNORECASE,
)

_DURING_CORR = re.compile(
    rf"во\s+время\s+(?:{_QUAL}){{0,3}}(?<![а-яё]){_CORR_NOUN}(?![а-яё])",
    re.IGNORECASE,
)

_DEMONSTRATIVE_CORR = re.compile(
    rf"(?:этими|этих|этот|этого|этому|этой|этом|эта|эту|эти|"
    r"прошлые|прошлых|прошлый|прошлого|прошлая|прошлую|прошлое|"
    r"текущие|текущих|текущий|текущего|текущая|текущую|текущее|"
    r"данные|данных|данного)\s+"
    rf"(?:{_QUAL}){{0,2}}(?<![а-яё]){_CORR_NOUN}(?![а-яё])",
    re.IGNORECASE,
)

_ORDINAL_CORR_WORD = re.compile(
    rf"(?:за|в|во|на|по)\s+{_WORD_ORDINAL}\s+(?:{_QUAL}){{0,2}}(?<![а-яё]){_CORR_NOUN}(?![а-яё])"
    rf"|\b{_WORD_ORDINAL}\s+(?:{_QUAL}){{0,2}}(?<![а-яё]){_CORR_NOUN}(?![а-яё])",
    re.IGNORECASE,
)

# «1-го письма», «1-е уведомление», «1-й повестки». Two digits so ids like 214 stay ids.
_ORDINAL_CORR_NUM = re.compile(
    rf"\b\d{{1,2}}(?:-?(?:го|му|ой|ую|й|е|я|ю|о|м|х|ем))?\s*(?:{_QUAL}){{0,2}}(?<![а-яё]){_CORR_NOUN}(?![а-яё])",
    re.IGNORECASE,
)

# «документы письма» / «документы повестки» — genitive scope, not a folder titled «Письмо».
_CORR_DOCS = re.compile(
    rf"(?:документ|файл)\w*\s+(?:{_QUAL}){{0,3}}(?<![а-яё]){_CORR_NOUN}(?![а-яё])",
    re.IGNORECASE,
)

DELETE_REFUSED_CORRESPONDENCE = (
    "Не удаляю файлы по письму / уведомлению / извещению / повестке "
    "вроде «за письмо» / «за уведомление» / «за извещение» / «за повестку» / "
    "«1-го письма» — это не номер документа и не команда очистить всю папку. "
    "Укажите id: «удали документ 214» или «удали документы [12] [18]». "
    "Чтобы очистить открытую папку целиком, напишите «удали все документы в этой папке» "
    "без письма, уведомления, извещения и повестки."
)

MOVE_REFUSED_CORRESPONDENCE = (
    "Не переношу все файлы папки по письму / уведомлению / извещению / повестке "
    "вроде «за письмо» / «за уведомление» / «за извещение» / «за повестку». "
    "Укажите id: «перенеси документ 214 в дело …». "
    "Чтобы перенести всю открытую папку, напишите без письма и повестки: "
    "«перенеси все документы в папку …»."
)


def mask_correspondence_ordinals(text: str) -> str:
    """Replace «1-го письма» so the leading digit cannot be parsed as a document id."""
    return _ORDINAL_CORR_NUM.sub(" ", text or "")


def looks_like_correspondence_scoped_document_request(text: str) -> bool:
    """True when the user scoped files to a letter, notice, summons, or notification."""
    raw = text or ""
    if (
        _PREP_CORR.search(raw)
        or _DURING_CORR.search(raw)
        or _DEMONSTRATIVE_CORR.search(raw)
        or _ORDINAL_CORR_WORD.search(raw)
        or _ORDINAL_CORR_NUM.search(raw)
        or _CORR_DOCS.search(raw)
    ):
        return True
    return False


def correspondence_blocks_bulk_document_mutation(
    text: str, *, explicit_document_ids: list[int] | None = None
) -> bool:
    """Refuse folder-wide delete/move when a letter/notice/summons scope is present.

    Chat used to treat «удали все документы за письмо в этой папке» as wipe-the-folder because
    «все документы» matched wants_all and the document-type phrase was ignored. «удали документы
    1-го письма» took the first digit as a document id.
    """
    if explicit_document_ids:
        return False
    return looks_like_correspondence_scoped_document_request(text)
