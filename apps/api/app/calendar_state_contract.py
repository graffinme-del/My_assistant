"""State/commercial «контракт» chat scope.

Do not treat «за контракт» / «по госконтракту» / «за государственный контракт»
as a folder wipe, and do not treat «1-го контракта» as document id 1.

«Договор» is a different noun (separate guard). Bare «акт» does not match here;
«контракт» only shares those letters inside a longer word.
"""

from __future__ import annotations

import re

# «госконтракт», «гос-контракт», «гос. контракт», «гос контракт», «контракт».
# Longer endings come first so «контрактами» is not cut down to «контракта».
# Trailing (?![а-яё]) is applied at the call site so «контрактация»,
# «контрактник», and «контрактный» do not steal the noun slot.
_KONTRAKT = (
    r"(?:гос(?:[.\-]\s*|\s+)?)?"
    r"контракт(?:ами|ах|ам|ом|ов|у|е|а|ы)?"
)

_DEMONSTRATIVE = (
    r"(?:этими|этих|этот|этого|этому|этой|этом|эта|эту|эти|это|"
    r"прошл\w{0,4}|текущ\w{0,4}|данн\w{0,4}|сво\w{0,4})\s+"
)

_WORD_ORDINAL = (
    r"(?:перв(?:ое|ого|ому|ым|ом|ая|ую|ой|ый|ые|ых|ыми)|втор(?:ое|ого|ому|ым|ом|ая|ую|ой|ый|ые|ых|ыми)|"
    r"трет(?:ье|ьего|ьему|ьим|ьем|ья|ью|ьей|ий|ьи|ьих|ьими)|четв[её]рт(?:ое|ого|ому|ым|ом|ая|ую|ой|ый|ые|ых|ыми))"
)

# One qualifier word: «государственный контракт», «муниципальный контракт».
# Optional hyphenated prefix: «гражданско-правовой контракт».
_ADJ_WORD = (
    r"(?:[а-яё]{3,}-)?[а-яё]{3,}(?:ый|ий|ой|ая|яя|ое|ее|ые|ие|ого|его|ому|ему|ым|им|ом|ем|ую|юю|ых|их|ыми|ими)"
)

_QUAL = rf"(?:{_DEMONSTRATIVE}|{_WORD_ORDINAL}\s+|{_ADJ_WORD}\s+)"

_PREP = re.compile(
    rf"(?<![а-яё])(?:за|на|в|во|по)\s+(?:{_QUAL}){{0,3}}(?<![а-яё]){_KONTRAKT}(?![а-яё])",
    re.IGNORECASE,
)

_DURING = re.compile(
    rf"во\s+время\s+(?:{_QUAL}){{0,3}}(?<![а-яё]){_KONTRAKT}(?![а-яё])",
    re.IGNORECASE,
)

_DEMONSTRATIVE_SCOPE = re.compile(
    rf"(?:этими|этих|этот|этого|этому|этой|этом|эта|эту|эти|"
    r"прошлые|прошлых|прошлый|прошлого|прошлая|прошлую|прошлое|"
    r"текущие|текущих|текущий|текущего|текущая|текущую|текущее|"
    r"данные|данных|данного)\s+"
    rf"(?:{_QUAL}){{0,2}}(?<![а-яё]){_KONTRAKT}(?![а-яё])",
    re.IGNORECASE,
)

_ORDINAL_WORD = re.compile(
    rf"(?:за|в|во|на|по)\s+{_WORD_ORDINAL}\s+(?:{_QUAL}){{0,2}}(?<![а-яё]){_KONTRAKT}(?![а-яё])"
    rf"|\b{_WORD_ORDINAL}\s+(?:{_QUAL}){{0,2}}(?<![а-яё]){_KONTRAKT}(?![а-яё])",
    re.IGNORECASE,
)

# «1-го контракта», «1-й госконтракт». Two digits so ids like 214 stay ids.
_ORDINAL_NUM = re.compile(
    rf"\b\d{{1,2}}(?:-?(?:го|му|ой|ую|й|е|я|ю|о|м|х|ем))?\s*(?:{_QUAL}){{0,2}}(?<![а-яё]){_KONTRAKT}(?![а-яё])",
    re.IGNORECASE,
)

# «документы контракта» — genitive scope, not a folder titled «Контракт».
_DOCS = re.compile(
    rf"(?:документ|файл)\w*\s+(?:{_QUAL}){{0,3}}(?<![а-яё]){_KONTRAKT}(?![а-яё])",
    re.IGNORECASE,
)

# «контрактные документы» / «документы контрактные».
_KONTRAKT_ADJ = r"контрактн(?:ый|ая|ое|ые|ого|ому|ым|ом|ую|ой|ых|ыми)"
_ADJ_DOCS = re.compile(
    rf"(?:{_KONTRAKT_ADJ}\s+(?:документ|файл)\w*|(?:документ|файл)\w*\s+{_KONTRAKT_ADJ})(?![а-яё])",
    re.IGNORECASE,
)

DELETE_REFUSED_STATE_CONTRACT = (
    "Не удаляю файлы по контракту или госконтракту "
    "вроде «за контракт» / «по госконтракту» / «за государственный контракт» / "
    "«1-го контракта» — это не номер документа и не команда очистить всю папку. "
    "Укажите id: «удали документ 214» или «удали документы [12] [18]». "
    "Чтобы очистить открытую папку целиком, напишите «удали все документы в этой папке» "
    "без контракта и госконтракта."
)

MOVE_REFUSED_STATE_CONTRACT = (
    "Не переношу все файлы папки по контракту или госконтракту "
    "вроде «за контракт» / «по госконтракту». "
    "Укажите id: «перенеси документ 214 в дело …». "
    "Чтобы перенести всю открытую папку, напишите без контракта: "
    "«перенеси все документы в папку …»."
)


def mask_state_contract_ordinals(text: str) -> str:
    """Replace «1-го контракта» so the leading digit cannot be parsed as a document id."""
    return _ORDINAL_NUM.sub(" ", text or "")


def looks_like_state_contract_scoped_document_request(text: str) -> bool:
    """True when the user scoped files to a контракт / госконтракт."""
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


def state_contract_blocks_bulk_document_mutation(
    text: str, *, explicit_document_ids: list[int] | None = None
) -> bool:
    """Refuse folder-wide delete/move when a контракт scope is present.

    Chat treated «удали все документы за контракт в этой папке» as wipe-the-folder
    because «все документы» matched wants_all and the document-type phrase was ignored.
    «удали документы 1-го контракта» took the first digit as a document id.
    """
    if explicit_document_ids:
        return False
    return looks_like_state_contract_scoped_document_request(text)
