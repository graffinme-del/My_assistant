"""Contract / power-of-attorney / pre-trial claim / certificate chat scope.

Do not treat «за договор» / «за доверенность» / «за претензию» / «за справку»
as a folder wipe.
"""

from __future__ import annotations

import re

# Noun after a time preposition: «за договор», «на доверенности», «по претензии»,
# «за справку». Trailing (?![а-яё]) is applied at the call site so
# «договорённость» / «претендент» / «справочник» do not steal the noun slot.
_CONTRACT_NOUN = (
    r"(?:договор(?:ами|ам|ах|ов|ом|а|у|е|ы)?"
    r"|доверенност(?:ями|ям|ях|ью|ей|и|ь)"
    r"|претензи(?:ями|ям|ях|ею|ей|я|ю|и|й)"
    r"|справ(?:ками|кам|ках|кою|кой|ка|ку|ке|ки|ок))"
)

# Optional qualifier before the noun: «трудовой договор», «нотариальная доверенность».
# Do not reuse «судебные» as adj+docs — that must stay an unscoped wipe.
_CONTRACT_ADJ = (
    r"(?:(?:трудов(?:ой|ая|ое|ые|ого|ому|ым|ом|ую|ых|ыми))"
    r"|(?:предварительн(?:ый|ая|ое|ые|ого|ому|ым|ом|ую|ой|ых|ыми))"
    r"|(?:агентск(?:ий|ая|ое|ие|ого|ому|им|ом|ую|ой|их|ими))"
    r"|(?:нотариальн(?:ый|ая|ое|ые|ого|ому|ым|ом|ую|ой|ых|ыми))"
    r"|(?:досудебн(?:ый|ая|ое|ые|ого|ому|ым|ом|ую|ой|ых|ыми))"
    r"|(?:генеральн(?:ый|ая|ое|ые|ого|ому|ым|ом|ую|ой|ых|ыми))"
    r"|(?:договорн(?:ый|ая|ое|ые|ого|ому|ым|ом|ую|ой|ых|ыми))"
    r"|(?:претензионн(?:ый|ая|ое|ые|ого|ому|ым|ом|ую|ой|ых|ыми))"
    r"|(?:справочн(?:ый|ая|ое|ые|ого|ому|ым|ом|ую|ой|ых|ыми)))"
)

_DEMONSTRATIVE = (
    r"(?:это|эти|этих|этими|этот|этой|этом|эта|эту|"
    r"прошл\w{0,4}|текущ\w{0,4}|данн\w{0,4}|сво\w{0,4})\s+"
)

_WORD_ORDINAL = (
    r"(?:перв(?:ое|ого|ому|ым|ом|ая|ую|ой|ый|ые|ых|ыми)|втор(?:ое|ого|ому|ым|ом|ая|ую|ой|ый|ые|ых|ыми)|"
    r"трет(?:ье|ьего|ьему|ьим|ьем|ья|ью|ьей|ий|ьи|ьих|ьими)|четв[её]рт(?:ое|ого|ому|ым|ом|ая|ую|ой|ый|ые|ых|ыми))"
)

_MODIFIER = rf"(?:{_WORD_ORDINAL}|{_CONTRACT_ADJ})"

# Wrap the demonstrative: `{_DEMONSTRATIVE}?` would make only the trailing `\s+` optional.
_PREP_CONTRACT = re.compile(
    rf"(?:за|на|в|во|по)\s+(?:{_DEMONSTRATIVE})?(?:(?<![а-яё]){_MODIFIER}\s+)?(?<![а-яё]){_CONTRACT_NOUN}(?![а-яё])",
    re.IGNORECASE,
)

_DURING_CONTRACT = re.compile(
    rf"во\s+время\s+(?:{_DEMONSTRATIVE})?(?:{_MODIFIER}\s+)?{_CONTRACT_NOUN}(?![а-яё])",
    re.IGNORECASE,
)

_DEMONSTRATIVE_CONTRACT = re.compile(
    rf"(?:эти|этих|этими|этот|этого|этом|эта|эту|этой|"
    r"прошлые|прошлых|прошлый|прошлая|прошлую|прошлое|"
    r"текущие|текущих|текущий|текущая|текущую|текущее|"
    r"данные|данных)\s+"
    rf"(?:{_MODIFIER}\s+)?{_CONTRACT_NOUN}(?![а-яё])",
    re.IGNORECASE,
)

_ORDINAL_CONTRACT_WORD = re.compile(
    rf"(?:за|в|во|на|по)\s+{_WORD_ORDINAL}\s+(?:{_CONTRACT_ADJ}\s+)?{_CONTRACT_NOUN}(?![а-яё])"
    rf"|\b{_WORD_ORDINAL}\s+(?:{_CONTRACT_ADJ}\s+)?{_CONTRACT_NOUN}(?![а-яё])",
    re.IGNORECASE,
)

# «1-го договора», «1-й доверенности», «1-й претензии», «1-й справки».
_ORDINAL_CONTRACT_NUM = re.compile(
    r"\b\d{1,2}(?:-?(?:го|му|ой|ую|й|е|я|ю|о|м|х|ем))?\s*"
    r"(?:договор|доверенност|претензи|справ(?:к|очн))",
    re.IGNORECASE,
)

# «документы договора» / «документы доверенности» — genitive scope,
# not a folder titled «Договор» / «Доверенность».
_CONTRACT_DOCS = re.compile(
    rf"(?:документ|файл)\w*\s+(?:{_MODIFIER}\s+)?{_CONTRACT_NOUN}(?![а-яё])",
    re.IGNORECASE,
)

# «договорные документы» / «претензионные документы» / «справочные документы».
_CONTRACT_ADJ_DOCS = re.compile(
    r"(?<![а-яё])(?:договорн(?:ый|ая|ое|ые|ого|ому|ым|ом|ую|ой|ых|ыми)|"
    r"претензионн(?:ый|ая|ое|ые|ого|ому|ым|ом|ую|ой|ых|ыми)|"
    r"справочн(?:ый|ая|ое|ые|ого|ому|ым|ом|ую|ой|ых|ыми))\s+(?:документ|файл)",
    re.IGNORECASE,
)

DELETE_REFUSED_CONTRACT = (
    "Не удаляю файлы по договору / доверенности / претензии / "
    "справке вроде «за договор» / «за доверенность» / "
    "«за претензию» / «за справку» / "
    "«1-го договора» — это не номер документа и не команда очистить всю папку. "
    "Укажите id: «удали документ 214» или «удали документы [12] [18]». "
    "Чтобы очистить открытую папку целиком, напишите «удали все документы в этой папке» "
    "без договора, доверенности, претензии и справки."
)

MOVE_REFUSED_CONTRACT = (
    "Не переношу все файлы папки по договору / доверенности / претензии / "
    "справке вроде «за договор» / «за доверенность» / "
    "«за претензию» / «за справку». "
    "Укажите id: «перенеси документ 214 в дело …». "
    "Чтобы перенести всю открытую папку, напишите без договора и доверенности: "
    "«перенеси все документы в папку …»."
)


def mask_contract_ordinals(text: str) -> str:
    """Replace «1-го договора» so the leading digit cannot be parsed as a document id."""
    return _ORDINAL_CONTRACT_NUM.sub(" ", text or "")


def looks_like_contract_scoped_document_request(text: str) -> bool:
    """True when the user scoped files to a contract, power of attorney, pre-trial claim, or certificate."""
    raw = text or ""
    if (
        _PREP_CONTRACT.search(raw)
        or _DURING_CONTRACT.search(raw)
        or _DEMONSTRATIVE_CONTRACT.search(raw)
        or _ORDINAL_CONTRACT_WORD.search(raw)
        or _ORDINAL_CONTRACT_NUM.search(raw)
        or _CONTRACT_DOCS.search(raw)
        or _CONTRACT_ADJ_DOCS.search(raw)
    ):
        return True
    return False


def contract_blocks_bulk_document_mutation(
    text: str, *, explicit_document_ids: list[int] | None = None
) -> bool:
    """Refuse folder-wide delete/move when a contract/certificate scope is present and no explicit [id] was given.

    Chat used to treat «удали все документы за договор в этой папке» as wipe-the-folder because
    «все документы» matched wants_all and the contract phrase was ignored. «удали документы
    1-го договора» took the first digit as a document id.
    """
    if explicit_document_ids:
        return False
    return looks_like_contract_scoped_document_request(text)
