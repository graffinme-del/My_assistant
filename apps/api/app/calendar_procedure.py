"""Insolvency and enforcement procedure scope.

Do not treat «за конкурсное производство» / «за конкурсную массу» /
«за наблюдение» / «за внешнее управление» / «за финансовое оздоровление» /
«за исполнительное производство» as a folder wipe, and do not treat
«1-го наблюдения» / «100 конкурсной массы» as a document id.

A folder titled «Наблюдение» or «Конкурсное производство» does not match.
«без наблюдения» does not match. Bare «банкротство» does not match: help text
uses it as a case title («удали все документы по делу Банкротство Эмиль»).
«внешний управляющий» and «исполнительный лист» are not these phrases.
"""

from __future__ import annotations

import re

# Neuter/plural «конкурсн*» plus the noun. «конкурсный управляющий» has no «производств».
_KONKURS_ADJ = r"конкурсн(?:ыми|ого|ому|ая|ой|ую|ое|ые|ых|ым|ом|ый)"
_PROIZV = r"производств(?:ами|ах|ам|ом|о|а|у|е|ы)?"
_KONKURS_PROC = rf"{_KONKURS_ADJ}\s+{_PROIZV}"
_MASSA = rf"{_KONKURS_ADJ}\s+масс(?:ами|ах|ам|ою|ой|у|е|ы|а)?"

# «наблюдение». «наблюдать» / «наблюдатель» do not contain this stem.
_OBSERV = r"наблюдени(?:ями|ях|ям|ем|ею|ю|и|е|я|й)?"

# «внешнее управление». «внешний управляющий» is «управляющ», not «управлени».
_VNESH = r"внешн(?:ими|его|ему|ее|ие|их|ым|им|ем)"
_UPRAV = r"управлени(?:ями|ях|ям|ем|ею|ю|и|е|я|й)?"
_VNESH_UPR = rf"{_VNESH}\s+{_UPRAV}"

# «финансовое оздоровление». «финансовый управляющий» does not match.
_FIN = r"финансов(?:ыми|ого|ому|ое|ые|ых|ым|ом)"
_OZD = r"оздоровлени(?:ями|ях|ям|ем|ею|ю|и|е|я|й)?"
_FIN_OZD = rf"{_FIN}\s+{_OZD}"

# «исполнительное производство». «исполнительный лист» does not match.
_ISP_ADJ = r"исполнительн(?:ыми|ого|ому|ое|ые|ых|ым|ом)"
_ISP_PROC = rf"{_ISP_ADJ}\s+{_PROIZV}"

_TARGET = rf"(?:{_KONKURS_PROC}|{_MASSA}|{_VNESH_UPR}|{_FIN_OZD}|{_ISP_PROC}|{_OBSERV})"

_DEMONSTRATIVE = (
    r"(?:этими|этих|этот|этого|этому|этой|этом|эта|эту|эти|это|"
    r"прошл\w{0,4}|текущ\w{0,4}|данн\w{0,4}|сво\w{0,4})\s+"
)

_WORD_ORDINAL = (
    r"(?:перв(?:ое|ого|ому|ым|ом|ая|ую|ой|ый|ые|ых|ыми)|втор(?:ое|ого|ому|ым|ом|ая|ую|ой|ый|ые|ых|ыми)|"
    r"трет(?:ье|ьего|ьему|ьим|ьем|ья|ью|ьей|ий|ьи|ьих|ьими)|четв[её]рт(?:ое|ого|ому|ым|ом|ая|ую|ой|ый|ые|ых|ыми))"
)

_ADJ_WORD = (
    r"(?:[а-яё]{3,}-)?[а-яё]{3,}(?:ыми|ими|ый|ий|ой|ая|яя|ое|ее|ые|ие|ого|его|ому|ему|ым|им|ом|ем|ую|юю|ых|их)"
)

_WHOLE = r"(?<![а-яё])(?:всеми|всех|всему|всего|всей|всем|весь|вся|всё|все|всю)"

# Words that sit between the preposition and the procedure.
# «процедура конкурсного производства», «введение наблюдения», «открытие конкурсного производства».
# «папке» and «делу» are not here, so a folder titled «Наблюдение» does not match.
_NOUN_QUAL = (
    r"(?<![а-яё])(?:процедур(?:ами|ах|ам|ою|ой|у|е|ы|а)?"
    r"|стади(?:ями|ях|ям|ей|ею|ю|и|е|я)?"
    r"|введени(?:ями|ях|ям|ем|ею|ю|и|е|я|й)?"
    r"|открыти(?:ями|ях|ям|ем|ею|ю|и|е|я|й)?"
    r"|возбуждени(?:ями|ях|ям|ем|ею|ю|и|е|я|й)?"
    r"|завершени(?:ями|ях|ям|ем|ею|ю|и|е|я|й)?"
    r"|формировани(?:ями|ях|ям|ем|ею|ю|и|е|я|й)?"
    r"|период(?:ами|ах|ам|ов|ом|е|а|у|ы)?"
    r"|состав(?:ами|ах|ам|ов|ом|е|а|у|ы)?"
    r"|ход(?:ами|ах|ам|ов|ом|е|а|у|ы)?"
    r"|рамк(?:ами|ах|ам|ою|ой|у|е|и|а)?)(?![а-яё])"
)

_QUAL = rf"(?:{_DEMONSTRATIVE}|{_WORD_ORDINAL}\s+|{_WHOLE}\s+|{_NOUN_QUAL}\s+|{_ADJ_WORD}\s+)"

_ORDINAL_SUFFIX = r"(?:го|му|ой|ую|й|е|я|ю|о|м|х|ем)"

_PREP = re.compile(
    rf"(?<![а-яё])(?:под|об|во|ко|со|за|на|по|из|к|в|с|о)\s+(?:{_QUAL}){{0,3}}(?<!без\s)(?<![а-яё]){_TARGET}(?![а-яё])",
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
    "Не удаляю файлы по виду «конкурсное производство» / «конкурсная масса» / "
    "«наблюдение» / «внешнее управление» / «финансовое оздоровление» / "
    "«исполнительное производство» вроде «за конкурсное производство» / "
    "«за наблюдение» / «за внешнее управление» / «1-го наблюдения» — "
    "это не номер документа и не команда очистить всю папку. "
    "Укажите id: «удали документ 214» или «удали документы [12] [18]». "
    "Чтобы очистить открытую папку целиком, напишите «удали все документы в этой папке» "
    "без этих слов."
)

MOVE_REFUSED_REPLY = (
    "Не переношу все файлы папки по виду «конкурсное производство» / «конкурсная масса» / "
    "«наблюдение» / «внешнее управление» / «финансовое оздоровление» / "
    "«исполнительное производство» вроде «за конкурсное производство» / «за наблюдение». "
    "Укажите id: «перенеси документ 214 в дело …». "
    "Чтобы перенести всю открытую папку, напишите без этих слов: "
    "«перенеси все документы в папку …»."
)


def mask_procedure_ordinals(text: str) -> str:
    """Replace «1-го наблюдения» / «100 конкурсной массы» so the digit is not a document id.

    Amounts run first so «12,5 конкурсной массы» is one token. The ordinal pass would
    otherwise keep «12» and only hide the «5».
    """
    masked = _SCOPED_AMOUNT.sub(" ", text or "")
    return _ORDINAL_NUM.sub(" ", masked)


def looks_like_procedure_scoped_document_request(text: str) -> bool:
    """True when the user scoped files to an insolvency or enforcement procedure."""
    raw = text or ""
    return bool(
        _PREP.search(raw)
        or _DURING.search(raw)
        or _DEMONSTRATIVE_SCOPE.search(raw)
        or _ORDINAL_WORD.search(raw)
        or _ORDINAL_NUM.search(raw)
        or _SCOPED_AMOUNT.search(raw)
        or _DOCS.search(raw)
    )


def procedure_blocks_bulk_document_mutation(
    text: str, *, explicit_document_ids: list[int] | None = None
) -> bool:
    """Refuse folder-wide delete/move when a procedure scope is present.

    Chat treated «удали все документы за конкурсное производство в этой папке» as
    wipe-the-folder because «все документы» matched wants_all and the procedure
    words were ignored. «удали документы 1-го наблюдения» took the first digit as
    a document id. The same path hits конкурсная масса, внешнее управление,
    финансовое оздоровление, and исполнительное производство.
    """
    if explicit_document_ids:
        return False
    return looks_like_procedure_scoped_document_request(text)
