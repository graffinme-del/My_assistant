"""Calendar-season chat scope: do not treat «за лето» as a folder wipe."""

from __future__ import annotations

import re

# Nouns after a time preposition: «за лето», «за зиму», «за эту осень», «за сезон».
_SEASON_NOUN = r"(?:лето|лета|лету|зиму|зимы|зиме|весну|весны|весне|осень|осени|сезон(?:а|у|е)?)"

# Instrumental time adverbs: «летом», «зимой», «весной», «осенью».
_SEASON_ADV = r"(?:летом|зимой|весной|осенью)"

# Adjectives: «летние документы», «за зимний период».
_SEASON_ADJ = (
    r"(?:летн(?:ий|яя|ее|ие|его|ему|им|ем|ую|ей|их|ими)"
    r"|зимн(?:ий|яя|ее|ие|его|ему|им|ем|ую|ей|их|ими)"
    r"|весенн(?:ий|яя|ее|ие|его|ему|им|ем|ую|ей|их|ими)"
    r"|осенн(?:ий|яя|ее|ие|его|ему|им|ем|ую|ей|их|ими))"
)

_DEMONSTRATIVE = r"(?:это|эту|этот|этой|этом|прошл\w{0,4}|текущ\w{0,4}|данн\w{0,4})\s+"

# «за лето», «за эту зиму», «на осень», «за сезон», «в этом сезоне».
# Wrap the demonstrative: `{_DEMONSTRATIVE}?` would make only the trailing `\s+` optional.
_PREP_SEASON = re.compile(
    rf"(?:за|на|в|во)\s+(?:{_DEMONSTRATIVE})?{_SEASON_NOUN}(?![а-яё])",
    re.IGNORECASE,
)

# «этим летом», «прошлой зимой», «текущей весной».
_DEMONSTRATIVE_ADV = re.compile(
    rf"(?:этим|этой|прошлым|прошлой|текущим|текущей|данным|данной)\s+{_SEASON_ADV}(?![а-яё])",
    re.IGNORECASE,
)

# Bare time adverb: «летом», «зимой». Not bare «лето» (could be a folder title).
_BARE_ADV = re.compile(
    rf"(?<![а-яё]){_SEASON_ADV}(?![а-яё])",
    re.IGNORECASE,
)

_ADJ = re.compile(
    rf"(?<![а-яё]){_SEASON_ADJ}(?![а-яё])",
    re.IGNORECASE,
)

DELETE_REFUSED_SEASON = (
    "Не удаляю файлы по сезону вроде «за лето» / «зимой» / «летние документы» — "
    "это не номер документа и не команда очистить всю папку. "
    "Укажите id: «удали документ 214» или «удали документы [12] [18]». "
    "Чтобы очистить открытую папку целиком, напишите «удали все документы в этой папке» "
    "без сезона."
)

MOVE_REFUSED_SEASON = (
    "Не переношу все файлы папки по сезону вроде «за лето» / «зимой» / «летние документы». "
    "Укажите id: «перенеси документ 214 в дело …». "
    "Чтобы перенести всю открытую папку, напишите без сезона: "
    "«перенеси все документы в папку …»."
)


def looks_like_season_scoped_document_request(text: str) -> bool:
    """True when the user scoped files to a calendar season."""
    raw = text or ""
    if _PREP_SEASON.search(raw) or _DEMONSTRATIVE_ADV.search(raw) or _BARE_ADV.search(raw) or _ADJ.search(raw):
        return True
    return False


def season_blocks_bulk_document_mutation(
    text: str, *, explicit_document_ids: list[int] | None = None
) -> bool:
    """Refuse folder-wide delete/move when a season is present and no explicit [id] was given.

    Chat used to treat «удали все документы за лето в этой папке» as wipe-the-folder because
    «все документы» matched wants_all and the season was ignored.
    """
    if explicit_document_ids:
        return False
    return looks_like_season_scoped_document_request(text)
