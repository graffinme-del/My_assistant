"""Court-act chat scope: do not treat «за ходатайство» / «за определение» as a folder wipe."""

from __future__ import annotations

import re

# Noun after a time preposition: «за ходатайство», «на определении», «по постановлению».
# Trailing (?![а-яё]) is applied at the call site so «решенный» does not steal the noun slot.
_ACT_NOUN = (
    r"(?:ходатайств(?:о|а|у|ом|е|ам|ами|ах)?"
    r"|определен(?:ие|ия|ию|ием|ии|ий|иям|иями|иях)"
    r"|решен(?:ие|ия|ию|ием|ии|ий|иям|иями|иях)"
    r"|постановлен(?:ие|ия|ию|ием|ии|ий|иям|иями|иях))"
)

# Optional qualifier before the noun: «судебное решение», «частное определение».
# Do not reuse these as adj+docs — «судебные документы» must stay an unscoped wipe.
_ACT_ADJ = (
    r"(?:(?:ходатайственн(?:ый|ая|ое|ые|ого|ому|ым|ом|ую|ой|ых|ыми))"
    r"|(?:судебн(?:ый|ая|ое|ые|ого|ому|ым|ом|ую|ой|ых|ыми))"
    r"|(?:частн(?:ое|ого|ому|ым|ом|ая|ую|ой|ый|ые|ых|ыми)))"
)

_DEMONSTRATIVE = (
    r"(?:это|эти|этих|этими|этот|этой|этом|эта|эту|"
    r"прошл\w{0,4}|текущ\w{0,4}|данн\w{0,4}|сво\w{0,4})\s+"
)

_WORD_ORDINAL = (
    r"(?:перв(?:ое|ого|ому|ым|ом|ая|ую|ой|ый|ые|ых|ыми)|втор(?:ое|ого|ому|ым|ом|ая|ую|ой|ый|ые|ых|ыми)|"
    r"трет(?:ье|ьего|ьему|ьим|ьем|ья|ью|ьей|ий|ьи|ьих|ьими)|четв[её]рт(?:ое|ого|ому|ым|ом|ая|ую|ой|ый|ые|ых|ыми))"
)

_MODIFIER = rf"(?:{_WORD_ORDINAL}|{_ACT_ADJ})"

# Wrap the demonstrative: `{_DEMONSTRATIVE}?` would make only the trailing `\s+` optional.
_PREP_ACT = re.compile(
    rf"(?:за|на|в|во|по)\s+(?:{_DEMONSTRATIVE})?(?:(?<![а-яё]){_MODIFIER}\s+)?(?<![а-яё]){_ACT_NOUN}(?![а-яё])",
    re.IGNORECASE,
)

_DURING_ACT = re.compile(
    rf"во\s+время\s+(?:{_DEMONSTRATIVE})?(?:{_MODIFIER}\s+)?{_ACT_NOUN}(?![а-яё])",
    re.IGNORECASE,
)

_DEMONSTRATIVE_ACT = re.compile(
    rf"(?:эти|этих|этими|этот|этого|этом|эта|эту|этой|"
    r"прошлые|прошлых|прошлый|прошлая|прошлую|прошлое|"
    r"текущие|текущих|текущий|текущая|текущую|текущее|"
    r"данные|данных)\s+"
    rf"(?:{_MODIFIER}\s+)?{_ACT_NOUN}(?![а-яё])",
    re.IGNORECASE,
)

_ORDINAL_ACT_WORD = re.compile(
    rf"(?:за|в|во|на|по)\s+{_WORD_ORDINAL}\s+(?:{_ACT_ADJ}\s+)?{_ACT_NOUN}(?![а-яё])"
    rf"|\b{_WORD_ORDINAL}\s+(?:{_ACT_ADJ}\s+)?{_ACT_NOUN}(?![а-яё])",
    re.IGNORECASE,
)

# «1-го ходатайства», «1-го определения», «1-го решения», «1-го постановления» — not a document id.
_ORDINAL_ACT_NUM = re.compile(
    r"\b\d{1,2}(?:-?(?:го|му|ой|ую|й|е|я|ю|о|м|х|ем))?\s*"
    r"(?:ходатайств|определен|решен|постановлен)",
    re.IGNORECASE,
)

# «документы ходатайства» / «документы судебного решения» — genitive scope,
# not a folder titled «Ходатайство».
_ACT_DOCS = re.compile(
    rf"(?:документ|файл)\w*\s+(?:{_MODIFIER}\s+)?{_ACT_NOUN}(?![а-яё])",
    re.IGNORECASE,
)

# «ходатайственные документы» — adj + files. Not «судебные документы».
_ACT_ADJ_DOCS = re.compile(
    r"(?<![а-яё])ходатайственн(?:ый|ая|ое|ые|ого|ому|ым|ом|ую|ой|ых|ыми)\s+(?:документ|файл)",
    re.IGNORECASE,
)

DELETE_REFUSED_ACT = (
    "Не удаляю файлы по судебному акту вроде «за ходатайство» / "
    "«за определение» / «за решение» / «за постановление» / "
    "«1-го ходатайства» — это не номер документа и не команда очистить всю папку. "
    "Укажите id: «удали документ 214» или «удали документы [12] [18]». "
    "Чтобы очистить открытую папку целиком, напишите «удали все документы в этой папке» "
    "без ходатайства, определения, решения и постановления."
)

MOVE_REFUSED_ACT = (
    "Не переношу все файлы папки по судебному акту вроде "
    "«за ходатайство» / «за определение» / «за решение» / «за постановление». "
    "Укажите id: «перенеси документ 214 в дело …». "
    "Чтобы перенести всю открытую папку, напишите без судебного акта: "
    "«перенеси все документы в папку …»."
)


def mask_act_ordinals(text: str) -> str:
    """Replace «1-го ходатайства» so the leading digit cannot be parsed as a document id."""
    return _ORDINAL_ACT_NUM.sub(" ", text or "")


def looks_like_act_scoped_document_request(text: str) -> bool:
    """True when the user scoped files to a motion, ruling, decision, or order."""
    raw = text or ""
    if (
        _PREP_ACT.search(raw)
        or _DURING_ACT.search(raw)
        or _DEMONSTRATIVE_ACT.search(raw)
        or _ORDINAL_ACT_WORD.search(raw)
        or _ORDINAL_ACT_NUM.search(raw)
        or _ACT_DOCS.search(raw)
        or _ACT_ADJ_DOCS.search(raw)
    ):
        return True
    return False


def act_blocks_bulk_document_mutation(
    text: str, *, explicit_document_ids: list[int] | None = None
) -> bool:
    """Refuse folder-wide delete/move when a court-act scope is present and no explicit [id] was given.

    Chat used to treat «удали все документы за ходатайство в этой папке» as wipe-the-folder because
    «все документы» matched wants_all and the act phrase was ignored. «удали документы
    1-го ходатайства» took the first digit as a document id.
    """
    if explicit_document_ids:
        return False
    return looks_like_act_scoped_document_request(text)
