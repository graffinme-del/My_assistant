"""Installment, deferral, restructuring, subsidiary liability, OSAGO, and PTS scope.

Do not treat «за рассрочку» / «за отсрочку» / «за реструктуризацию» /
«за субсидиарную ответственность» / «за солидарную ответственность» /
«за ОСАГО» / «за ПТС» as a folder wipe, and do not treat
«1-й рассрочки» / «1-й отсрочки» / «1-й субсидиарной» / «1 ОСАГО» / «100 ПТС»
as a document id.

A folder titled «Рассрочка», «Отсрочка», «Реструктуризация», «ОСАГО», or «ПТС»
does not match. «без рассрочки» / «без отсрочки» / «без ОСАГО» / «без ПТС»
do not match. «рассрочить», «отсрочить», «реструктуризировать», «солидарность»,
and «субсидиарно» do not match. Bare «полис» / «паспорт» remain a separate guard.
«Вред» / «пошлина» / «проценты» / «взыскание» remain a separate guard.
"""

from __future__ import annotations

import re

# «рассрочка». «рассрочить» does not contain this stem.
_INSTALLMENT = r"рассрочк(?:ами|ах|ам|ою|ой|у|е|и|а)?"
# «отсрочка». «отсрочить» does not contain this stem.
_DEFERRAL = r"отсрочк(?:ами|ах|ам|ою|ой|у|е|и|а)?"
# «реструктуризация». «реструктуризировать» does not contain this stem.
_RESTRUCT = r"реструктуризаци(?:ями|ях|ям|ею|ей|ю|и|я|й)"
# «субсидиарка». The adjective «субсидиарный» is a separate stem.
_SUBSIDIARY_SHORT = r"субсидиарк(?:ами|ах|ам|ою|ой|у|е|и|а)?"
# «субсидиарная ответственность», «субсидиарный иск». «субсидиарно» does not match.
_SUBSIDIARY_ADJ = r"субсидиарн(?:ыми|ый|ая|ое|ые|ого|ому|ым|ом|ую|ой|ых)"
# «солидарная ответственность». «солидарность» / «солидарно» do not match.
_JOINT_ADJ = r"солидарн(?:ыми|ый|ая|ое|ые|ого|ому|ым|ом|ую|ой|ых)"
# Indeclinable acronyms. Latin «OSAGO» is the same policy; Latin «pts» is not.
_OSAGO = r"(?<![a-z])(?:осаго|osago)(?![a-z])"
_PTS = r"(?<![a-z])птс(?![a-z])"

_TARGET = (
    rf"(?:{_RESTRUCT}|{_INSTALLMENT}|{_DEFERRAL}|{_SUBSIDIARY_SHORT}|"
    rf"{_SUBSIDIARY_ADJ}|{_JOINT_ADJ}|{_OSAGO}|{_PTS})"
)

_INSTALLMENT_ADJ = r"рассроченн(?:ыми|ый|ая|ое|ые|ого|ому|ым|ом|ую|ой|ых)"
_DEFERRAL_ADJ = r"отсроченн(?:ыми|ый|ая|ое|ые|ого|ому|ым|ом|ую|ой|ых)"
_RESTRUCT_ADJ = r"реструктуризационн(?:ыми|ый|ая|ое|ые|ого|ому|ым|ом|ую|ой|ых)"
_ADJ = rf"(?:{_INSTALLMENT_ADJ}|{_DEFERRAL_ADJ}|{_RESTRUCT_ADJ}|{_SUBSIDIARY_ADJ}|{_JOINT_ADJ})"

_DEMONSTRATIVE = (
    r"(?:этими|этих|этот|этого|этому|этой|этом|эта|эту|эти|это|"
    r"прошл\w{0,4}|текущ\w{0,4}|данн\w{0,4}|сво\w{0,4})\s+"
)

_WORD_ORDINAL = (
    r"(?:перв(?:ое|ого|ому|ым|ом|ая|ую|ой|ый|ые|ых|ыми)|втор(?:ое|ого|ому|ым|ом|ая|ую|ой|ый|ые|ых|ыми)|"
    r"трет(?:ье|ьего|ьему|ьим|ьем|ья|ью|ьей|ий|ьи|ьих|ьими)|четв[её]рт(?:ое|ого|ому|ым|ом|ая|ую|ой|ый|ые|ых|ыми))"
)

# One qualifier word: «судебную рассрочку», «электронное ОСАГО».
_ADJ_WORD = (
    r"(?:[а-яё]{3,}-)?[а-яё]{3,}(?:ыми|ими|ый|ий|ой|ая|яя|ое|ее|ые|ие|ого|его|ому|ему|ым|им|ом|ем|ую|юю|ых|их)"
)

# «вся рассрочка», «все отсрочки». Not an adjective, so _ADJ_WORD does not see it.
_WHOLE = r"(?<![а-яё])(?:всеми|всех|всему|всего|всей|всем|весь|вся|всё|все|всю)"

# Nouns that sit between the preposition and the target:
# «предоставление рассрочки», «график отсрочки», «план реструктуризации», «полис ОСАГО».
# Bare «полис» / «график» / «план» without one of these targets do not match.
_NOUN_QUAL = (
    r"(?<![а-яё])(?:предоставлени(?:ями|ях|ям|ем|ею|ю|и|е|я)"
    r"|график(?:ами|ах|ам|ов|ом|и|а|у|е)?"
    r"|план(?:ами|ах|ам|ов|ом|а|у|е|ы)?"
    r"|полис(?:ами|ах|ам|ов|ом|у|е|а|ы)?"
    r"|паспорт(?:ами|ах|ам|ов|ом|у|е|а|ы)?)(?![а-яё])"
)

_QUAL = rf"(?:{_DEMONSTRATIVE}|{_WORD_ORDINAL}\s+|{_WHOLE}\s+|{_NOUN_QUAL}\s+|{_ADJ_WORD}\s+)"

_ORDINAL_SUFFIX = r"(?:го|му|ой|ую|й|е|я|ю|о|м|х|ем)"

_PREP = re.compile(
    rf"(?<![а-яё])(?:под|об|во|ко|со|за|на|по|из|к|в|с|о)\s+(?:{_QUAL}){{0,3}}(?<![а-яё]){_TARGET}(?![а-яё])",
    re.IGNORECASE,
)

_DURING = re.compile(
    rf"во\s+время\s+(?:{_QUAL}){{0,3}}(?<![а-яё]){_TARGET}(?![а-яё])",
    re.IGNORECASE,
)

_DEMONSTRATIVE_SCOPE = re.compile(
    rf"(?:этими|этих|этот|этого|этому|этой|этом|эта|эту|эти|это|"
    r"прошлые|прошлых|прошлый|прошлого|прошлая|прошлую|прошлое|"
    r"текущие|текущих|текущий|текущего|текущая|текущую|текущее|"
    r"данные|данных|данного)\s+"
    rf"(?:{_QUAL}){{0,2}}(?<![а-яё]){_TARGET}(?![а-яё])",
    re.IGNORECASE,
)

_ORDINAL_WORD = re.compile(
    rf"(?:об|за|в|во|на|по|с|со|из|о|под|к|ко)\s+{_WORD_ORDINAL}\s+(?:{_QUAL}){{0,2}}(?<![а-яё]){_TARGET}(?![а-яё])"
    rf"|\b{_WORD_ORDINAL}\s+(?:{_QUAL}){{0,2}}(?<![а-яё]){_TARGET}(?![а-яё])",
    re.IGNORECASE,
)

# «1-й рассрочки», «1-го ОСАГО». Two digits so ids like 214 stay ids.
# (?!\d) so a longer number is not sliced. Amounts below cover 100 and decimals.
_ORDINAL_NUM = re.compile(
    rf"\b\d{{1,2}}(?!\d)(?:-?{_ORDINAL_SUFFIX})?\s*(?:{_QUAL}){{0,2}}(?<![а-яё]){_TARGET}(?![а-яё])",
    re.IGNORECASE,
)

# «100 ПТС», «12,5 рассрочки» — not a 1–2 digit ordinal, still not a document id.
_SCOPED_AMOUNT = re.compile(
    rf"\b\d+(?:\s*[.,]\s*\d+)?\s*(?:{_QUAL}){{0,2}}(?<![а-яё]){_TARGET}(?![а-яё])",
    re.IGNORECASE,
)

# «документы рассрочки» — genitive scope, not a folder titled «Рассрочка».
_DOCS = re.compile(
    rf"(?:документ|файл)\w*\s+(?:{_QUAL}){{0,3}}(?<![а-яё]){_TARGET}(?![а-яё])",
    re.IGNORECASE,
)

# «рассроченные документы» / «документы субсидиарные».
_ADJ_DOCS = re.compile(
    rf"(?:(?<![а-яё]){_ADJ}\s+(?:документ|файл)\w*|(?:документ|файл)\w*\s+(?<![а-яё]){_ADJ})(?![а-яё])",
    re.IGNORECASE,
)

DELETE_REFUSED_REPLY = (
    "Не удаляю файлы по виду «рассрочка» / «отсрочка» / «реструктуризация» / "
    "«субсидиарная ответственность» / «солидарная ответственность» / «ОСАГО» / «ПТС» "
    "вроде «за рассрочку» / «за отсрочку» / «за субсидиарную ответственность» / "
    "«за ОСАГО» / «за ПТС» / «1-й рассрочки» — "
    "это не номер документа и не команда очистить всю папку. "
    "Укажите id: «удали документ 214» или «удали документы [12] [18]». "
    "Чтобы очистить открытую папку целиком, напишите «удали все документы в этой папке» "
    "без этих слов."
)

MOVE_REFUSED_REPLY = (
    "Не переношу все файлы папки по виду «рассрочка» / «отсрочка» / «реструктуризация» / "
    "«субсидиарная ответственность» / «солидарная ответственность» / «ОСАГО» / «ПТС» "
    "вроде «за рассрочку» / «за отсрочку» / «за ОСАГО» / «за ПТС». "
    "Укажите id: «перенеси документ 214 в дело …». "
    "Чтобы перенести всю открытую папку, напишите без этих слов: "
    "«перенеси все документы в папку …»."
)


def mask_installment_ordinals(text: str) -> str:
    """Replace «1-й рассрочки» / «100 ПТС» so the digit is not a document id.

    Amounts run first so «12,5 рассрочки» is one token. The ordinal pass would
    otherwise keep «12» and only hide the «5».
    """
    masked = _SCOPED_AMOUNT.sub(" ", text or "")
    return _ORDINAL_NUM.sub(" ", masked)


def looks_like_installment_scoped_document_request(text: str) -> bool:
    """True when the user scoped files to рассрочка / отсрочка / субсидиарная / ОСАГО / ПТС."""
    raw = text or ""
    if (
        _PREP.search(raw)
        or _DURING.search(raw)
        or _DEMONSTRATIVE_SCOPE.search(raw)
        or _ORDINAL_WORD.search(raw)
        or _ORDINAL_NUM.search(raw)
        or _SCOPED_AMOUNT.search(raw)
        or _DOCS.search(raw)
        or _ADJ_DOCS.search(raw)
    ):
        return True
    return False


def installment_blocks_bulk_document_mutation(
    text: str, *, explicit_document_ids: list[int] | None = None
) -> bool:
    """Refuse folder-wide delete/move when an installment/liability/title scope is present.

    Chat treated «удали все документы за рассрочку в этой папке» as wipe-the-folder
    because «все документы» matched wants_all and the document-type phrase was
    ignored. «удали документы 1-й рассрочки» took the first digit as a document id.
    The same path hits отсрочка, реструктуризация, субсидиарная / солидарная
    ответственность, bare ОСАГО, and bare ПТС.
    """
    if explicit_document_ids:
        return False
    return looks_like_installment_scoped_document_request(text)
