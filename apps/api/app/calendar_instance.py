"""Supervisory-review / court-instance chat scope: do not treat «за надзор» as a folder wipe."""

from __future__ import annotations

import re

# Noun after a time preposition: «за надзор», «на инстанции», «по надзору».
# Trailing (?![а-яё]) is applied at the call site so «надзорный» does not steal the noun slot.
_INSTANCE_NOUN = (
    r"(?:надзор(?:а|у|ом|е|ы|ов|ам|ами|ах)?"
    r"|инстанци(?:я|и|ю|ей|ею|ям|ями|ях)?)"
)

_INSTANCE_ADJ = (
    r"(?:(?:надзорн(?:ый|ая|ое|ые|ого|ому|ым|ом|ую|ой|ых|ыми))"
    r"|(?:апелляционн(?:ый|ая|ое|ые|ого|ому|ым|ом|ую|ой|ых|ыми))"
    r"|(?:кассационн(?:ый|ая|ое|ые|ого|ому|ым|ом|ую|ой|ых|ыми)))"
)

# «надзорная жалоба» — supervisory complaint, not bare «жалоба».
_COMPLAINT_NOUN = r"(?:жалоб(?:а|ы|у|е|ой|ам|ами|ах)?)"
_COMPLAINT_ADJ = r"(?:надзорн(?:ый|ая|ое|ые|ого|ому|ым|ом|ую|ой|ых|ыми))"

_DEMONSTRATIVE = (
    r"(?:это|эти|этих|этими|этот|этой|этом|эта|эту|"
    r"прошл\w{0,4}|текущ\w{0,4}|данн\w{0,4}|сво\w{0,4})\s+"
)

_WORD_ORDINAL = (
    r"(?:перв(?:ое|ого|ому|ым|ом|ая|ую|ой|ый|ые|ых|ыми)|втор(?:ое|ого|ому|ым|ом|ая|ую|ой|ый|ые|ых|ыми)|"
    r"трет(?:ье|ьего|ьему|ьим|ьем|ья|ью|ьей|ий|ьи|ьих|ьими)|четв[её]рт(?:ое|ого|ому|ым|ом|ая|ую|ой|ый|ые|ых|ыми))"
)

_MODIFIER = rf"(?:{_WORD_ORDINAL}|{_INSTANCE_ADJ})"

# Wrap the demonstrative: `{_DEMONSTRATIVE}?` would make only the trailing `\s+` optional.
_PREP_INSTANCE = re.compile(
    rf"(?:за|на|в|во|по)\s+(?:{_DEMONSTRATIVE})?(?:(?<![а-яё]){_MODIFIER}\s+)?(?<![а-яё]){_INSTANCE_NOUN}(?![а-яё])",
    re.IGNORECASE,
)

_PREP_COMPLAINT = re.compile(
    rf"(?:за|на|в|во|по)\s+(?:{_DEMONSTRATIVE})?(?<![а-яё]){_COMPLAINT_ADJ}\s+(?<![а-яё]){_COMPLAINT_NOUN}(?![а-яё])",
    re.IGNORECASE,
)

_DURING_INSTANCE = re.compile(
    rf"во\s+время\s+(?:{_DEMONSTRATIVE})?(?:{_MODIFIER}\s+)?{_INSTANCE_NOUN}(?![а-яё])",
    re.IGNORECASE,
)

_DURING_COMPLAINT = re.compile(
    rf"во\s+время\s+(?:{_DEMONSTRATIVE})?{_COMPLAINT_ADJ}\s+{_COMPLAINT_NOUN}(?![а-яё])",
    re.IGNORECASE,
)

_DEMONSTRATIVE_INSTANCE = re.compile(
    rf"(?:эти|этих|этими|этот|этого|этом|эта|эту|этой|"
    r"прошлые|прошлых|прошлый|прошлая|прошлую|прошлое|"
    r"текущие|текущих|текущий|текущая|текущую|текущее|"
    r"данные|данных)\s+"
    rf"(?:{_MODIFIER}\s+)?{_INSTANCE_NOUN}(?![а-яё])",
    re.IGNORECASE,
)

_ORDINAL_INSTANCE_WORD = re.compile(
    rf"(?:за|в|во|на|по)\s+{_WORD_ORDINAL}\s+(?:{_INSTANCE_ADJ}\s+)?(?:{_INSTANCE_NOUN}|{_COMPLAINT_NOUN})(?![а-яё])"
    rf"|\b{_WORD_ORDINAL}\s+(?:{_INSTANCE_ADJ}\s+)?(?:{_INSTANCE_NOUN}|{_COMPLAINT_NOUN})(?![а-яё])",
    re.IGNORECASE,
)

# «1-й инстанции», «1-го надзора», «1-й надзорной жалобы» — not a document id.
_ORDINAL_INSTANCE_NUM = re.compile(
    r"\b\d{1,2}(?:-?(?:го|му|ой|ую|й|е|я|ю|о|м|х|ем))?\s*"
    r"(?:надзор|инстанци)",
    re.IGNORECASE,
)

# «документы надзора» / «документы первой инстанции» — genitive scope,
# not a folder titled «Надзор».
_INSTANCE_DOCS = re.compile(
    rf"(?:документ|файл)\w*\s+(?:{_MODIFIER}\s+)?{_INSTANCE_NOUN}(?![а-яё])",
    re.IGNORECASE,
)

_COMPLAINT_DOCS = re.compile(
    rf"(?:документ|файл)\w*\s+{_COMPLAINT_ADJ}\s+{_COMPLAINT_NOUN}(?![а-яё])",
    re.IGNORECASE,
)

# «надзорные документы» — adj + files, not «судебные документы».
_INSTANCE_ADJ_DOCS = re.compile(
    rf"(?<![а-яё]){_COMPLAINT_ADJ}\s+(?:документ|файл)",
    re.IGNORECASE,
)

DELETE_REFUSED_INSTANCE = (
    "Не удаляю файлы по надзору/инстанции вроде «за надзор» / "
    "«за надзорную жалобу» / «за первую инстанцию» / «за вторую инстанцию» / "
    "«1-й инстанции» — это не номер документа и не команда очистить всю папку. "
    "Укажите id: «удали документ 214» или «удали документы [12] [18]». "
    "Чтобы очистить открытую папку целиком, напишите «удали все документы в этой папке» "
    "без надзора и инстанции."
)

MOVE_REFUSED_INSTANCE = (
    "Не переношу все файлы папки по надзору/инстанции вроде "
    "«за надзор» / «за надзорную жалобу» / «за первую инстанцию». "
    "Укажите id: «перенеси документ 214 в дело …». "
    "Чтобы перенести всю открытую папку, напишите без надзора: "
    "«перенеси все документы в папку …»."
)


def mask_instance_ordinals(text: str) -> str:
    """Replace «1-й инстанции» so the leading digit cannot be parsed as a document id."""
    return _ORDINAL_INSTANCE_NUM.sub(" ", text or "")


def looks_like_instance_scoped_document_request(text: str) -> bool:
    """True when the user scoped files to a supervisory review or court instance."""
    raw = text or ""
    if (
        _PREP_INSTANCE.search(raw)
        or _PREP_COMPLAINT.search(raw)
        or _DURING_INSTANCE.search(raw)
        or _DURING_COMPLAINT.search(raw)
        or _DEMONSTRATIVE_INSTANCE.search(raw)
        or _ORDINAL_INSTANCE_WORD.search(raw)
        or _ORDINAL_INSTANCE_NUM.search(raw)
        or _INSTANCE_DOCS.search(raw)
        or _COMPLAINT_DOCS.search(raw)
        or _INSTANCE_ADJ_DOCS.search(raw)
    ):
        return True
    return False


def instance_blocks_bulk_document_mutation(
    text: str, *, explicit_document_ids: list[int] | None = None
) -> bool:
    """Refuse folder-wide delete/move when a supervisory/instance scope is present and no explicit [id] was given.

    Chat used to treat «удали все документы за надзор в этой папке» as wipe-the-folder because
    «все документы» matched wants_all and the instance phrase was ignored. «удали документы
    1-й инстанции» took the first digit as a document id.
    """
    if explicit_document_ids:
        return False
    return looks_like_instance_scoped_document_request(text)
