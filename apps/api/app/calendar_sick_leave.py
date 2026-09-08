"""Sick-leave / maternity chat scope: do not treat «за больничный» / «в декрете» as a folder wipe."""

from __future__ import annotations

import re

# Nouns after a time preposition: «за больничный», «на больничном».
_SICK_NOUN = (
    r"(?:больничн(?:ый|ая|ое|ые|ого|ому|ым|ом|ую|ой|ых|ыми))"
)

# Maternity as leave, not a legal «декрет» (decree): «в декрете», «за декрет».
_MATERNITY_NOUN = (
    r"(?:декрет(?:а|у|ом|е|ов|ам|ами|ах)?)"
)

# Adjectives: «декретные документы», «декретный отпуск».
# «больничный» is the same stem as the noun — do not match it as a bare adjective
# (that would fire on a folder titled «Больничный»).
_MATERNITY_ADJ = (
    r"(?:декретн(?:ый|ая|ое|ые|ого|ому|ым|ом|ую|ой|ых|ыми))"
)

_DEMONSTRATIVE = r"(?:это|эти|этих|этими|этот|этой|этом|прошл\w{0,4}|текущ\w{0,4}|данн\w{0,4}|сво\w{0,4})\s+"

# Wrap the demonstrative: `{_DEMONSTRATIVE}?` would make only the trailing `\s+` optional.
_PREP_SICK = re.compile(
    rf"(?:за|на|в|во)\s+(?:{_DEMONSTRATIVE})?{_SICK_NOUN}(?![а-яё])",
    re.IGNORECASE,
)

_PREP_MATERNITY = re.compile(
    rf"(?:за|на|в|во)\s+(?:{_DEMONSTRATIVE})?{_MATERNITY_NOUN}(?![а-яё])",
    re.IGNORECASE,
)

_DURING_SICK = re.compile(
    rf"во\s+время\s+(?:{_DEMONSTRATIVE})?{_SICK_NOUN}(?![а-яё])",
    re.IGNORECASE,
)

_DURING_MATERNITY = re.compile(
    rf"во\s+время\s+(?:{_DEMONSTRATIVE})?{_MATERNITY_NOUN}(?![а-яё])",
    re.IGNORECASE,
)

_DEMONSTRATIVE_SICK = re.compile(
    rf"(?:эти|этих|этими|этот|этого|этом|прошлые|прошлых|прошлый|текущие|текущих|текущий|данные|данных)\s+{_SICK_NOUN}(?![а-яё])",
    re.IGNORECASE,
)

_DEMONSTRATIVE_MATERNITY = re.compile(
    rf"(?:эти|этих|этими|этот|этого|этом|прошлые|прошлых|прошлый|текущие|текущих|текущий|данные|данных)\s+{_MATERNITY_NOUN}(?![а-яё])",
    re.IGNORECASE,
)

# «больничные документы» / «документы больничные» — collocation, not a folder title.
_SICK_ADJ_DOCS = re.compile(
    rf"(?:{_SICK_NOUN}\s+(?:документ|файл)|(?:документ|файл)\w*\s+{_SICK_NOUN})(?![а-яё])",
    re.IGNORECASE,
)

_MATERNITY_ADJ_RE = re.compile(
    rf"(?<![а-яё]){_MATERNITY_ADJ}(?![а-яё])",
    re.IGNORECASE,
)

DELETE_REFUSED_SICK_LEAVE = (
    "Не удаляю файлы по больничному или декрету вроде «за больничный» / «на больничном» / "
    "«в декрете» / «декретные документы» — это не номер документа и не команда очистить всю папку. "
    "Укажите id: «удали документ 214» или «удали документы [12] [18]». "
    "Чтобы очистить открытую папку целиком, напишите «удали все документы в этой папке» "
    "без больничного и декрета."
)

MOVE_REFUSED_SICK_LEAVE = (
    "Не переношу все файлы папки по больничному или декрету вроде «за больничный» / "
    "«на больничном» / «в декрете» / «декретные документы». "
    "Укажите id: «перенеси документ 214 в дело …». "
    "Чтобы перенести всю открытую папку, напишите без больничного и декрета: "
    "«перенеси все документы в папку …»."
)


def looks_like_sick_leave_scoped_document_request(text: str) -> bool:
    """True when the user scoped files to sick leave or maternity leave."""
    raw = text or ""
    if (
        _PREP_SICK.search(raw)
        or _PREP_MATERNITY.search(raw)
        or _DURING_SICK.search(raw)
        or _DURING_MATERNITY.search(raw)
        or _DEMONSTRATIVE_SICK.search(raw)
        or _DEMONSTRATIVE_MATERNITY.search(raw)
        or _SICK_ADJ_DOCS.search(raw)
        or _MATERNITY_ADJ_RE.search(raw)
    ):
        return True
    return False


def sick_leave_blocks_bulk_document_mutation(
    text: str, *, explicit_document_ids: list[int] | None = None
) -> bool:
    """Refuse folder-wide delete/move when a sick-leave/maternity scope is present and no explicit [id] was given.

    Chat used to treat «удали все документы за больничный в этой папке» as wipe-the-folder because
    «все документы» matched wants_all and the sick-leave phrase was ignored.
    """
    if explicit_document_ids:
        return False
    return looks_like_sick_leave_scoped_document_request(text)
