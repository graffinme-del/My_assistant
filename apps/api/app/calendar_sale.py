"""Bare sale scope the supply and auction guards do not cover.

«продажа» and «купля». «купля-продажа» is the supply guard. «прямая продажа»
is the auction guard. «реализация имущества» is the trustee guard.

Do not treat «за продажу» / «по купле» as a folder wipe, and do not treat
«1-й продажи» / «12,5% продажи» / «214-й продажи» as a document id.

A folder titled «Продажа» or «Купля» does not match. «без продажи» does not
match. «продать», «продажный», «распродажа», and «купель» do not match.
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

# Nouns that may stand between the preposition and the sale word.
# «папке» and «делу» are absent, so a folder titled «Продажа» does not match.
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

_QUAL = (
    rf"(?:{_DEMONSTRATIVE}|{_WORD_ORDINAL}\s+|{_WHOLE}\s+|"
    rf"{_NOUN_QUAL}\s+|{_ADJ_WORD}\s+)"
)
_Q = r"(?:[«»\"'„“”]\s*)?"

_ORDINAL_SUFFIX = r"(?:го|му|ой|ую|й|е|я|ю|о|м|х|ем)"

# «продажа». «продажный», «продать», and «распродажа» do not match.
_PRODAZHA = r"продаж(?:ами|ах|ам|ею|ей|у|е|и|а)?"
# «купля». «купель» and «купить» do not match.
_KUPLYA = r"купл(?:ями|ях|ям|ею|ей|ю|е|и|я)"

_TARGET = rf"(?:{_PRODAZHA}|{_KUPLYA})"
_SCOPE = _TARGET

# Supply owns «купля-продажа». Auction owns «прямая продажа».
_EXCLUDED_COMPOUND = re.compile(
    rf"(?:"
    rf"(?<![а-яё]){_KUPLYA}\s*[-–—‑]\s*{_PRODAZHA}"
    rf"|(?<![а-яё])прям{_ADJ_END}\s+{_PRODAZHA}"
    rf")(?![а-яё])",
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
# 3+ digits must wear «-й» / «-го» so «документ 214» stays an id.
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
    "Не удаляю файлы по виду «продажа» / «купля» "
    "вроде «за продажу» / «по купле» / «1-я продажа» — "
    "это не номер документа и не команда очистить всю папку. "
    "Укажите id: «удали документ 214» или «удали документы [12] [18]». "
    "Чтобы очистить открытую папку целиком, напишите «удали все документы в этой папке» "
    "без этих слов."
)

MOVE_REFUSED_REPLY = (
    "Не переношу все файлы папки по виду «продажа» / «купля» "
    "вроде «за продажу» / «по купле». "
    "Укажите id: «перенеси документ 214 в дело …». "
    "Чтобы перенести всю открытую папку, напишите без этих слов: "
    "«перенеси все документы в папку …»."
)


def _prepare(text: str) -> str:
    raw = (text or "").replace("ё", "е").replace("Ё", "Е")
    return _EXCLUDED_COMPOUND.sub(" ", raw)


def mask_sale_ordinals(text: str) -> str:
    """Replace «1-й продажи» so the digit is not a document id.

    Amounts run first so «12,5% продажи» is one token. The ordinal pass
    would otherwise keep «12» and only hide the «5». «купля-продажа» and
    «прямая продажа» are removed before masking so their digits stay for
    the guards that own those phrases.
    """
    raw = _prepare(text)
    masked = _SCOPED_AMOUNT.sub(" ", raw)
    return _ORDINAL_NUM.sub(" ", masked)


def looks_like_sale_scoped_document_request(text: str) -> bool:
    """True when the user scoped files to a bare sale or купля."""
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


def sale_blocks_bulk_document_mutation(
    text: str, *, explicit_document_ids: list[int] | None = None
) -> bool:
    """Refuse folder-wide delete/move when a bare sale scope is present.

    Chat treated «удали все документы за продажу в этой папке» as wipe-the-folder
    because «все документы» matched wants_all and «в этой папке» (or a case
    number, or «текущ» / «открыт») selected the case. «удали документы 1-й
    продажи» took the first digit as a document id. The same path hits
    «по купле». «купля-продажа» and «прямая продажа» are separate guards.
    """
    if explicit_document_ids:
        return False
    return looks_like_sale_scoped_document_request(text)
