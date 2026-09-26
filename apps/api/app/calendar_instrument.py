"""Work-act / internal-instrument chat scope.

Do not treat «за акт» (выполненных работ, приёма-передачи), «за распоряжение»,
«за положение», «за заключение», «за отчёт», or «за платежное поручение»
as a folder wipe, and do not treat «1-го акта» as document id 1.

«Акт сверки» is a different collocation and is intentionally not matched here.
"""

from __future__ import annotations

import re

# Bare «акт» excludes «акт сверки» via (?!\s+свер). Trailing (?![а-яё]) is applied
# at the call site so «актуальный», «актив», «контракт», «факт», «отчётность»,
# «расположение», and «заключительный» do not match.
_ACT = r"акт(?:ами|ах|ам|ом|ов|у|е|а|ы)?(?!\s+свер)"
_DIRECTIVE = r"распоряжени(?:ями|ях|ям|ем|ю|я|и|й|е)"
_REGULATION = r"положени(?:ями|ях|ям|ем|ю|я|и|й|е)"
_OPINION = r"заключени(?:ями|ях|ям|ем|ю|я|и|й|е)"
_REPORT = r"отч[её]т(?:ами|ах|ам|ом|ов|у|е|а|ы)?"
_PAY_ORDER = r"плат[её]жн[а-яё]{1,4}\s+поручени(?:ями|ях|ям|ем|ю|я|и|й|е)"

_NOUN = rf"(?:{_PAY_ORDER}|{_DIRECTIVE}|{_REGULATION}|{_OPINION}|{_REPORT}|{_ACT})"

_DEMONSTRATIVE = (
    r"(?:этими|этих|этот|этого|этому|этой|этом|эта|эту|эти|это|"
    r"прошл\w{0,4}|текущ\w{0,4}|данн\w{0,4}|сво\w{0,4})\s+"
)

_WORD_ORDINAL = (
    r"(?:перв(?:ое|ого|ому|ым|ом|ая|ую|ой|ый|ые|ых|ыми)|втор(?:ое|ого|ому|ым|ом|ая|ую|ой|ый|ые|ых|ыми)|"
    r"трет(?:ье|ьего|ьему|ьим|ьем|ья|ью|ьей|ий|ьи|ьих|ьими)|четв[её]рт(?:ое|ого|ому|ым|ом|ая|ую|ой|ый|ые|ых|ыми))"
)

# One qualifier word: «выполненный акт», «годовой отчёт», «исходящее платежное поручение».
_ADJ_WORD = (
    r"[а-яё]{3,}(?:ый|ий|ой|ая|яя|ое|ее|ые|ие|ого|его|ому|ему|ым|им|ом|ем|ую|юю|ых|их|ыми|ими)"
)

_QUAL = rf"(?:{_DEMONSTRATIVE}|{_WORD_ORDINAL}\s+|{_ADJ_WORD}\s+)"

_PREP = re.compile(
    rf"(?<![а-яё])(?:за|на|в|во|по)\s+(?:{_QUAL}){{0,3}}(?<![а-яё]){_NOUN}(?![а-яё])",
    re.IGNORECASE,
)

_DURING = re.compile(
    rf"во\s+время\s+(?:{_QUAL}){{0,3}}(?<![а-яё]){_NOUN}(?![а-яё])",
    re.IGNORECASE,
)

_DEMONSTRATIVE_SCOPE = re.compile(
    rf"(?:этими|этих|этот|этого|этому|этой|этом|эта|эту|эти|"
    r"прошлые|прошлых|прошлый|прошлого|прошлая|прошлую|прошлое|"
    r"текущие|текущих|текущий|текущего|текущая|текущую|текущее|"
    r"данные|данных|данного)\s+"
    rf"(?:{_QUAL}){{0,2}}(?<![а-яё]){_NOUN}(?![а-яё])",
    re.IGNORECASE,
)

_ORDINAL_WORD = re.compile(
    rf"(?:за|в|во|на|по)\s+{_WORD_ORDINAL}\s+(?:{_QUAL}){{0,2}}(?<![а-яё]){_NOUN}(?![а-яё])"
    rf"|\b{_WORD_ORDINAL}\s+(?:{_QUAL}){{0,2}}(?<![а-яё]){_NOUN}(?![а-яё])",
    re.IGNORECASE,
)

# «1-го акта», «1-е заключение», «1-го платежного поручения».
# Two digits so ids like 214 stay ids.
_ORDINAL_NUM = re.compile(
    rf"\b\d{{1,2}}(?:-?(?:го|му|ой|ую|й|е|я|ю|о|м|х|ем))?\s*(?:{_QUAL}){{0,2}}(?<![а-яё]){_NOUN}(?![а-яё])",
    re.IGNORECASE,
)

# «документы акта» / «документы отчёта» — genitive scope, not a folder titled «Акт».
_DOCS = re.compile(
    rf"(?:документ|файл)\w*\s+(?:{_QUAL}){{0,3}}(?<![а-яё]){_NOUN}(?![а-яё])",
    re.IGNORECASE,
)

DELETE_REFUSED_INSTRUMENT = (
    "Не удаляю файлы по акту выполненных работ, акту приёма-передачи, распоряжению, "
    "положению, заключению, отчёту или платёжному поручению "
    "вроде «за акт» / «за распоряжение» / «за положение» / «за заключение» / "
    "«за отчёт» / «за платежное поручение» / «1-го акта» — "
    "это не номер документа и не команда очистить всю папку. "
    "Укажите id: «удали документ 214» или «удали документы [12] [18]». "
    "Чтобы очистить открытую папку целиком, напишите «удали все документы в этой папке» "
    "без акта, распоряжения, положения, заключения, отчёта и платёжного поручения."
)

MOVE_REFUSED_INSTRUMENT = (
    "Не переношу все файлы папки по акту, распоряжению, положению, заключению, "
    "отчёту или платёжному поручению "
    "вроде «за акт» / «за распоряжение» / «за отчёт» / «за платежное поручение». "
    "Укажите id: «перенеси документ 214 в дело …». "
    "Чтобы перенести всю открытую папку, напишите без такого документа: "
    "«перенеси все документы в папку …»."
)


def mask_instrument_ordinals(text: str) -> str:
    """Replace «1-го акта» so the leading digit cannot be parsed as a document id."""
    return _ORDINAL_NUM.sub(" ", text or "")


def looks_like_instrument_scoped_document_request(text: str) -> bool:
    """True when the user scoped files to a work act, directive, report, or payment order."""
    raw = text or ""
    if (
        _PREP.search(raw)
        or _DURING.search(raw)
        or _DEMONSTRATIVE_SCOPE.search(raw)
        or _ORDINAL_WORD.search(raw)
        or _ORDINAL_NUM.search(raw)
        or _DOCS.search(raw)
    ):
        return True
    return False


def instrument_blocks_bulk_document_mutation(
    text: str, *, explicit_document_ids: list[int] | None = None
) -> bool:
    """Refuse folder-wide delete/move when a work-act or report scope is present.

    Chat used to treat «удали все документы за акт выполненных работ в этой папке» as
    wipe-the-folder because «все документы» matched wants_all and the document-type
    phrase was ignored. «удали документы 1-го акта» took the first digit as a document id.
    """
    if explicit_document_ids:
        return False
    return looks_like_instrument_scoped_document_request(text)
