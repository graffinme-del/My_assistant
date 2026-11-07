"""Debt-restructuring scope the procedure guard does not cover.

«реструктуризация», including «реструктуризация долгов», «план реструктуризации»,
and «график реструктуризации». «наблюдение», «конкурсное производство»,
«внешнее управление», «финансовое оздоровление», and «реализация имущества»
are other guards.

Do not treat «за реструктуризацию долгов» as a folder wipe, and do not treat
«1-я реструктуризация» / «12,5% реструктуризации» / «214-я реструктуризация»
as a document id.

A folder titled «Реструктуризация» does not match. «без реструктуризации»
does not match. «реструктурированный», «реструктурировать», and
«реструктуризационный» do not match.
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

# Nouns that may stand between the preposition and the restructuring word.
# «папке» and «делу» are absent, so a folder titled «Реструктуризация» does not match.
# «план» / «график» / «долг» are only qualifiers here: «по плану реструктуризации»
# matches, bare «за план» does not.
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
    r"|проект(?:ами|ах|ам|ов|ом|е|а|у|ы)?"
    r"|процесс(?:ами|ах|ам|ов|ом|е|а|у|ы)?"
    r"|программ(?:ами|ах|ам|ою|ой|у|е|ы|а)?"
    r"|планировани(?:ями|ях|ям|ем|ею|ю|и|е|я|й)"
    r"|план(?:ами|ах|ам|ов|ом|е|а|у|ы)?"
    r"|график(?:ами|ах|ам|ов|ом|е|а|у|и)?"
    r"|долг(?:ами|ах|ам|ов|ом|е|а|у|и)?"
    r"|счет(?:ами|ах|ам|ов|ом|е|а|у|ы)?"
    r")(?![а-яё])"
)

# «реструктуризация». «реструктурированный» and «реструктурировать» do not match.
_RESTRUCTURING = r"реструктуризаци(?:ями|ях|ям|ею|ей|ю|и|е|я|й)"

# The noun itself ends in «ия» / «ии» / «ий», which overlap adjective endings.
# Do not let the qualifier slot consume «реструктуризация».
_ADJ_WORD = (
    rf"(?:[а-яё]{{3,}}-)?(?!(?:не)?{_RESTRUCTURING}(?![а-яё]))[а-яё]{{3,}}{_ADJ_END}"
)

_QUAL = (
    rf"(?:{_DEMONSTRATIVE}|{_WORD_ORDINAL}\s+|{_WHOLE}\s+|"
    rf"{_NOUN_QUAL}\s+|{_ADJ_WORD}\s+)"
)
_Q = r"(?:[«»\"'„“”]\s*)?"

_ORDINAL_SUFFIX = r"(?:го|му|ой|ую|й|е|я|ю|о|м|х|ем)"

_TARGET = _RESTRUCTURING
_SCOPE = _TARGET
# «нереструктуризацию» and the spaced «не реструктуризацию».
_NEG = r"(?:не(?:\s+)?)?"
_NEG_WORD = r"(?:не\s+)?"

_PREP = re.compile(
    rf"(?<![а-яё])(?:под|об|во|ко|со|от|для|перед|после|при|за|на|по|из|до|к|в|с|о)\s+"
    rf"(?:{_NEG_WORD}{_Q}{_QUAL}){{0,3}}(?<!без\s){_Q}(?<![a-zа-яё]){_NEG}{_SCOPE}(?![a-zа-яё])",
    re.IGNORECASE,
)

_DURING = re.compile(
    rf"во\s+время\s+(?:{_NEG_WORD}{_Q}{_QUAL}){{0,3}}{_Q}(?<![a-zа-яё]){_NEG}{_SCOPE}(?![a-zа-яё])",
    re.IGNORECASE,
)

_DEMONSTRATIVE_SCOPE = re.compile(
    rf"(?:этими|этих|этот|этого|этому|этой|этом|эта|эту|эти|это|"
    r"(?<![а-яё])(?:теми|тех|тому|того|той|тот|тем|том|та|ту|те|то|его|ее|их)|"
    r"прошлые|прошлых|прошлый|прошлого|прошлая|прошлую|прошлое|"
    r"текущие|текущих|текущий|текущего|текущая|текущую|текущее|"
    r"данные|данных|данного|"
    rf"{_POSSESSIVE})\s+"
    rf"(?:{_NEG_WORD}{_Q}{_QUAL}){{0,2}}{_Q}(?<![a-zа-яё]){_NEG}{_SCOPE}(?![a-zа-яё])",
    re.IGNORECASE,
)

_ORDINAL_WORD = re.compile(
    rf"(?:об|за|в|во|на|по|с|со|из|о|от|для|под|к|ко)\s+{_WORD_ORDINAL}\s+(?:{_NEG_WORD}{_Q}{_QUAL}){{0,2}}{_Q}(?<![a-zа-яё]){_NEG}{_SCOPE}(?![a-zа-яё])"
    rf"|\b{_WORD_ORDINAL}\s+(?:{_NEG_WORD}{_Q}{_QUAL}){{0,2}}{_Q}(?<![a-zа-яё]){_NEG}{_SCOPE}(?![a-zа-яё])",
    re.IGNORECASE,
)

# 1–2 digits may omit the ordinal ending («100» is an amount, below).
# 3+ digits must wear «-я» / «-й» so «документ 214» stays an id.
_ORDINAL_NUM = re.compile(
    rf"(?:\b\d{{1,2}}(?!\d)(?:-?{_ORDINAL_SUFFIX})?|\b\d{{3,6}}(?!\d)-?{_ORDINAL_SUFFIX})"
    rf"\s*(?:{_NEG_WORD}{_Q}{_QUAL}){{0,2}}{_Q}(?<![a-zа-яё]){_NEG}{_SCOPE}(?![a-zа-яё])",
    re.IGNORECASE,
)

_SCOPED_AMOUNT = re.compile(
    rf"\b\d+(?:\s*[.,]\s*\d+)?\s*%?\s*(?:{_NEG_WORD}{_Q}{_QUAL}){{0,2}}{_Q}(?<![a-zа-яё]){_NEG}{_SCOPE}(?![a-zа-яё])",
    re.IGNORECASE,
)

_DOCS = re.compile(
    rf"(?:документ|файл)\w*\s+(?:{_NEG_WORD}{_Q}{_QUAL}){{0,3}}{_Q}(?<![a-zа-яё]){_NEG}{_TARGET}(?![a-zа-яё])",
    re.IGNORECASE,
)


DELETE_REFUSED_REPLY = (
    "Не удаляю файлы по виду «реструктуризация» "
    "вроде «за реструктуризацию» / «за реструктуризацию долгов» / «1-я реструктуризация» — "
    "это не номер документа и не команда очистить всю папку. "
    "Укажите id: «удали документ 214» или «удали документы [12] [18]». "
    "Чтобы очистить открытую папку целиком, напишите «удали все документы в этой папке» "
    "без этих слов."
)

MOVE_REFUSED_REPLY = (
    "Не переношу все файлы папки по виду «реструктуризация» "
    "вроде «за реструктуризацию» / «по плану реструктуризации». "
    "Укажите id: «перенеси документ 214 в дело …». "
    "Чтобы перенести всю открытую папку, напишите без этих слов: "
    "«перенеси все документы в папку …»."
)


def _prepare(text: str) -> str:
    return (text or "").replace("ё", "е").replace("Ё", "Е")


def mask_restructuring_ordinals(text: str) -> str:
    """Replace «1-я реструктуризация» so the digit is not a document id.

    Amounts run first so «12,5% реструктуризации» is one token. The ordinal
    pass would otherwise keep «12» and only hide the «5».
    """
    raw = _prepare(text)
    masked = _SCOPED_AMOUNT.sub(" ", raw)
    return _ORDINAL_NUM.sub(" ", masked)


def looks_like_restructuring_scoped_document_request(text: str) -> bool:
    """True when the user scoped files to debt restructuring."""
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


def restructuring_blocks_bulk_document_mutation(
    text: str, *, explicit_document_ids: list[int] | None = None
) -> bool:
    """Refuse folder-wide delete/move when a restructuring scope is present.

    Chat treated «удали все документы за реструктуризацию долгов в этой папке»
    as wipe-the-folder because «все документы» matched wants_all and «в этой
    папке» (or a case number, or «текущ» / «открыт») selected the case.
    «удали документы 1-я реструктуризация» took the first digit as a document id.
    """
    if explicit_document_ids:
        return False
    return looks_like_restructuring_scoped_document_request(text)
