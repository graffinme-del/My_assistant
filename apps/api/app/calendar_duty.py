"""Duty/rotation-class chat scope: do not treat «за дежурство» / «вахтовые документы» as a folder wipe."""

from __future__ import annotations

import re

# Noun after a time preposition: «за дежурство», «на вахте», «по дежурствам».
# Trailing (?![а-яё]) is applied at the call site so «вахтенный» does not match.
_DUTY_NOUN = (
    r"(?:дежурств(?:о|а|у|е|ом|ами|ам|ах)?"
    r"|вахт(?:а|ы|е|у|ой|ою|ах|ам|ами)?)"
)

_DUTY_ADJ = (
    r"(?:(?:дежурн(?:ый|ая|ое|ые|ого|ому|ым|ом|ую|ой|ых|ыми))"
    r"|(?:вахтов(?:ый|ая|ое|ые|ого|ому|ым|ом|ую|ой|ых|ыми)))"
)

_DEMONSTRATIVE = (
    r"(?:это|эти|этих|этими|этот|этой|этом|эта|эту|"
    r"прошл\w{0,4}|текущ\w{0,4}|данн\w{0,4}|сво\w{0,4})\s+"
)

# Wrap the demonstrative: `{_DEMONSTRATIVE}?` would make only the trailing `\s+` optional.
_PREP_DUTY = re.compile(
    rf"(?:за|на|в|во|по)\s+(?:{_DEMONSTRATIVE})?(?:(?<![а-яё]){_DUTY_ADJ}\s+)?(?<![а-яё]){_DUTY_NOUN}(?![а-яё])",
    re.IGNORECASE,
)

_DURING_DUTY = re.compile(
    rf"во\s+время\s+(?:{_DEMONSTRATIVE})?(?:{_DUTY_ADJ}\s+)?{_DUTY_NOUN}(?![а-яё])",
    re.IGNORECASE,
)

_DEMONSTRATIVE_DUTY = re.compile(
    rf"(?:эти|этих|этими|этот|этого|этом|эта|эту|этой|"
    r"прошлые|прошлых|прошлый|прошлая|прошлую|прошлое|"
    r"текущие|текущих|текущий|текущая|текущую|текущее|"
    r"данные|данных)\s+"
    rf"(?:{_DUTY_ADJ}\s+)?{_DUTY_NOUN}(?![а-яё])",
    re.IGNORECASE,
)

_WORD_ORDINAL = (
    r"(?:перв(?:ое|ого|ому|ым|ом|ая|ую|ой|ый)|втор(?:ое|ого|ому|ым|ом|ая|ую|ой|ый)|"
    r"трет(?:ье|ьего|ьему|ьим|ьем|ья|ью|ьей|ий)|четв[её]рт(?:ое|ого|ому|ым|ом|ая|ую|ой|ый))"
)

_ORDINAL_DUTY_WORD = re.compile(
    rf"(?:за|в|во|на|по)\s+{_WORD_ORDINAL}\s+{_DUTY_NOUN}(?![а-яё])"
    rf"|\b{_WORD_ORDINAL}\s+{_DUTY_NOUN}(?![а-яё])",
    re.IGNORECASE,
)

# «1-го дежурства», «1-й вахты», «1 вахты» — not a document id.
_ORDINAL_DUTY_NUM = re.compile(
    r"\b\d{1,2}(?:-?(?:го|му|ой|ую|й|е|я|ю|о|м))?\s*(?:дежурств|вахт)",
    re.IGNORECASE,
)

# «дежурные документы» / «документы вахтовые» — collocation, not a folder titled «Дежурство».
_DUTY_ADJ_DOCS = re.compile(
    rf"(?:(?<![а-яё]){_DUTY_ADJ}\s+(?:документ|файл)\w*"
    rf"|(?:документ|файл)\w*\s+(?<![а-яё]){_DUTY_ADJ})(?![а-яё])",
    re.IGNORECASE,
)

DELETE_REFUSED_DUTY = (
    "Не удаляю файлы по дежурству/вахте вроде «за дежурство» / «за вахту» / "
    "«дежурные документы» / «1-го дежурства» — это не номер документа и не команда очистить всю папку. "
    "Укажите id: «удали документ 214» или «удали документы [12] [18]». "
    "Чтобы очистить открытую папку целиком, напишите «удали все документы в этой папке» "
    "без дежурства и вахтовых документов."
)

MOVE_REFUSED_DUTY = (
    "Не переношу все файлы папки по дежурству/вахте вроде «за дежурство» / "
    "«за вахту» / «дежурные документы». "
    "Укажите id: «перенеси документ 214 в дело …». "
    "Чтобы перенести всю открытую папку, напишите без дежурства: "
    "«перенеси все документы в папку …»."
)


def mask_duty_ordinals(text: str) -> str:
    """Replace «1-го дежурства» so the leading digit cannot be parsed as a document id."""
    return _ORDINAL_DUTY_NUM.sub(" ", text or "")


def looks_like_duty_scoped_document_request(text: str) -> bool:
    """True when the user scoped files to a duty or rotation (вахта) period."""
    raw = text or ""
    if (
        _PREP_DUTY.search(raw)
        or _DURING_DUTY.search(raw)
        or _DEMONSTRATIVE_DUTY.search(raw)
        or _ORDINAL_DUTY_WORD.search(raw)
        or _ORDINAL_DUTY_NUM.search(raw)
        or _DUTY_ADJ_DOCS.search(raw)
    ):
        return True
    return False


def duty_blocks_bulk_document_mutation(
    text: str, *, explicit_document_ids: list[int] | None = None
) -> bool:
    """Refuse folder-wide delete/move when a duty/rotation scope is present and no explicit [id] was given.

    Chat used to treat «удали все документы за дежурство в этой папке» as wipe-the-folder because
    «все документы» matched wants_all and the duty phrase was ignored. «удали документы
    1-го дежурства» took the first digit as a document id.
    """
    if explicit_document_ids:
        return False
    return looks_like_duty_scoped_document_request(text)
