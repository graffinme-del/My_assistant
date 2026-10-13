"""Writ, interim-measures, and creditors'-meeting scope.

Do not treat «за исполнительный лист» / «за обеспечительные меры» /
«за собрание кредиторов» / «за комитет кредиторов» as a folder wipe,
and do not treat «1-го исполнительного листа» / «100 обеспечительных мер» /
«1-го собрания кредиторов» as a document id.

A folder titled «Исполнительный лист», «Обеспечительные меры», or
«Собрание кредиторов» does not match. «без исполнительного листа» does
not match. Bare «банкротство» does not match.

«мировое соглашение» is a different guard. «судебный приказ» / bare
«приказ» is a different guard. «исполнительное производство» is a
different guard. «больничный лист» is not this phrase.
"""

from __future__ import annotations

import re

# Longer adjective endings first so «ыми» wins over «ым».
_ADJ_END = (
    r"(?:ыми|ими|ого|его|ому|ему|ых|их|ая|яя|ое|ее|ую|юю|ые|ие|ый|ий|ой|ым|им|ом|ем)"
)
_ADJ_WORD = rf"(?:[а-яё]{{3,}}-)?[а-яё]{{3,}}{_ADJ_END}"

# «исполнительный лист». «исполнительное производство» has no «лист».
# «больничный лист» has no «исполнительн».
_ISP = rf"исполнительн{_ADJ_END}"
_LIST = r"лист(?:ами|ах|ам|ов|ом|у|е|ы|а)?"
_WRIT = rf"{_ISP}\s+(?:{_ADJ_WORD}\s+){{0,2}}{_LIST}"

# «обеспечительные меры». Bare «меры» and «обеспечение» do not match.
_OBESP = rf"обеспечительн{_ADJ_END}"
_MERA = r"мер(?:ами|ах|ам|ою|ой|у|е|ы|а)?"
_MEASURES = rf"{_OBESP}\s+(?:{_ADJ_WORD}\s+){{0,2}}{_MERA}"

# «собрание кредиторов», including «собрание комитета кредиторов» and
# «собрание всех кредиторов». Bare «собрание» and bare «кредиторов»
# (and «кредиторская задолженность») do not match.
_SOBR = r"собрани(?:ями|ях|ям|ем|ею|ю|и|е|я|й)"
_COMMITTEE = r"комитет(?:ами|ах|ам|ов|ом|е|а|у|ы)?"
_CREDITOR = r"кредитор(?:ами|ах|ам|ов|ом|у|е|ы|а)?"
_MEETING_BODY = (
    rf"(?:(?:{_ADJ_WORD}|всеми|всех|всему|всего|всей|всем|весь|вся|все|всю)\s+){{0,2}}"
    rf"(?:{_COMMITTEE}\s+)?(?:{_ADJ_WORD}\s+){{0,2}}{_CREDITOR}"
)
# «собрание кредиторов» and «комитет кредиторов». Bare «кредиторов» does not match.
_MEETING = rf"(?:{_SOBR}\s+{_MEETING_BODY}|{_COMMITTEE}\s+(?:{_ADJ_WORD}\s+){{0,2}}{_CREDITOR})"

_TARGET = rf"(?:{_WRIT}|{_MEASURES}|{_MEETING})"

_DEMONSTRATIVE = (
    r"(?:этими|этих|этот|этого|этому|этой|этом|эта|эту|эти|это|"
    r"прошл\w{0,4}|текущ\w{0,4}|данн\w{0,4}|сво\w{0,4})\s+"
)

_WORD_ORDINAL = (
    r"(?:перв(?:ое|ого|ому|ым|ом|ая|ую|ой|ый|ые|ых|ыми)|втор(?:ое|ого|ому|ым|ом|ая|ую|ой|ый|ые|ых|ыми)|"
    r"трет(?:ье|ьего|ьему|ьим|ьем|ья|ью|ьей|ий|ьи|ьих|ьими)|четв[её]рт(?:ое|ого|ому|ым|ом|ая|ую|ой|ый|ые|ых|ыми))"
)

_WHOLE = r"(?<![а-яё])(?:всеми|всех|всему|всего|всей|всем|весь|вся|всё|все|всю)"

# Words that sit between the preposition and the writ / measures / meeting.
# «папке» and «делу» are not here, so a folder titled «Исполнительный лист»
# does not match.
_NOUN_QUAL = (
    r"(?<![а-яё])(?:выдач(?:ами|ах|ам|ею|ей|у|е|и|а)?"
    r"|получени(?:ями|ях|ям|ем|ею|ю|и|е|я|й)?"
    r"|предъявлени(?:ями|ях|ям|ем|ею|ю|и|е|я|й)?"
    r"|исполнени(?:ями|ях|ям|ем|ею|ю|и|е|я|й)?"
    r"|дубликат(?:ами|ах|ам|ов|ом|е|а|у|ы)?"
    r"|оригинал(?:ами|ах|ам|ов|ом|е|а|у|ы)?"
    r"|копи(?:ями|ях|ям|ею|ей|ю|и|е|я|й)?"
    r"|отмен(?:ами|ах|ам|ою|ой|у|е|ы|а)?"
    r"|приняти(?:ями|ях|ям|ем|ею|ю|и|е|я|й)?"
    r"|введени(?:ями|ях|ям|ем|ею|ю|и|е|я|й)?"
    r"|применени(?:ями|ях|ям|ем|ею|ю|и|е|я|й)?"
    r"|замен(?:ами|ах|ам|ою|ой|у|е|ы|а)?"
    r"|протокол(?:ами|ах|ам|ов|ом|е|а|у|ы)?"
    r"|проведени(?:ями|ях|ям|ем|ею|ю|и|е|я|й)?"
    r"|повестк(?:ами|ах|ам|ою|ой|у|е|и|а)?"
    r"|решени(?:ями|ях|ям|ем|ею|ю|и|е|я|й)?"
    r"|результат(?:ами|ах|ам|ов|ом|е|а|у|ы)?"
    r"|голосовани(?:ями|ях|ям|ем|ею|ю|и|е|я|й)?"
    r"|период(?:ами|ах|ам|ов|ом|е|а|у|ы)?"
    r"|срок(?:ами|ах|ам|ов|ом|е|а|у|и)?"
    r"|процедур(?:ами|ах|ам|ою|ой|у|е|ы|а)?)(?![а-яё])"
)

_QUAL = rf"(?:{_DEMONSTRATIVE}|{_WORD_ORDINAL}\s+|{_WHOLE}\s+|{_NOUN_QUAL}\s+|{_ADJ_WORD}\s+)"

_ORDINAL_SUFFIX = r"(?:го|му|ой|ую|й|е|я|ю|о|м|х|ем)"

_PREP = re.compile(
    rf"(?<![а-яё])(?:под|об|во|ко|со|от|для|перед|после|при|за|на|по|из|к|в|с|о)\s+"
    rf"(?:{_QUAL}){{0,3}}(?<!без\s)(?<![а-яё]){_TARGET}(?![а-яё])",
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
    rf"(?:об|за|в|во|на|по|с|со|из|о|от|для|под|к|ко)\s+{_WORD_ORDINAL}\s+(?:{_QUAL}){{0,2}}(?<![а-яё]){_TARGET}(?![а-яё])"
    rf"|\b{_WORD_ORDINAL}\s+(?:{_QUAL}){{0,2}}(?<![а-яё]){_TARGET}(?![а-яё])",
    re.IGNORECASE,
)

_ORDINAL_NUM = re.compile(
    rf"\b\d{{1,2}}(?!\d)(?:-?{_ORDINAL_SUFFIX})?\s*(?:{_QUAL}){{0,2}}(?<![а-яё]){_TARGET}(?![а-яё])",
    re.IGNORECASE,
)

_SCOPED_AMOUNT = re.compile(
    rf"\b\d+(?:\s*[.,]\s*\d+)?\s*(?:{_QUAL}){{0,2}}(?<![а-яё]){_TARGET}(?![а-яё])",
    re.IGNORECASE,
)

_DOCS = re.compile(
    rf"(?:документ|файл)\w*\s+(?:{_QUAL}){{0,3}}(?<![а-яё]){_TARGET}(?![а-яё])",
    re.IGNORECASE,
)


DELETE_REFUSED_REPLY = (
    "Не удаляю файлы по виду «исполнительный лист» / «обеспечительные меры» / "
    "«собрание кредиторов» / «комитет кредиторов» вроде «за исполнительный лист» / "
    "«за обеспечительные меры» / «за собрание кредиторов» / "
    "«1-го исполнительного листа» — "
    "это не номер документа и не команда очистить всю папку. "
    "Укажите id: «удали документ 214» или «удали документы [12] [18]». "
    "Чтобы очистить открытую папку целиком, напишите «удали все документы в этой папке» "
    "без этих слов."
)

MOVE_REFUSED_REPLY = (
    "Не переношу все файлы папки по виду «исполнительный лист» / «обеспечительные меры» / "
    "«собрание кредиторов» / «комитет кредиторов» вроде «за исполнительный лист» / "
    "«за обеспечительные меры» / «за собрание кредиторов». "
    "Укажите id: «перенеси документ 214 в дело …». "
    "Чтобы перенести всю открытую папку, напишите без этих слов: "
    "«перенеси все документы в папку …»."
)


def _prepare(text: str) -> str:
    return (text or "").replace("ё", "е").replace("Ё", "Е")


def mask_enforcement_ordinals(text: str) -> str:
    """Replace «1-го исполнительного листа» so the digit is not a document id.

    Amounts run first so «12,5 исполнительного листа» is one token. The ordinal
    pass would otherwise keep «12» and only hide the «5».
    """
    raw = _prepare(text)
    masked = _SCOPED_AMOUNT.sub(" ", raw)
    return _ORDINAL_NUM.sub(" ", masked)


def looks_like_enforcement_scoped_document_request(text: str) -> bool:
    """True when the user scoped files to a writ, interim measures, or a creditors' meeting."""
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


def enforcement_blocks_bulk_document_mutation(
    text: str, *, explicit_document_ids: list[int] | None = None
) -> bool:
    """Refuse folder-wide delete/move when a writ, measures, or meeting scope is present.

    Chat treated «удали все документы за исполнительный лист в этой папке» as
    wipe-the-folder because «все документы» matched wants_all and «в этой папке»
    selected the open case. «удали документы 1-го исполнительного листа» took
    the first digit as a document id. The same path hits «за обеспечительные
    меры» and «за собрание кредиторов».
    """
    if explicit_document_ids:
        return False
    return looks_like_enforcement_scoped_document_request(text)
