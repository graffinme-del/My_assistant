"""Hearing/session chat scope: do not treat «за заседание» / «на слушании» as a folder wipe."""

from __future__ import annotations

import re

# Noun after a time preposition: «за заседание», «на слушании», «по заседаниям».
# Trailing (?![а-яё]) is applied at the call site so «заседательный» does not steal the noun slot.
_HEARING_NOUN = (
    r"(?:заседани(?:е|я|ю|ем|и|й|ям|ями|ях)?"
    r"|слушани(?:е|я|ю|ем|и|й|ям|ями|ях)?)"
)

_HEARING_ADJ = (
    r"(?:(?:судебн(?:ый|ая|ое|ые|ого|ому|ым|ом|ую|ой|ых|ыми))"
    r"|(?:предварительн(?:ый|ая|ое|ые|ого|ому|ым|ом|ую|ой|ых|ыми)))"
)

_DEMONSTRATIVE = (
    r"(?:это|эти|этих|этими|этот|этой|этом|эта|эту|"
    r"прошл\w{0,4}|текущ\w{0,4}|данн\w{0,4}|сво\w{0,4})\s+"
)

# Wrap the demonstrative: `{_DEMONSTRATIVE}?` would make only the trailing `\s+` optional.
_PREP_HEARING = re.compile(
    rf"(?:за|на|в|во|по)\s+(?:{_DEMONSTRATIVE})?(?:(?<![а-яё]){_HEARING_ADJ}\s+)?(?<![а-яё]){_HEARING_NOUN}(?![а-яё])",
    re.IGNORECASE,
)

_DURING_HEARING = re.compile(
    rf"во\s+время\s+(?:{_DEMONSTRATIVE})?(?:{_HEARING_ADJ}\s+)?{_HEARING_NOUN}(?![а-яё])",
    re.IGNORECASE,
)

_DEMONSTRATIVE_HEARING = re.compile(
    rf"(?:эти|этих|этими|этот|этого|этом|эта|эту|этой|"
    r"прошлые|прошлых|прошлый|прошлая|прошлую|прошлое|"
    r"текущие|текущих|текущий|текущая|текущую|текущее|"
    r"данные|данных)\s+"
    rf"(?:{_HEARING_ADJ}\s+)?{_HEARING_NOUN}(?![а-яё])",
    re.IGNORECASE,
)

_WORD_ORDINAL = (
    r"(?:перв(?:ое|ого|ому|ым|ом|ая|ую|ой|ый|ые|ых|ыми)|втор(?:ое|ого|ому|ым|ом|ая|ую|ой|ый|ые|ых|ыми)|"
    r"трет(?:ье|ьего|ьему|ьим|ьем|ья|ью|ьей|ий|ьи|ьих|ьими)|четв[её]рт(?:ое|ого|ому|ым|ом|ая|ую|ой|ый|ые|ых|ыми))"
)

_ORDINAL_HEARING_WORD = re.compile(
    rf"(?:за|в|во|на|по)\s+{_WORD_ORDINAL}\s+{_HEARING_NOUN}(?![а-яё])"
    rf"|\b{_WORD_ORDINAL}\s+{_HEARING_NOUN}(?![а-яё])",
    re.IGNORECASE,
)

# «1-го заседания», «1-е слушание», «1 заседание» — not a document id.
_ORDINAL_HEARING_NUM = re.compile(
    r"\b\d{1,2}(?:-?(?:го|му|ой|ую|й|е|я|ю|о|м|х|ем))?\s*(?:заседани|слушани)",
    re.IGNORECASE,
)

# «документы заседания» / «документы судебного слушания» — genitive scope, not a folder titled «Заседание».
_HEARING_DOCS = re.compile(
    rf"(?:документ|файл)\w*\s+(?:{_HEARING_ADJ}\s+)?{_HEARING_NOUN}(?![а-яё])",
    re.IGNORECASE,
)

DELETE_REFUSED_HEARING = (
    "Не удаляю файлы по заседанию/слушанию вроде «за заседание» / «за слушание» / "
    "«на заседании» / «документы заседания» / «1-го заседания» — это не номер документа "
    "и не команда очистить всю папку. "
    "Укажите id: «удали документ 214» или «удали документы [12] [18]». "
    "Чтобы очистить открытую папку целиком, напишите «удали все документы в этой папке» "
    "без заседания и слушания."
)

MOVE_REFUSED_HEARING = (
    "Не переношу все файлы папки по заседанию/слушанию вроде «за заседание» / "
    "«за слушание» / «на заседании» / «документы заседания». "
    "Укажите id: «перенеси документ 214 в дело …». "
    "Чтобы перенести всю открытую папку, напишите без заседания: "
    "«перенеси все документы в папку …»."
)


def mask_hearing_ordinals(text: str) -> str:
    """Replace «1-го заседания» so the leading digit cannot be parsed as a document id."""
    return _ORDINAL_HEARING_NUM.sub(" ", text or "")


def looks_like_hearing_scoped_document_request(text: str) -> bool:
    """True when the user scoped files to a hearing or court session."""
    raw = text or ""
    if (
        _PREP_HEARING.search(raw)
        or _DURING_HEARING.search(raw)
        or _DEMONSTRATIVE_HEARING.search(raw)
        or _ORDINAL_HEARING_WORD.search(raw)
        or _ORDINAL_HEARING_NUM.search(raw)
        or _HEARING_DOCS.search(raw)
    ):
        return True
    return False


def hearing_blocks_bulk_document_mutation(
    text: str, *, explicit_document_ids: list[int] | None = None
) -> bool:
    """Refuse folder-wide delete/move when a hearing/session scope is present and no explicit [id] was given.

    Chat used to treat «удали все документы за заседание в этой папке» as wipe-the-folder because
    «все документы» matched wants_all and the hearing phrase was ignored. «удали документы
    1-го заседания» took the first digit as a document id.
    """
    if explicit_document_ids:
        return False
    return looks_like_hearing_scoped_document_request(text)
