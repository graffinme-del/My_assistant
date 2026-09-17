"""Claim/response/protocol chat scope: do not treat «за иск» / «за протокол» as a folder wipe."""

from __future__ import annotations

import re

# Noun after a time preposition: «за иск», «на отзыве», «по протоколу», «за исполнительный лист».
# Trailing (?![а-яё]) is applied at the call site so «искать» / «исключить» do not steal the noun slot.
_CLAIM_NOUN = (
    r"(?:иск(?:ами|ам|ах|ом|ов|а|у|е|и)?"
    r"|отзыв(?:ами|ам|ах|ом|ов|а|у|е|ы)?"
    r"|возражен(?:ие|ия|ию|ием|ии|ий|иям|иями|иях)"
    r"|протокол(?:ами|ам|ах|ом|ов|а|у|е|ы)?"
    r"|исполнительн(?:ый|ого|ому|ым|ом|ая|ую|ой|ое|ые|ых|ыми)\s+лист(?:ами|ам|ах|ом|ов|а|у|е|ы)?"
    r"|исков(?:ой|ая|ое|ые|ого|ому|ым|ом|ую|ых|ыми)\s+заявлен(?:ие|ия|ию|ием|ии|ий|иям|иями|иях))"
)

# Optional qualifier before the noun: «встречный иск», «исковой отзыв».
# Do not reuse these as adj+docs — «судебные документы» must stay an unscoped wipe.
_CLAIM_ADJ = (
    r"(?:(?:исков(?:ой|ая|ое|ые|ого|ому|ым|ом|ую|ых|ыми))"
    r"|(?:протокол(?:ьн(?:ый|ая|ое|ые|ого|ому|ым|ом|ую|ой|ых|ыми)))"
    r"|(?:встречн(?:ый|ая|ое|ые|ого|ому|ым|ом|ую|ой|ых|ыми))"
    r"|(?:исполнительн(?:ый|ого|ому|ым|ом|ая|ую|ой|ое|ые|ых|ыми)))"
)

_DEMONSTRATIVE = (
    r"(?:это|эти|этих|этими|этот|этой|этом|эта|эту|"
    r"прошл\w{0,4}|текущ\w{0,4}|данн\w{0,4}|сво\w{0,4})\s+"
)

_WORD_ORDINAL = (
    r"(?:перв(?:ое|ого|ому|ым|ом|ая|ую|ой|ый|ые|ых|ыми)|втор(?:ое|ого|ому|ым|ом|ая|ую|ой|ый|ые|ых|ыми)|"
    r"трет(?:ье|ьего|ьему|ьим|ьем|ья|ью|ьей|ий|ьи|ьих|ьими)|четв[её]рт(?:ое|ого|ому|ым|ом|ая|ую|ой|ый|ые|ых|ыми))"
)

_MODIFIER = rf"(?:{_WORD_ORDINAL}|{_CLAIM_ADJ})"

# Wrap the demonstrative: `{_DEMONSTRATIVE}?` would make only the trailing `\s+` optional.
_PREP_CLAIM = re.compile(
    rf"(?:за|на|в|во|по)\s+(?:{_DEMONSTRATIVE})?(?:(?<![а-яё]){_MODIFIER}\s+)?(?<![а-яё]){_CLAIM_NOUN}(?![а-яё])",
    re.IGNORECASE,
)

_DURING_CLAIM = re.compile(
    rf"во\s+время\s+(?:{_DEMONSTRATIVE})?(?:{_MODIFIER}\s+)?{_CLAIM_NOUN}(?![а-яё])",
    re.IGNORECASE,
)

_DEMONSTRATIVE_CLAIM = re.compile(
    rf"(?:эти|этих|этими|этот|этого|этом|эта|эту|этой|"
    r"прошлые|прошлых|прошлый|прошлая|прошлую|прошлое|"
    r"текущие|текущих|текущий|текущая|текущую|текущее|"
    r"данные|данных)\s+"
    rf"(?:{_MODIFIER}\s+)?{_CLAIM_NOUN}(?![а-яё])",
    re.IGNORECASE,
)

_ORDINAL_CLAIM_WORD = re.compile(
    rf"(?:за|в|во|на|по)\s+{_WORD_ORDINAL}\s+(?:{_CLAIM_ADJ}\s+)?{_CLAIM_NOUN}(?![а-яё])"
    rf"|\b{_WORD_ORDINAL}\s+(?:{_CLAIM_ADJ}\s+)?{_CLAIM_NOUN}(?![а-яё])",
    re.IGNORECASE,
)

# «1-го иска», «1-го отзыва», «1-го возражения», «1-го протокола», «1-го исполнительного листа».
_ORDINAL_CLAIM_NUM = re.compile(
    r"\b\d{1,2}(?:-?(?:го|му|ой|ую|й|е|я|ю|о|м|х|ем))?\s*"
    r"(?:иск|отзыв|возражен|протокол|исполнительн|исков)",
    re.IGNORECASE,
)

# «документы иска» / «документы исполнительного листа» — genitive scope,
# not a folder titled «Иск» / «Протокол».
_CLAIM_DOCS = re.compile(
    rf"(?:документ|файл)\w*\s+(?:{_MODIFIER}\s+)?{_CLAIM_NOUN}(?![а-яё])",
    re.IGNORECASE,
)

# «исковые документы» / «протокольные документы» — adj + files.
_CLAIM_ADJ_DOCS = re.compile(
    r"(?<![а-яё])(?:исков(?:ой|ая|ое|ые|ого|ому|ым|ом|ую|ых|ыми)|"
    r"протокол(?:ьн(?:ый|ая|ое|ые|ого|ому|ым|ом|ую|ой|ых|ыми)))\s+(?:документ|файл)",
    re.IGNORECASE,
)

DELETE_REFUSED_CLAIM = (
    "Не удаляю файлы по иску / отзыву / возражению / протоколу / "
    "исполнительному листу вроде «за иск» / «за отзыв» / "
    "«за возражение» / «за протокол» / «за исполнительный лист» / "
    "«1-го иска» — это не номер документа и не команда очистить всю папку. "
    "Укажите id: «удали документ 214» или «удали документы [12] [18]». "
    "Чтобы очистить открытую папку целиком, напишите «удали все документы в этой папке» "
    "без иска, отзыва, возражения, протокола и исполнительного листа."
)

MOVE_REFUSED_CLAIM = (
    "Не переношу все файлы папки по иску / отзыву / возражению / протоколу / "
    "исполнительному листу вроде «за иск» / «за отзыв» / "
    "«за возражение» / «за протокол» / «за исполнительный лист». "
    "Укажите id: «перенеси документ 214 в дело …». "
    "Чтобы перенести всю открытую папку, напишите без иска и протокола: "
    "«перенеси все документы в папку …»."
)


def mask_claim_ordinals(text: str) -> str:
    """Replace «1-го иска» so the leading digit cannot be parsed as a document id."""
    return _ORDINAL_CLAIM_NUM.sub(" ", text or "")


def looks_like_claim_scoped_document_request(text: str) -> bool:
    """True when the user scoped files to a claim, response, objection, protocol, or writ."""
    raw = text or ""
    if (
        _PREP_CLAIM.search(raw)
        or _DURING_CLAIM.search(raw)
        or _DEMONSTRATIVE_CLAIM.search(raw)
        or _ORDINAL_CLAIM_WORD.search(raw)
        or _ORDINAL_CLAIM_NUM.search(raw)
        or _CLAIM_DOCS.search(raw)
        or _CLAIM_ADJ_DOCS.search(raw)
    ):
        return True
    return False


def claim_blocks_bulk_document_mutation(
    text: str, *, explicit_document_ids: list[int] | None = None
) -> bool:
    """Refuse folder-wide delete/move when a claim/protocol scope is present and no explicit [id] was given.

    Chat used to treat «удали все документы за иск в этой папке» as wipe-the-folder because
    «все документы» matched wants_all and the claim phrase was ignored. «удали документы
    1-го иска» took the first digit as a document id.
    """
    if explicit_document_ids:
        return False
    return looks_like_claim_scoped_document_request(text)
