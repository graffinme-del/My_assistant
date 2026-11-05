"""Bare proposal scope the auction and payment guards do not cover.

«предложение», including «коммерческое предложение» and «встречное предложение».
«публичное предложение» is the auction guard. «оферта» is the payment guard.

Do not treat «за предложение» / «по коммерческому предложению» as a folder wipe,
and do not treat «1-е предложение» / «12,5% предложения» / «214-е предложение»
as a document id.

A folder titled «Предложение» does not match. «без предложения» does not match.
«предложенный», «предложить», and «оферта» do not match.
"""

from __future__ import annotations

import re

# Longer adjective endings first so «ыми» wins over «ым».
_ADJ_END = (
    r"(?:ою|ыми|ими|ого|его|ому|ему|ых|их|ая|яя|ое|ее|ую|юю|ые|ие|ый|ий|ой|ым|им|ом|ем)"
)

# «моё» is normalized to «мое» before matching. The stem is only two letters,
# so it cannot go through the generic adjective slot.
_POSSESSIVE = (
    r"мо(?:его|ему|ими|ею|ей|им|ем|их|ю|я|е|и|й)"
    r"|тво(?:его|ему|ими|ею|ей|им|ем|их|ю|я|е|и|й)"
    r"|наш(?:его|ему|ими|ею|ей|им|ем|их|ю|а|е|и|у)"
    r"|ваш(?:его|ему|ими|ею|ей|им|ем|их|ю|а|е|и|у)"
)

_DEMONSTRATIVE = (
    r"(?:этими|этих|этот|этого|этому|этой|этом|эта|эту|эти|это|"
    r"(?<![а-яё])(?:теми|тех|тому|того|той|тот|тем|том|та|ту|те|то|его|ее|их)|"
    rf"прошл\w{{0,4}}|текущ\w{{0,4}}|данн\w{{0,4}}|сво\w{{0,4}}|{_POSSESSIVE})\s+"
)

_WORD_ORDINAL = (
    r"(?:перв(?:ое|ого|ому|ым|ом|ая|ую|ой|ый|ые|ых|ыми)|втор(?:ое|ого|ому|ым|ом|ая|ую|ой|ый|ые|ых|ыми)|"
    r"трет(?:ье|ьего|ьему|ьим|ьем|ья|ью|ьей|ий|ьи|ьих|ьими)|четв[её]рт(?:ое|ого|ому|ым|ом|ая|ую|ой|ый|ые|ых|ыми))"
)

_WHOLE = r"(?<![а-яё])(?:всеми|всех|всему|всего|всей|всем|весь|вся|всё|все|всю)"

# Nouns that may stand between the preposition and the proposal word.
# «папке» and «делу» are absent, so a folder titled «Предложение» does not match.
_NOUN_QUAL = (
    r"(?<![а-яё])(?:не)?(?:"
    r"основани(?:ями|ях|ям|ем|ею|ю|и|е|я|й)"
    r"|имуществ(?:ами|ах|ам|ом|е|а|у|о)?"
    r"|процедур(?:ами|ах|ам|ою|ой|у|е|ы|а)?"
    r"|результат(?:ами|ах|ам|ов|ом|е|а|у|ы)?"
    r"|договор(?:ами|ах|ам|ов|ом|е|а|у|ы)?"
    r"|предмет(?:ами|ах|ам|ов|ом|е|а|у|ы)?"
    r"|объект(?:ами|ах|ам|ов|ом|е|а|у|ы)?"
    r"|услови(?:ями|ях|ям|ем|ею|ю|и|е|я|й)"
    r"|перечн(?:ями|ях|ям|ем|ею|ю|и|е|я|й)"
    r"|состав(?:ами|ах|ам|ов|ом|е|а|у|ы)?"
    r"|порядок(?:ами|ах|ам|ов|ом|е|а|у|и)?"
    r"|способ(?:ами|ах|ам|ов|ом|е|а|у|ы)?"
    r"|период(?:ами|ах|ам|ов|ом|е|а|у|ы)?"
    r"|сумм(?:ами|ах|ам|ою|ой|у|е|ы|а)?"
    r"|дол(?:ями|ях|ям|ею|ей|ю|и|е|я|й)"
    r"|цен(?:ами|ах|ам|ою|ой|у|е|ы|а)?"
    r"|част(?:ями|ях|ям|ью|ей|и|ь)?"
    r"|этап(?:ами|ах|ам|ов|ом|е|а|у|ы)?"
    r"|срок(?:ами|ах|ам|ов|ом|е|а|у|и)?"
    r"|ход(?:ами|ах|ам|ов|ом|е|а|у|ы)?"
    r"|рам(?:к(?:ами|ах|ам|ою|ой|у|е|и|а)?|ок)"
    r"|круг(?:ами|ах|ам|ов|ом|е|а|у|и)?"
    r")(?![а-яё])"
)

# «предложение». «предложенный» and «предложить» do not match.
# «публичное предложение» is removed before matching; it belongs to the auction guard.
_OFFER = r"предложени(?:ями|ях|ям|ем|ею|ю|и|е|я|й)"

# The noun itself ends in «ие» / «ем» / «ий», which are also adjective endings.
# Do not let the qualifier slot consume «предложение».
_ADJ_WORD = (
    rf"(?:[а-яё]{{3,}}-)?(?!(?:не)?{_OFFER}(?![а-яё]))[а-яё]{{3,}}{_ADJ_END}"
)

_QUAL = (
    rf"(?:{_DEMONSTRATIVE}|{_WORD_ORDINAL}\s+|{_WHOLE}\s+|"
    rf"{_NOUN_QUAL}\s+|{_ADJ_WORD}\s+)"
)
_Q = r"(?:[«»\"'„“”]\s*)?"

_ORDINAL_SUFFIX = r"(?:го|му|ой|ую|й|е|я|ю|о|м|х|ем)"

_TARGET = _OFFER
_SCOPE = _TARGET

_EXCLUDED_COMPOUND = re.compile(
    rf"(?<![а-яё])публичн{_ADJ_END}\s+{_OFFER}(?![а-яё])",
    re.IGNORECASE,
)

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
    r"данные|данных|данного|"
    rf"{_POSSESSIVE})\s+"
    rf"(?:{_Q}{_QUAL}){{0,2}}{_Q}(?<![a-zа-яё])(?:не)?{_SCOPE}(?![a-zа-яё])",
    re.IGNORECASE,
)

_ORDINAL_WORD = re.compile(
    rf"(?:об|за|в|во|на|по|с|со|из|о|от|для|под|к|ко)\s+{_WORD_ORDINAL}\s+(?:{_Q}{_QUAL}){{0,2}}{_Q}(?<![a-zа-яё])(?:не)?{_SCOPE}(?![a-zа-яё])"
    rf"|\b{_WORD_ORDINAL}\s+(?:{_Q}{_QUAL}){{0,2}}{_Q}(?<![a-zа-яё])(?:не)?{_SCOPE}(?![a-zа-яё])",
    re.IGNORECASE,
)

# 1–2 digits may omit the ordinal ending («100» is an amount, below).
# 3+ digits must wear «-е» / «-го» so «документ 214» stays an id.
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
    "Не удаляю файлы по виду «предложение» "
    "вроде «за предложение» / «за коммерческое предложение» / «1-е предложение» — "
    "это не номер документа и не команда очистить всю папку. "
    "Укажите id: «удали документ 214» или «удали документы [12] [18]». "
    "Чтобы очистить открытую папку целиком, напишите «удали все документы в этой папке» "
    "без этих слов."
)

MOVE_REFUSED_REPLY = (
    "Не переношу все файлы папки по виду «предложение» "
    "вроде «за предложение» / «за коммерческое предложение». "
    "Укажите id: «перенеси документ 214 в дело …». "
    "Чтобы перенести всю открытую папку, напишите без этих слов: "
    "«перенеси все документы в папку …»."
)


def _prepare(text: str) -> str:
    raw = (text or "").replace("ё", "е").replace("Ё", "Е")
    return _EXCLUDED_COMPOUND.sub(" ", raw)


def mask_proposal_ordinals(text: str) -> str:
    """Replace «1-е предложение» so the digit is not a document id.

    Amounts run first so «12,5% предложения» is one token. The ordinal pass
    would otherwise keep «12» and only hide the «5». «публичное предложение»
    is removed before masking so its digits stay for the auction guard.
    """
    raw = _prepare(text)
    masked = _SCOPED_AMOUNT.sub(" ", raw)
    return _ORDINAL_NUM.sub(" ", masked)


def looks_like_proposal_scoped_document_request(text: str) -> bool:
    """True when the user scoped files to a bare proposal."""
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


def proposal_blocks_bulk_document_mutation(
    text: str, *, explicit_document_ids: list[int] | None = None
) -> bool:
    """Refuse folder-wide delete/move when a bare proposal scope is present.

    Chat treated «удали все документы за коммерческое предложение в этой папке»
    as wipe-the-folder because «все документы» matched wants_all and «в этой
    папке» (or a case number, or «текущ» / «открыт») selected the case.
    «удали документы 1-е предложение» took the first digit as a document id.
    «публичное предложение» is the auction guard. «оферта» is the payment guard.
    """
    if explicit_document_ids:
        return False
    return looks_like_proposal_scoped_document_request(text)
