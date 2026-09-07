"""Leave/time-off chat scope: do not treat «за отпуск» as a folder wipe."""

from __future__ import annotations

import re

# Nouns after a time preposition: «за отпуск», «в отпуске», «во время отпуска».
_LEAVE_NOUN = (
    r"(?:отпуск(?:а|у|ом|е|ов|ам|ами|ах)?)"
)

# Adjectives: «отпускные документы».
_LEAVE_ADJ = (
    r"(?:отпускн(?:ой|ая|ое|ые|ого|ому|ым|ом|ую|ой|ых|ыми))"
)

_DEMONSTRATIVE = r"(?:это|эти|этих|этими|этот|этой|этом|прошл\w{0,4}|текущ\w{0,4}|данн\w{0,4}|сво\w{0,4})\s+"

# «за отпуск», «за этот отпуск», «в отпуске», «на отпуске».
# Wrap the demonstrative: `{_DEMONSTRATIVE}?` would make only the trailing `\s+` optional.
_PREP_LEAVE = re.compile(
    rf"(?:за|на|в|во)\s+(?:{_DEMONSTRATIVE})?{_LEAVE_NOUN}(?![а-яё])",
    re.IGNORECASE,
)

# «во время отпуска».
_DURING_LEAVE = re.compile(
    rf"во\s+время\s+(?:{_DEMONSTRATIVE})?{_LEAVE_NOUN}(?![а-яё])",
    re.IGNORECASE,
)

# «этот отпуск», «прошлые отпуска» without a preposition.
_DEMONSTRATIVE_NOUN = re.compile(
    rf"(?:эти|этих|этими|этот|этого|этом|прошлые|прошлых|прошлый|текущие|текущих|текущий|данные|данных)\s+{_LEAVE_NOUN}(?![а-яё])",
    re.IGNORECASE,
)

_ADJ = re.compile(
    rf"(?<![а-яё]){_LEAVE_ADJ}(?![а-яё])",
    re.IGNORECASE,
)

DELETE_REFUSED_LEAVE = (
    "Не удаляю файлы по отпуску вроде «за отпуск» / «в отпуске» / "
    "«отпускные документы» — это не номер документа и не команда очистить всю папку. "
    "Укажите id: «удали документ 214» или «удали документы [12] [18]». "
    "Чтобы очистить открытую папку целиком, напишите «удали все документы в этой папке» "
    "без отпуска."
)

MOVE_REFUSED_LEAVE = (
    "Не переношу все файлы папки по отпуску вроде «за отпуск» / "
    "«в отпуске» / «отпускные документы». "
    "Укажите id: «перенеси документ 214 в дело …». "
    "Чтобы перенести всю открытую папку, напишите без отпуска: "
    "«перенеси все документы в папку …»."
)


def looks_like_leave_scoped_document_request(text: str) -> bool:
    """True when the user scoped files to leave / time-off."""
    raw = text or ""
    if (
        _PREP_LEAVE.search(raw)
        or _DURING_LEAVE.search(raw)
        or _DEMONSTRATIVE_NOUN.search(raw)
        or _ADJ.search(raw)
    ):
        return True
    return False


def leave_blocks_bulk_document_mutation(
    text: str, *, explicit_document_ids: list[int] | None = None
) -> bool:
    """Refuse folder-wide delete/move when a leave/time-off scope is present and no explicit [id] was given.

    Chat used to treat «удали все документы за отпуск в этой папке» as wipe-the-folder because
    «все документы» matched wants_all and the leave phrase was ignored.
    """
    if explicit_document_ids:
        return False
    return looks_like_leave_scoped_document_request(text)
