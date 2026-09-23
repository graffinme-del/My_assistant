"""Bank-statement / register / appendix / schedule chat scope.

Do not treat «за выписку» / «за реестр» / «за приложение» / «за график»
as a folder wipe, and do not treat «1-го приложения» as document id 1.
"""

from __future__ import annotations

import re

# Noun after a time preposition: «за выписку», «на реестре», «в приложении»,
# «по графику». Trailing (?![а-яё]) is applied at the call site so
# «графический», «приложенный», «выписывать», «реестровый» do not steal the noun.
# «выписка» genitive plural is «выписок» (к drops), so the stem is «выпис».
_RECORD_NOUN = (
    r"(?:выпис(?:ками|кам|ках|кою|кой|ку|ке|ки|ка|ок)"
    r"|реестр(?:ами|ам|ах|ов|ом|у|е|ы|а)?"
    r"|приложени(?:ями|ям|ях|ем|ю|й|я|и|е)"
    r"|график(?:ами|ам|ах|ов|ом|у|е|и|а)?)"
)

# Optional qualifier before the noun: «банковская выписка», «платёжный график».
_RECORD_ADJ = (
    r"(?:(?:банковск(?:ий|ая|ое|ие|ого|ому|им|ом|ую|ой|их|ими))"
    r"|(?:календарн(?:ый|ая|ое|ые|ого|ому|ым|ом|ую|ой|ых|ыми))"
    r"|(?:плат[её]жн(?:ый|ая|ое|ые|ого|ому|ым|ом|ую|ой|ых|ыми))"
    r"|(?:рабоч(?:ий|ая|ее|ие|его|ему|им|ем|ую|ей|их|ими))"
    r"|(?:дополнительн(?:ый|ая|ое|ые|ого|ому|ым|ом|ую|ой|ых|ыми)))"
)

_DEMONSTRATIVE = (
    r"(?:это|эти|этих|этими|этот|этой|этом|эта|эту|"
    r"прошл\w{0,4}|текущ\w{0,4}|данн\w{0,4}|сво\w{0,4})\s+"
)

_WORD_ORDINAL = (
    r"(?:перв(?:ое|ого|ому|ым|ом|ая|ую|ой|ый|ые|ых|ыми)|втор(?:ое|ого|ому|ым|ом|ая|ую|ой|ый|ые|ых|ыми)|"
    r"трет(?:ье|ьего|ьему|ьим|ьем|ья|ью|ьей|ий|ьи|ьих|ьими)|четв[её]рт(?:ое|ого|ому|ым|ом|ая|ую|ой|ый|ые|ых|ыми))"
)

_MODIFIER = rf"(?:{_WORD_ORDINAL}|{_RECORD_ADJ})"

_PREP_RECORD = re.compile(
    rf"(?:за|на|в|во|по)\s+(?:{_DEMONSTRATIVE})?(?:(?<![а-яё]){_MODIFIER}\s+)?(?<![а-яё]){_RECORD_NOUN}(?![а-яё])",
    re.IGNORECASE,
)

_DURING_RECORD = re.compile(
    rf"во\s+время\s+(?:{_DEMONSTRATIVE})?(?:{_MODIFIER}\s+)?{_RECORD_NOUN}(?![а-яё])",
    re.IGNORECASE,
)

_DEMONSTRATIVE_RECORD = re.compile(
    rf"(?:эти|этих|этими|этот|этого|этому|этом|эта|эту|этой|"
    r"прошлые|прошлых|прошлый|прошлого|прошлая|прошлую|прошлое|"
    r"текущие|текущих|текущий|текущего|текущая|текущую|текущее|"
    r"данные|данных|данного)\s+"
    rf"(?:{_MODIFIER}\s+)?{_RECORD_NOUN}(?![а-яё])",
    re.IGNORECASE,
)

_ORDINAL_RECORD_WORD = re.compile(
    rf"(?:за|в|во|на|по)\s+{_WORD_ORDINAL}\s+(?:{_RECORD_ADJ}\s+)?{_RECORD_NOUN}(?![а-яё])"
    rf"|\b{_WORD_ORDINAL}\s+(?:{_RECORD_ADJ}\s+)?{_RECORD_NOUN}(?![а-яё])",
    re.IGNORECASE,
)

# «1-й выписки», «1-го реестра», «1-го приложения», «1-го графика».
# Two digits so document ids like 214 stay ids. Full noun + boundary so
# «1-го человека» is not an appendix ordinal.
_ORDINAL_RECORD_NUM = re.compile(
    rf"\b\d{{1,2}}(?:-?(?:го|му|ой|ую|й|е|я|ю|о|м|х|ем))?\s*{_RECORD_NOUN}(?![а-яё])",
    re.IGNORECASE,
)

# «документы выписки» / «документы приложения» — genitive scope, not a folder
# titled «Выписка» / «Приложение».
_RECORD_DOCS = re.compile(
    rf"(?:документ|файл)\w*\s+(?:{_DEMONSTRATIVE})?(?:{_MODIFIER}\s+)?{_RECORD_NOUN}(?![а-яё])",
    re.IGNORECASE,
)

# «выписочные документы» / «реестровые документы».
_RECORD_ADJ_DOCS = re.compile(
    r"(?<![а-яё])(?:выписочн(?:ый|ая|ое|ые|ого|ому|ым|ом|ую|ой|ых|ыми)|"
    r"реестров(?:ый|ая|ое|ые|ого|ому|ым|ом|ую|ой|ых|ыми))\s+(?:документ|файл)",
    re.IGNORECASE,
)

DELETE_REFUSED_RECORD = (
    "Не удаляю файлы по выписке / реестру / приложению / "
    "графику вроде «за выписку» / «за реестр» / "
    "«за приложение» / «за график» / "
    "«1-го приложения» — это не номер документа и не команда очистить всю папку. "
    "Укажите id: «удали документ 214» или «удали документы [12] [18]». "
    "Чтобы очистить открытую папку целиком, напишите «удали все документы в этой папке» "
    "без выписки, реестра, приложения и графика."
)

MOVE_REFUSED_RECORD = (
    "Не переношу все файлы папки по выписке / реестру / приложению / "
    "графику вроде «за выписку» / «за реестр» / "
    "«за приложение» / «за график». "
    "Укажите id: «перенеси документ 214 в дело …». "
    "Чтобы перенести всю открытую папку, напишите без выписки и приложения: "
    "«перенеси все документы в папку …»."
)


def mask_record_ordinals(text: str) -> str:
    """Replace «1-го приложения» so the leading digit cannot be parsed as a document id."""
    return _ORDINAL_RECORD_NUM.sub(" ", text or "")


def looks_like_record_scoped_document_request(text: str) -> bool:
    """True when the user scoped files to a statement, register, appendix, or schedule."""
    raw = text or ""
    if (
        _PREP_RECORD.search(raw)
        or _DURING_RECORD.search(raw)
        or _DEMONSTRATIVE_RECORD.search(raw)
        or _ORDINAL_RECORD_WORD.search(raw)
        or _ORDINAL_RECORD_NUM.search(raw)
        or _RECORD_DOCS.search(raw)
        or _RECORD_ADJ_DOCS.search(raw)
    ):
        return True
    return False


def record_blocks_bulk_document_mutation(
    text: str, *, explicit_document_ids: list[int] | None = None
) -> bool:
    """Refuse folder-wide delete/move when a statement/register/appendix/schedule scope is present.

    Chat used to treat «удали все документы за выписку в этой папке» as wipe-the-folder because
    «все документы» matched wants_all and the statement phrase was ignored. «удали документы
    1-го приложения» took the first digit as a document id.
    """
    if explicit_document_ids:
        return False
    return looks_like_record_scoped_document_request(text)
