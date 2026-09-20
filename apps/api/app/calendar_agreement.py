"""Agreement / receipt / invoice / waybill chat scope.

Do not treat «за соглашение» / «за расписку» / «за счёт» / «за накладную»
as a folder wipe.
"""

from __future__ import annotations

import re

# Noun after a time preposition: «за соглашение», «на расписке», «по счёту»,
# «за накладную». Trailing (?![а-яё]) is applied at the call site so
# «согласованность» / «расписание» / «счетчик» do not steal the noun slot.
_AGREEMENT_NOUN = (
    r"(?:соглашени(?:ями|ям|ях|ем|ю|я|и|й|е)"
    r"|расписк(?:ами|ам|ах|ою|ой|ок|а|у|е|и)"
    r"|сч[её]т(?:ами|ам|ах|ов|ом|а|у|е|ы)?"
    r"|накладн(?:ыми|ых|ым|ые|ого|ому|ой|ое|ая|ую|ый))"
)

# Optional qualifier before the noun: «мировое соглашение», «товарная накладная».
# Do not reuse «судебные» as adj+docs — that must stay an unscoped wipe.
_AGREEMENT_ADJ = (
    r"(?:(?:миров(?:ой|ая|ое|ые|ого|ому|ым|ом|ую|ой|ых|ыми))"
    r"|(?:предварительн(?:ый|ая|ое|ые|ого|ому|ым|ом|ую|ой|ых|ыми))"
    r"|(?:дополнительн(?:ый|ая|ое|ые|ого|ому|ым|ом|ую|ой|ых|ыми))"
    r"|(?:товарн(?:ый|ая|ое|ые|ого|ому|ым|ом|ую|ой|ых|ыми))"
    r"|(?:транспортн(?:ый|ая|ое|ые|ого|ому|ым|ом|ую|ой|ых|ыми)))"
)

_DEMONSTRATIVE = (
    r"(?:это|эти|этих|этими|этот|этой|этом|эта|эту|"
    r"прошл\w{0,4}|текущ\w{0,4}|данн\w{0,4}|сво\w{0,4})\s+"
)

_WORD_ORDINAL = (
    r"(?:перв(?:ое|ого|ому|ым|ом|ая|ую|ой|ый|ые|ых|ыми)|втор(?:ое|ого|ому|ым|ом|ая|ую|ой|ый|ые|ых|ыми)|"
    r"трет(?:ье|ьего|ьему|ьим|ьем|ья|ью|ьей|ий|ьи|ьих|ьими)|четв[её]рт(?:ое|ого|ому|ым|ом|ая|ую|ой|ый|ые|ых|ыми))"
)

_MODIFIER = rf"(?:{_WORD_ORDINAL}|{_AGREEMENT_ADJ})"

# Wrap the demonstrative: `{_DEMONSTRATIVE}?` would make only the trailing `\s+` optional.
_PREP_AGREEMENT = re.compile(
    rf"(?:за|на|в|во|по)\s+(?:{_DEMONSTRATIVE})?(?:(?<![а-яё]){_MODIFIER}\s+)?(?<![а-яё]){_AGREEMENT_NOUN}(?![а-яё])",
    re.IGNORECASE,
)

_DURING_AGREEMENT = re.compile(
    rf"во\s+время\s+(?:{_DEMONSTRATIVE})?(?:{_MODIFIER}\s+)?{_AGREEMENT_NOUN}(?![а-яё])",
    re.IGNORECASE,
)

_DEMONSTRATIVE_AGREEMENT = re.compile(
    rf"(?:эти|этих|этими|этот|этого|этом|эта|эту|этой|"
    r"прошлые|прошлых|прошлый|прошлая|прошлую|прошлое|"
    r"текущие|текущих|текущий|текущая|текущую|текущее|"
    r"данные|данных)\s+"
    rf"(?:{_MODIFIER}\s+)?{_AGREEMENT_NOUN}(?![а-яё])",
    re.IGNORECASE,
)

_ORDINAL_AGREEMENT_WORD = re.compile(
    rf"(?:за|в|во|на|по)\s+{_WORD_ORDINAL}\s+(?:{_AGREEMENT_ADJ}\s+)?{_AGREEMENT_NOUN}(?![а-яё])"
    rf"|\b{_WORD_ORDINAL}\s+(?:{_AGREEMENT_ADJ}\s+)?{_AGREEMENT_NOUN}(?![а-яё])",
    re.IGNORECASE,
)

# «1-го соглашения», «1-й расписки», «1-го счёта», «1-й накладной».
_ORDINAL_AGREEMENT_NUM = re.compile(
    r"\b\d{1,2}(?:-?(?:го|му|ой|ую|й|е|я|ю|о|м|х|ем))?\s*"
    r"(?:соглашени|расписк|сч[её]т|накладн)",
    re.IGNORECASE,
)

# «документы соглашения» / «документы расписки» — genitive scope,
# not a folder titled «Соглашение» / «Расписка».
_AGREEMENT_DOCS = re.compile(
    rf"(?:документ|файл)\w*\s+(?:{_MODIFIER}\s+)?{_AGREEMENT_NOUN}(?![а-яё])",
    re.IGNORECASE,
)

# «счётные документы» / «накладные документы».
_AGREEMENT_ADJ_DOCS = re.compile(
    r"(?<![а-яё])(?:сч[её]тн(?:ый|ая|ое|ые|ого|ому|ым|ом|ую|ой|ых|ыми)|"
    r"накладн(?:ый|ая|ое|ые|ого|ому|ым|ом|ую|ой|ых|ыми))\s+(?:документ|файл)",
    re.IGNORECASE,
)

DELETE_REFUSED_AGREEMENT = (
    "Не удаляю файлы по соглашению / расписке / счёту / "
    "накладной вроде «за соглашение» / «за расписку» / "
    "«за счёт» / «за накладную» / "
    "«1-го соглашения» — это не номер документа и не команда очистить всю папку. "
    "Укажите id: «удали документ 214» или «удали документы [12] [18]». "
    "Чтобы очистить открытую папку целиком, напишите «удали все документы в этой папке» "
    "без соглашения, расписки, счёта и накладной."
)

MOVE_REFUSED_AGREEMENT = (
    "Не переношу все файлы папки по соглашению / расписке / счёту / "
    "накладной вроде «за соглашение» / «за расписку» / "
    "«за счёт» / «за накладную». "
    "Укажите id: «перенеси документ 214 в дело …». "
    "Чтобы перенести всю открытую папку, напишите без соглашения и расписки: "
    "«перенеси все документы в папку …»."
)


def mask_agreement_ordinals(text: str) -> str:
    """Replace «1-го соглашения» so the leading digit cannot be parsed as a document id."""
    return _ORDINAL_AGREEMENT_NUM.sub(" ", text or "")


def looks_like_agreement_scoped_document_request(text: str) -> bool:
    """True when the user scoped files to an agreement, receipt, invoice, or waybill."""
    raw = text or ""
    if (
        _PREP_AGREEMENT.search(raw)
        or _DURING_AGREEMENT.search(raw)
        or _DEMONSTRATIVE_AGREEMENT.search(raw)
        or _ORDINAL_AGREEMENT_WORD.search(raw)
        or _ORDINAL_AGREEMENT_NUM.search(raw)
        or _AGREEMENT_DOCS.search(raw)
        or _AGREEMENT_ADJ_DOCS.search(raw)
    ):
        return True
    return False


def agreement_blocks_bulk_document_mutation(
    text: str, *, explicit_document_ids: list[int] | None = None
) -> bool:
    """Refuse folder-wide delete/move when an agreement/invoice scope is present and no explicit [id] was given.

    Chat used to treat «удали все документы за соглашение в этой папке» as wipe-the-folder because
    «все документы» matched wants_all and the agreement phrase was ignored. «удали документы
    1-го соглашения» took the first digit as a document id.
    """
    if explicit_document_ids:
        return False
    return looks_like_agreement_scoped_document_request(text)
