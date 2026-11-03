"""Auction scope the carriage and supply guards do not cover.

«торги», «аукцион», «публичное предложение», «прямая продажа», and «лот».
Bare «продажа», bare «купля», «купля-продажа», bare «предложение», and
«оферта» are not this guard. «реализация имущества» is not this guard.

Do not treat «за торги» / «по аукциону» / «за публичное предложение» /
«за прямую продажу» / «за лот» as a folder wipe, and do not treat
«1-х торгов» / «12,5% аукциона» / «214-го лота» as a document id.

A folder titled «Торги», «Аукцион», «Публичное предложение»,
«Прямая продажа», or «Лот» does not match. «без торгов» does not match.
«торговля», «торговый», «аукционист», «лотерея», and «лоток» do not match.
"""

from __future__ import annotations

import re

# Longer adjective endings first so «ыми» wins over «ым».
_ADJ_END = (
    r"(?:ою|ыми|ими|ого|его|ому|ему|ых|их|ая|яя|ое|ее|ую|юю|ые|ие|ый|ий|ой|ым|им|ом|ем)"
)
_ADJ_WORD = rf"(?:[а-яё]{{3,}}-)?[а-яё]{{3,}}{_ADJ_END}"

_DEMONSTRATIVE = (
    r"(?:этими|этих|этот|этого|этому|этой|этом|эта|эту|эти|это|"
    r"(?<![а-яё])(?:теми|тех|тому|того|той|тот|тем|том|та|ту|те|то|его|ее|их)|"
    r"прошл\w{0,4}|текущ\w{0,4}|данн\w{0,4}|сво\w{0,4})\s+"
)

_WORD_ORDINAL = (
    r"(?:перв(?:ое|ого|ому|ым|ом|ая|ую|ой|ый|ые|ых|ыми)|втор(?:ое|ого|ому|ым|ом|ая|ую|ой|ый|ые|ых|ыми)|"
    r"трет(?:ье|ьего|ьему|ьим|ьем|ья|ью|ьей|ий|ьи|ьих|ьими)|четв[её]рт(?:ое|ого|ому|ым|ом|ая|ую|ой|ый|ые|ых|ыми))"
)

_WHOLE = r"(?<![а-яё])(?:всеми|всех|всему|всего|всей|всем|весь|вся|всё|все|всю)"

_HELD = (
    r"(?:не)?состоявш(?:иеся|ихся|имися|егося|емуся|емся|уюся|аяся|ееся|ийся|имся)"
)

# Qualifiers that may stand between the preposition and the auction word.
_NOUN_QUAL = (
    r"(?<![а-яё])(?:не)?(?:"
    r"разбирательств(?:ами|ах|ам|ом|е|а|у|о)?"
    r"|производств(?:ами|ах|ам|ом|е|а|у|о)?"
    r"|процесс(?:ами|ах|ам|ов|ом|е|а|у|ы)?"
    r"|проведени(?:ями|ях|ям|ем|ею|ю|и|е|я|й)"
    r"|организатор(?:ами|ах|ам|ов|ом|е|а|у|ы)?"
    r"|победител(?:ями|ях|ям|ем|ею|ю|и|е|я|й)"
    r"|площад(?:ок|к(?:ами|ах|ам|ою|ой|у|е|и|а)?)"
    r"|извещени(?:ями|ях|ям|ем|ею|ю|и|е|я|й)"
    r"|сообщени(?:ями|ях|ям|ем|ею|ю|и|е|я|й)"
    r"|публикаци(?:ями|ях|ям|ею|ей|ю|и|я|й)"
    r"|положени(?:ями|ях|ям|ем|ею|ю|и|е|я|й)"
    r"|результат(?:ами|ах|ам|ов|ом|е|а|у|ы)?"
    r"|протокол(?:ами|ах|ам|ов|ом|е|а|у|ы)?"
    r"|имуществ(?:ами|ах|ам|ом|е|а|у|о)?"
    r"|должник(?:ами|ах|ам|ов|ом|е|а|у|и)?"
    r"|кредитор(?:ами|ах|ам|ов|ом|е|а|у|ы)?"
    r"|договор(?:ами|ах|ам|ов|ом|е|а|у|ы)?"
    r"|порядок(?:ами|ах|ам|ов|ом|е|а|у|и)?"
    r"|перечн(?:ями|ях|ям|ем|ею|ю|и|е|я|й)"
    r"|период(?:ами|ах|ам|ов|ом|е|а|у|ы)?"
    r"|состав(?:ами|ах|ам|ов|ом|е|а|у|ы)?"
    r"|этап(?:ами|ах|ам|ов|ом|е|а|у|ы)?"
    r"|срок(?:ами|ах|ам|ов|ом|е|а|у|и)?"
    r"|ход(?:ами|ах|ам|ов|ом|е|а|у|ы)?"
    r"|рам(?:к(?:ами|ах|ам|ою|ой|у|е|и|а)?|ок)"
    r"|круг(?:ами|ах|ам|ов|ом|е|а|у|и)?"
    r")(?![а-яё])"
)

_QUAL = (
    rf"(?:{_DEMONSTRATIVE}|{_WORD_ORDINAL}\s+|{_WHOLE}\s+|"
    rf"{_HELD}\s+|{_NOUN_QUAL}\s+|{_ADJ_WORD}\s+)"
)
_Q = r"(?:[«»\"'„“”]\s*)?"

_ORDINAL_SUFFIX = r"(?:го|му|ой|ую|й|е|я|ю|о|м|х|ем)"

# «торги». «торговля» and «торговый» do not match.
_BIDDING = r"торг(?:ами|ах|ам|ов|ом|и|е|а|у)?"
# «аукцион». «аукционист» does not match.
_AUCTION = r"аукцион(?:ами|ах|ам|ов|ом|ы|а|у|е)?"
# «публичное предложение». Bare «предложение» and «оферта» do not match.
_PUBLIC = rf"публичн{_ADJ_END}"
_OFFER = r"предложени(?:ями|ях|ям|ем|ею|ю|и|е|я|й)"
_PUBLIC_OFFER = rf"{_PUBLIC}\s+{_OFFER}"
# «прямая продажа». Bare «продажа» and «купля-продажа» do not match.
_DIRECT = rf"прям{_ADJ_END}"
_SALE = r"продаж(?:ами|ах|ам|ею|ей|у|е|и|а)?"
_DIRECT_SALE = rf"{_DIRECT}\s+{_SALE}"
# «лот». «лотерея» and «лоток» do not match.
_LOT = r"лот(?:ами|ах|ам|ов|ом|ы|а|у|е)?"

_TARGET = rf"(?:{_PUBLIC_OFFER}|{_DIRECT_SALE}|{_AUCTION}|{_BIDDING}|{_LOT})"
_SCOPE = _TARGET

_PREP = re.compile(
    rf"(?<![а-яё])(?:под|об|во|ко|со|от|для|перед|после|при|за|на|по|из|до|к|в|с|о)\s+"
    rf"(?:{_Q}{_QUAL}){{0,3}}(?<!без\s){_Q}(?<![a-zа-яё])(?:не)?{_SCOPE}(?![a-zа-яё])",
    re.IGNORECASE,
)

_DURING = re.compile(
    rf"во\s+время\s+(?:{_Q}{_QUAL}){{0,3}}{_Q}(?<![a-zа-яё])(?:не)?{_SCOPE}(?![a-zа-яё])",
    re.IGNORECASE,
)

_DEMONSTRATIVE_SCOPE = re.compile(
    rf"(?:этими|этих|этот|этого|этому|этой|этом|эта|эту|эти|это|"
    r"(?<![а-яё])(?:теми|тех|тому|того|той|тот|тем|том|та|ту|те|то|его|ее|их)|"
    r"прошлые|прошлых|прошлый|прошлого|прошлая|прошлую|прошлое|"
    r"текущие|текущих|текущий|текущего|текущая|текущую|текущее|"
    r"данные|данных|данного)\s+"
    rf"(?:{_Q}{_QUAL}){{0,2}}{_Q}(?<![a-zа-яё])(?:не)?{_SCOPE}(?![a-zа-яё])",
    re.IGNORECASE,
)

_ORDINAL_WORD = re.compile(
    rf"(?:об|за|в|во|на|по|с|со|из|о|от|для|под|к|ко)\s+{_WORD_ORDINAL}\s+(?:{_Q}{_QUAL}){{0,2}}{_Q}(?<![a-zа-яё])(?:не)?{_SCOPE}(?![a-zа-яё])"
    rf"|\b{_WORD_ORDINAL}\s+(?:{_Q}{_QUAL}){{0,2}}{_Q}(?<![a-zа-яё])(?:не)?{_SCOPE}(?![a-zа-яё])",
    re.IGNORECASE,
)

# 1–2 digits may omit the ordinal ending («100» is an amount, below).
# 3+ digits must wear «-го» / «-й» so «документ 214» stays an id.
_ORDINAL_NUM = re.compile(
    rf"(?:\b\d{{1,2}}(?!\d)(?:-?{_ORDINAL_SUFFIX})?|\b\d{{3,6}}(?!\d)-?{_ORDINAL_SUFFIX})"
    rf"\s*(?:{_Q}{_QUAL}){{0,2}}{_Q}(?<![a-zа-яё])(?:не)?{_SCOPE}(?![a-zа-яё])",
    re.IGNORECASE,
)

_SCOPED_AMOUNT = re.compile(
    rf"\b\d+(?:\s*[.,]\s*\d+)?\s*%?\s*(?:{_Q}{_QUAL}){{0,2}}{_Q}(?<![a-zа-яё])(?:не)?{_SCOPE}(?![a-zа-яё])",
    re.IGNORECASE,
)

_DOCS = re.compile(
    rf"(?:документ|файл)\w*\s+(?:{_Q}{_QUAL}){{0,3}}{_Q}(?<![a-zа-яё])(?:не)?{_TARGET}(?![a-zа-яё])",
    re.IGNORECASE,
)


DELETE_REFUSED_REPLY = (
    "Не удаляю файлы по виду «торги» / «аукцион» / «публичное предложение» / "
    "«прямая продажа» / «лот» вроде «за торги» / «по аукциону» / "
    "«за публичное предложение» / «1-е торги» — "
    "это не номер документа и не команда очистить всю папку. "
    "Укажите id: «удали документ 214» или «удали документы [12] [18]». "
    "Чтобы очистить открытую папку целиком, напишите «удали все документы в этой папке» "
    "без этих слов."
)

MOVE_REFUSED_REPLY = (
    "Не переношу все файлы папки по виду «торги» / «аукцион» / «публичное предложение» / "
    "«прямая продажа» / «лот» вроде «за торги» / «по аукциону» / "
    "«за публичное предложение». "
    "Укажите id: «перенеси документ 214 в дело …». "
    "Чтобы перенести всю открытую папку, напишите без этих слов: "
    "«перенеси все документы в папку …»."
)


def _prepare(text: str) -> str:
    return (text or "").replace("ё", "е").replace("Ё", "Е")


def mask_auction_ordinals(text: str) -> str:
    """Replace «1-х торгов» so the digit is not a document id.

    Amounts run first so «12,5% аукциона» is one token. The ordinal pass
    would otherwise keep «12» and only hide the «5».
    """
    raw = _prepare(text)
    masked = _SCOPED_AMOUNT.sub(" ", raw)
    return _ORDINAL_NUM.sub(" ", masked)


def looks_like_auction_scoped_document_request(text: str) -> bool:
    """True when the user scoped files to an auction, public offer, or lot."""
    raw = _prepare(text)
    return bool(
        _PREP.search(raw)
        or _DURING.search(raw)
        or _DEMONSTRATIVE_SCOPE.search(raw)
        or _ORDINAL_WORD.search(raw)
        or _ORDINAL_NUM.search(raw)
        or _SCOPED_AMOUNT.search(raw)
        or _DOCS.search(raw)
    )


def auction_blocks_bulk_document_mutation(
    text: str, *, explicit_document_ids: list[int] | None = None
) -> bool:
    """Refuse folder-wide delete/move when an auction scope is present.

    Chat treated «удали все документы за торги в этой папке» as wipe-the-folder
    because «все документы» matched wants_all and «в этой папке» (or a case
    number, or «текущ» / «открыт») selected the case. «удали документы 1-х
    торгов» took the first digit as a document id. The same path hits
    «по аукциону», «за публичное предложение», «за прямую продажу», and
    «214-го лота». Bare «продажа» is a separate gap and is not matched here.
    """
    if explicit_document_ids:
        return False
    return looks_like_auction_scoped_document_request(text)
