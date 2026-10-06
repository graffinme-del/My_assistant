"""Fine / contractual penalty / late fee (штраф / неустойка / пеня) chat scope.

Do not treat «за штраф» / «за неустойку» / «за пеню» / «за пени» as a folder
wipe, and do not treat «1-го штрафа» / «1-й неустойки» / «1-й пени» as
document id 1.

A folder titled «Штраф», «Неустойка», or «Пеня» does not match.
«без штрафа», «без неустойки», «без пени», «штрафовать», and «пенять» do not match.
Bare «санкции» and «пена» (foam) do not match. «Гарантия» remains a separate guard.
"""

from __future__ import annotations

import re

# «штраф». Longer endings first. «штрафовать» / «оштрафовать» do not match:
# the stem must end on a non-letter, and «оштрафовать» has a letter before the stem.
_FINE = r"штраф(?:ами|ах|ам|ов|ом|а|у|е|ы)?"

# «неустойка». Genitive plural is «неустоек» (the к drops).
_PENALTY = r"неустойк(?:ами|ах|ам|ою|ой|у|и|е|а)|неустоек"

# «пеня» / «пени». No empty ending, so «пен» does not match.
# No «а»/«у», so «пена» / «пену» (foam) do not match. «пенять» does not match.
_LATE_FEE = r"пен(?:ями|ях|ям|ею|ей|ю|я|и|е)"

_FINE_ADJ = r"штрафн(?:ыми|ый|ая|ое|ые|ого|ому|ым|ом|ую|ой|ых)"

# «штрафные санкции» is the instrument name. Bare «санкции» is not.
_SANCTION = rf"{_FINE_ADJ}\s+санкци(?:ями|ях|ям|ею|ей|ю|я|и|е|й)"

_TARGET = rf"(?:{_SANCTION}|{_PENALTY}|{_FINE}|{_LATE_FEE})"

_DEMONSTRATIVE = (
    r"(?:этими|этих|этот|этого|этому|этой|этом|эта|эту|эти|это|"
    r"прошл\w{0,4}|текущ\w{0,4}|данн\w{0,4}|сво\w{0,4})\s+"
)

_WORD_ORDINAL = (
    r"(?:перв(?:ое|ого|ому|ым|ом|ая|ую|ой|ый|ые|ых|ыми)|втор(?:ое|ого|ому|ым|ом|ая|ую|ой|ый|ые|ых|ыми)|"
    r"трет(?:ье|ьего|ьему|ьим|ьем|ья|ью|ьей|ий|ьи|ьих|ьими)|четв[её]рт(?:ое|ого|ому|ым|ом|ая|ую|ой|ый|ые|ых|ыми))"
)

# One qualifier word: «договорная неустойка», «административный штраф».
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

# «1-го штрафа», «1-й неустойки», «1-й пени».
# Two digits so ids like 214 stay ids. (?!\d) so a longer number is not sliced.
_ORDINAL_NUM = re.compile(
    rf"\b\d{{1,2}}(?!\d)(?:-?{_ORDINAL_SUFFIX})?\s*(?:{_QUAL}){{0,2}}(?<![а-яё]){_TARGET}(?![а-яё])",
    re.IGNORECASE,
)

# «документы штрафа» — genitive scope, not a folder titled «Штраф».
_DOCS = re.compile(
    rf"(?:документ|файл)\w*\s+(?:{_QUAL}){{0,3}}(?<![а-яё]){_TARGET}(?![а-яё])",
    re.IGNORECASE,
)

# «штрафные документы» / «документы штрафные».
_ADJ_DOCS = re.compile(
    rf"(?:(?<![а-яё]){_FINE_ADJ}\s+(?:документ|файл)\w*|(?:документ|файл)\w*\s+(?<![а-яё]){_FINE_ADJ})(?![а-яё])",
    re.IGNORECASE,
)

DELETE_REFUSED_REPLY = (
    "Не удаляю файлы по виду «штраф» / «неустойка» / «пеня» "
    "вроде «за штраф» / «за неустойку» / «за пеню» / «за пени» / "
    "«1-го штрафа» / «1-й неустойки» / «1-й пени» — "
    "это не номер документа и не команда очистить всю папку. "
    "Укажите id: «удали документ 214» или «удали документы [12] [18]». "
    "Чтобы очистить открытую папку целиком, напишите «удали все документы в этой папке» "
    "без этих слов."
)

MOVE_REFUSED_REPLY = (
    "Не переношу все файлы папки по виду «штраф» / «неустойка» / «пеня» "
    "вроде «за штраф» / «за неустойку» / «за пеню» / «за пени». "
    "Укажите id: «перенеси документ 214 в дело …». "
    "Чтобы перенести всю открытую папку, напишите без этих слов: "
    "«перенеси все документы в папку …»."
)


def mask_penalty_ordinals(text: str) -> str:
    """Replace «1-го штрафа» so the digit is not a document id."""
    return _ORDINAL_NUM.sub(" ", text or "")


def looks_like_penalty_scoped_document_request(text: str) -> bool:
    """True when the user scoped files to a штраф / неустойка / пеня."""
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


def penalty_blocks_bulk_document_mutation(
    text: str, *, explicit_document_ids: list[int] | None = None
) -> bool:
    """Refuse folder-wide delete/move when a penalty scope is present.

    Chat treated «удали все документы за штраф в этой папке» as
    wipe-the-folder because «все документы» matched wants_all and the
    document-type phrase was ignored. «удали документы 1-го штрафа»
    took the first digit as a document id. The same path hits
    «неустойка» and «пеня».
    """
    if explicit_document_ids:
        return False
    return looks_like_penalty_scoped_document_request(text)
