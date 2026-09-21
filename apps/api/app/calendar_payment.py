"""Payment-receipt / check / specification / offer chat scope.

Do not treat «за квитанцию» / «за чек» / «за спецификацию» / «за оферту»
as a folder wipe.
"""

from __future__ import annotations

import re

# Noun after a time preposition: «за квитанцию», «на чеке», «по спецификации»,
# «за оферту». Trailing (?![а-яё]) is applied at the call site so
# «человек» / «специфика» / «офертный» do not steal the noun slot.
# «чек» is short — optional endings must not consume a prefix of «человек».
_PAYMENT_NOUN = (
    r"(?:квитанц(?:иями|иям|иях|ией|ию|ии|ий|ия)"
    r"|чек(?:ами|ам|ах|ов|ом|а|у|е|и)?"
    r"|спецификаци(?:ями|ям|ях|ей|ею|ий|я|ю|и|е)"
    r"|оферт(?:ами|ам|ах|ою|ой|ы|у|е|а)?)"
)

# Optional qualifier before the noun: «кассовый чек», «публичная оферта».
# Do not reuse «судебные» as adj+docs — that must stay an unscoped wipe.
_PAYMENT_ADJ = (
    r"(?:(?:плат[её]жн(?:ый|ая|ое|ые|ого|ому|ым|ом|ую|ой|ых|ыми))"
    r"|(?:кассов(?:ый|ая|ое|ые|ого|ому|ым|ом|ую|ой|ых|ыми))"
    r"|(?:товарн(?:ый|ая|ое|ые|ого|ому|ым|ом|ую|ой|ых|ыми))"
    r"|(?:фискальн(?:ый|ая|ое|ые|ого|ому|ым|ом|ую|ой|ых|ыми))"
    r"|(?:техническ(?:ий|ая|ое|ие|ого|ому|им|ом|ую|ой|их|ими))"
    r"|(?:коммерческ(?:ий|ая|ое|ие|ого|ому|им|ом|ую|ой|их|ими))"
    r"|(?:публичн(?:ый|ая|ое|ые|ого|ому|ым|ом|ую|ой|ых|ыми)))"
)

_DEMONSTRATIVE = (
    r"(?:это|эти|этих|этими|этот|этой|этом|эта|эту|"
    r"прошл\w{0,4}|текущ\w{0,4}|данн\w{0,4}|сво\w{0,4})\s+"
)

_WORD_ORDINAL = (
    r"(?:перв(?:ое|ого|ому|ым|ом|ая|ую|ой|ый|ые|ых|ыми)|втор(?:ое|ого|ому|ым|ом|ая|ую|ой|ый|ые|ых|ыми)|"
    r"трет(?:ье|ьего|ьему|ьим|ьем|ья|ью|ьей|ий|ьи|ьих|ьими)|четв[её]рт(?:ое|ого|ому|ым|ом|ая|ую|ой|ый|ые|ых|ыми))"
)

_MODIFIER = rf"(?:{_WORD_ORDINAL}|{_PAYMENT_ADJ})"

# Wrap the demonstrative: `{_DEMONSTRATIVE}?` would make only the trailing `\s+` optional.
_PREP_PAYMENT = re.compile(
    rf"(?:за|на|в|во|по)\s+(?:{_DEMONSTRATIVE})?(?:(?<![а-яё]){_MODIFIER}\s+)?(?<![а-яё]){_PAYMENT_NOUN}(?![а-яё])",
    re.IGNORECASE,
)

_DURING_PAYMENT = re.compile(
    rf"во\s+время\s+(?:{_DEMONSTRATIVE})?(?:{_MODIFIER}\s+)?{_PAYMENT_NOUN}(?![а-яё])",
    re.IGNORECASE,
)

_DEMONSTRATIVE_PAYMENT = re.compile(
    rf"(?:эти|этих|этими|этот|этого|этому|этом|эта|эту|этой|"
    r"прошлые|прошлых|прошлый|прошлого|прошлая|прошлую|прошлое|"
    r"текущие|текущих|текущий|текущего|текущая|текущую|текущее|"
    r"данные|данных|данного)\s+"
    rf"(?:{_MODIFIER}\s+)?{_PAYMENT_NOUN}(?![а-яё])",
    re.IGNORECASE,
)

_ORDINAL_PAYMENT_WORD = re.compile(
    rf"(?:за|в|во|на|по)\s+{_WORD_ORDINAL}\s+(?:{_PAYMENT_ADJ}\s+)?{_PAYMENT_NOUN}(?![а-яё])"
    rf"|\b{_WORD_ORDINAL}\s+(?:{_PAYMENT_ADJ}\s+)?{_PAYMENT_NOUN}(?![а-яё])",
    re.IGNORECASE,
)

# «1-й квитанции», «1-го чека», «1-й спецификации», «1-й оферты».
# Full noun + trailing boundary so «1-го человека» is not a check ordinal.
_ORDINAL_PAYMENT_NUM = re.compile(
    rf"\b\d{{1,2}}(?:-?(?:го|му|ой|ую|й|е|я|ю|о|м|х|ем))?\s*{_PAYMENT_NOUN}(?![а-яё])",
    re.IGNORECASE,
)

# «документы квитанции» / «документы чека» / «файлы текущего чека» —
# genitive scope, not a folder titled «Квитанция» / «Чек».
_PAYMENT_DOCS = re.compile(
    rf"(?:документ|файл)\w*\s+(?:{_DEMONSTRATIVE})?(?:{_MODIFIER}\s+)?{_PAYMENT_NOUN}(?![а-яё])",
    re.IGNORECASE,
)

# «чековые документы» / «офертные документы».
_PAYMENT_ADJ_DOCS = re.compile(
    r"(?<![а-яё])(?:квитанционн(?:ый|ая|ое|ые|ого|ому|ым|ом|ую|ой|ых|ыми)|"
    r"чеков(?:ый|ая|ое|ые|ого|ому|ым|ом|ую|ой|ых|ыми)|"
    r"спецификационн(?:ый|ая|ое|ые|ого|ому|ым|ом|ую|ой|ых|ыми)|"
    r"офертн(?:ый|ая|ое|ые|ого|ому|ым|ом|ую|ой|ых|ыми))\s+(?:документ|файл)",
    re.IGNORECASE,
)

DELETE_REFUSED_PAYMENT = (
    "Не удаляю файлы по квитанции / чеку / спецификации / "
    "оферте вроде «за квитанцию» / «за чек» / "
    "«за спецификацию» / «за оферту» / "
    "«1-й квитанции» — это не номер документа и не команда очистить всю папку. "
    "Укажите id: «удали документ 214» или «удали документы [12] [18]». "
    "Чтобы очистить открытую папку целиком, напишите «удали все документы в этой папке» "
    "без квитанции, чека, спецификации и оферты."
)

MOVE_REFUSED_PAYMENT = (
    "Не переношу все файлы папки по квитанции / чеку / спецификации / "
    "оферте вроде «за квитанцию» / «за чек» / "
    "«за спецификацию» / «за оферту». "
    "Укажите id: «перенеси документ 214 в дело …». "
    "Чтобы перенести всю открытую папку, напишите без квитанции и чека: "
    "«перенеси все документы в папку …»."
)


def mask_payment_ordinals(text: str) -> str:
    """Replace «1-й квитанции» so the leading digit cannot be parsed as a document id."""
    return _ORDINAL_PAYMENT_NUM.sub(" ", text or "")


def looks_like_payment_scoped_document_request(text: str) -> bool:
    """True when the user scoped files to a payment receipt, check, specification, or offer."""
    raw = text or ""
    if (
        _PREP_PAYMENT.search(raw)
        or _DURING_PAYMENT.search(raw)
        or _DEMONSTRATIVE_PAYMENT.search(raw)
        or _ORDINAL_PAYMENT_WORD.search(raw)
        or _ORDINAL_PAYMENT_NUM.search(raw)
        or _PAYMENT_DOCS.search(raw)
        or _PAYMENT_ADJ_DOCS.search(raw)
    ):
        return True
    return False


def payment_blocks_bulk_document_mutation(
    text: str, *, explicit_document_ids: list[int] | None = None
) -> bool:
    """Refuse folder-wide delete/move when a payment/offer scope is present and no explicit [id] was given.

    Chat used to treat «удали все документы за квитанцию в этой папке» as wipe-the-folder because
    «все документы» matched wants_all and the receipt phrase was ignored. «удали документы
    1-й квитанции» took the first digit as a document id.
    """
    if explicit_document_ids:
        return False
    return looks_like_payment_scoped_document_request(text)
