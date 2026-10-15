"""Deposit, security-payment, novation, and subrogation scope.

Do not treat «за задаток» / «за обеспечительный платеж» / «за новацию» /
«за суброгацию» as a folder wipe, and do not treat «1-го задатка» /
«100 обеспечительного платежа» / «12,5 новации» / «214-го суброгации»
as a document id.

A folder titled «Задаток», «Обеспечительный платеж», «Новация», or
«Суброгация» does not match. «без задатка» does not match.
Bare «банкротство» does not match. «инновация» and «реновация» do not
match. Bare «платеж» and «обеспечительные меры» do not match.
"""

from __future__ import annotations

import re

# Longer adjective endings first so «ыми» wins over «ым».
_ADJ_END = (
    r"(?:ыми|ими|ого|его|ому|ему|ых|их|ая|яя|ое|ее|ую|юю|ые|ие|ый|ий|ой|ым|им|ом|ем)"
)
_ADJ_WORD = rf"(?:[а-яё]{{3,}}-)?[а-яё]{{3,}}{_ADJ_END}"

# «задаток» / «задатка» / «задатку» — the «о» drops in oblique cases.
# «задача» and «задатчик» do not match.
_ZADATOCH = rf"задаточн{_ADJ_END}"
_ZADATOK_NOUN = r"задат(?:ками|ках|кам|ков|ком|ке|ки|ка|ку|ок)"
_ZADATOK = rf"(?:{_ZADATOCH}|{_ZADATOK_NOUN})"

# «обеспечительный платеж» / «обеспечительный взнос».
# «обеспечительные меры» has no «платеж» / «взнос». Bare «платеж» has no adjective.
_OBESP_ADJ = rf"обеспечительн{_ADJ_END}"
_PLATEZH = r"платеж(?:ами|ах|ам|ей|ом|у|е|и|а)?"
_VZNOS = r"взнос(?:ами|ах|ам|ов|ом|у|е|ы|а)?"
_SECURITY_PAYMENT = rf"{_OBESP_ADJ}\s+(?:{_ADJ_WORD}\s+){{0,2}}(?:{_PLATEZH}|{_VZNOS})"

# «новация». «инновация» and «реновация» fail the lookbehind (letter before «н»).
_NOVATION_ADJ = rf"новационн{_ADJ_END}"
_NOVATION_NOUN = r"новаци(?:ями|ях|ям|ею|ей|ю|и|я|й)"
_NOVATION = rf"(?:{_NOVATION_ADJ}|{_NOVATION_NOUN})"

# «суброгация» / «суброгационный» / «суброгант».
_SUBRO_ADJ = rf"суброгационн{_ADJ_END}"
_SUBRO_NOUN = r"суброгаци(?:ями|ях|ям|ею|ей|ю|и|я|й)"
_SUBROGANT = r"суброгант(?:ами|ах|ам|ов|ом|у|е|ы|а)?"
_SUBRO = rf"(?:{_SUBRO_ADJ}|{_SUBRO_NOUN}|{_SUBROGANT})"

_TARGET = rf"(?:{_ZADATOK}|{_SECURITY_PAYMENT}|{_NOVATION}|{_SUBRO})"

_DEMONSTRATIVE = (
    r"(?:этими|этих|этот|этого|этому|этой|этом|эта|эту|эти|это|"
    r"прошл\w{0,4}|текущ\w{0,4}|данн\w{0,4}|сво\w{0,4})\s+"
)

_WORD_ORDINAL = (
    r"(?:перв(?:ое|ого|ому|ым|ом|ая|ую|ой|ый|ые|ых|ыми)|втор(?:ое|ого|ому|ым|ом|ая|ую|ой|ый|ые|ых|ыми)|"
    r"трет(?:ье|ьего|ьему|ьим|ьем|ья|ью|ьей|ий|ьи|ьих|ьими)|четв[её]рт(?:ое|ого|ому|ым|ом|ая|ую|ой|ый|ые|ых|ыми))"
)

_WHOLE = r"(?<![а-яё])(?:всеми|всех|всему|всего|всей|всем|весь|вся|всё|все|всю)"

# Words that sit between the preposition and the deposit / payment / novation / subrogation.
# «папке» and «делу» are not here, so a folder titled «Задаток» does not match.
_NOUN_QUAL = (
    r"(?<![а-яё])(?:не)?(?:"
    r"постановлени(?:ями|ях|ям|ем|ею|ю|и|е|я|й)?"
    r"|отсутстви(?:ями|ях|ям|ем|ею|ю|и|е|я|й)?"
    r"|перечислени(?:ями|ях|ям|ем|ею|ю|и|е|я|й)?"
    r"|внесени(?:ями|ях|ям|ем|ею|ю|и|е|я|й)?"
    r"|удержани(?:ями|ях|ям|ем|ею|ю|и|е|я|й)?"
    r"|наличи(?:ями|ях|ям|ем|ею|ю|и|е|я|й)?"
    r"|возврат(?:ами|ах|ам|ов|ом|е|а|у|ы)?"
    r"|зачет(?:ами|ах|ам|ов|ом|е|а|у|ы)?"
    r"|бездействи(?:ями|ях|ям|ем|ею|ю|и|е|я|й)?"
    r"|действи(?:ями|ях|ям|ем|ею|ю|и|е|я|й)?"
    r"|обжаловани(?:ями|ях|ям|ем|ею|ю|и|е|я|й)?"
    r"|взыскани(?:ями|ях|ям|ем|ею|ю|и|е|я|й)?"
    r"|уведомлени(?:ями|ях|ям|ем|ею|ю|и|е|я|й)?"
    r"|предоставлени(?:ями|ях|ям|ем|ею|ю|и|е|я|й)?"
    r"|уменьшени(?:ями|ях|ям|ем|ею|ю|и|е|я|й)?"
    r"|ограничени(?:ями|ях|ям|ем|ею|ю|и|е|я|й)?"
    r"|соглашени(?:ями|ях|ям|ем|ею|ю|и|е|я|й)?"
    r"|заявлени(?:ями|ях|ям|ем|ею|ю|и|е|я|й)?"
    r"|требовани(?:ями|ях|ям|ем|ею|ю|и|е|я|й)?"
    r"|жалоб(?:ами|ах|ам|ою|ой|у|е|ы|а)?"
    r"|уплат(?:ами|ах|ам|ою|ой|у|е|ы|а)?"
    r"|оплат(?:ами|ах|ам|ою|ой|у|е|ы|а)?"
    r"|отмен(?:ами|ах|ам|ою|ой|у|е|ы|а)?"
    r"|сумм(?:ами|ах|ам|ою|ой|у|е|ы|а)?"
    r"|служб(?:ами|ах|ам|ою|ой|у|е|ы|а)?"
    r"|договор(?:ами|ах|ам|ов|ом|е|а|у|ы)?"
    r"|расчет(?:ами|ах|ам|ов|ом|е|а|у|ы)?"
    r"|размер(?:ами|ах|ам|ов|ом|е|а|у|ы)?"
    r"|запрет(?:ами|ах|ам|ов|ом|е|а|у|ы)?"
    r"|арест(?:ами|ах|ам|ов|ом|е|а|у|ы)?"
    r"|розыск(?:ами|ах|ам|ов|ом|е|а|у|и)?"
    r"|акт(?:ами|ах|ам|ов|ом|е|а|у|ы)?"
    r"|прав(?:ами|ах|ам|ою|ой|у|е|о|а)?)(?![а-яё])"
)

_QUAL = rf"(?:{_DEMONSTRATIVE}|{_WORD_ORDINAL}\s+|{_WHOLE}\s+|{_NOUN_QUAL}\s+|{_ADJ_WORD}\s+)"

_ORDINAL_SUFFIX = r"(?:го|му|ой|ую|й|е|я|ю|о|м|х|ем)"

_PREP = re.compile(
    rf"(?<![а-яё])(?:под|об|во|ко|со|от|для|перед|после|при|за|на|по|из|к|в|с|о)\s+"
    rf"(?:{_QUAL}){{0,3}}(?<!без\s)(?<![a-zа-яё]){_TARGET}(?![a-zа-яё])",
    re.IGNORECASE,
)

_DURING = re.compile(
    rf"во\s+время\s+(?:{_QUAL}){{0,3}}(?<![a-zа-яё]){_TARGET}(?![a-zа-яё])",
    re.IGNORECASE,
)

_DEMONSTRATIVE_SCOPE = re.compile(
    rf"(?:этими|этих|этот|этого|этому|этой|этом|эта|эту|эти|это|"
    r"прошлые|прошлых|прошлый|прошлого|прошлая|прошлую|прошлое|"
    r"текущие|текущих|текущий|текущего|текущая|текущую|текущее|"
    r"данные|данных|данного)\s+"
    rf"(?:{_QUAL}){{0,2}}(?<![a-zа-яё]){_TARGET}(?![a-zа-яё])",
    re.IGNORECASE,
)

_ORDINAL_WORD = re.compile(
    rf"(?:об|за|в|во|на|по|с|со|из|о|от|для|под|к|ко)\s+{_WORD_ORDINAL}\s+(?:{_QUAL}){{0,2}}(?<![a-zа-яё]){_TARGET}(?![a-zа-яё])"
    rf"|\b{_WORD_ORDINAL}\s+(?:{_QUAL}){{0,2}}(?<![a-zа-яё]){_TARGET}(?![a-zа-яё])",
    re.IGNORECASE,
)

# 1–2 digits may omit the ordinal ending («100» is an amount, below).
# 3+ digits must wear «-го» / «-й» so «документ 214» stays an id.
_ORDINAL_NUM = re.compile(
    rf"(?:\b\d{{1,2}}(?!\d)(?:-?{_ORDINAL_SUFFIX})?|\b\d{{3,6}}(?!\d)-?{_ORDINAL_SUFFIX})"
    rf"\s*(?:{_QUAL}){{0,2}}(?<![a-zа-яё]){_TARGET}(?![a-zа-яё])",
    re.IGNORECASE,
)

_SCOPED_AMOUNT = re.compile(
    rf"\b\d+(?:\s*[.,]\s*\d+)?\s*(?:{_QUAL}){{0,2}}(?<![a-zа-яё]){_TARGET}(?![a-zа-яё])",
    re.IGNORECASE,
)

_DOCS = re.compile(
    rf"(?:документ|файл)\w*\s+(?:{_QUAL}){{0,3}}(?<![a-zа-яё]){_TARGET}(?![a-zа-яё])",
    re.IGNORECASE,
)


DELETE_REFUSED_REPLY = (
    "Не удаляю файлы по виду «задаток» / «обеспечительный платеж» / "
    "«новация» / «суброгация» вроде «за задаток» / "
    "«за обеспечительный платеж» / «за новацию» / «за суброгацию» / "
    "«1-го задатка» — "
    "это не номер документа и не команда очистить всю папку. "
    "Укажите id: «удали документ 214» или «удали документы [12] [18]». "
    "Чтобы очистить открытую папку целиком, напишите «удали все документы в этой папке» "
    "без этих слов."
)

MOVE_REFUSED_REPLY = (
    "Не переношу все файлы папки по виду «задаток» / «обеспечительный платеж» / "
    "«новация» / «суброгация» вроде «за задаток» / "
    "«за обеспечительный платеж» / «за новацию» / «за суброгацию». "
    "Укажите id: «перенеси документ 214 в дело …». "
    "Чтобы перенести всю открытую папку, напишите без этих слов: "
    "«перенеси все документы в папку …»."
)


def _prepare(text: str) -> str:
    return (text or "").replace("ё", "е").replace("Ё", "Е")


def mask_deposit_ordinals(text: str) -> str:
    """Replace «1-го задатка» so the digit is not a document id.

    Amounts run first so «12,5 новации» is one token. The ordinal pass
    would otherwise keep «12» and only hide the «5».
    """
    raw = _prepare(text)
    masked = _SCOPED_AMOUNT.sub(" ", raw)
    return _ORDINAL_NUM.sub(" ", masked)


def looks_like_deposit_scoped_document_request(text: str) -> bool:
    """True when the user scoped files to a deposit, security payment, novation, or subrogation."""
    raw = _prepare(text)
    return bool(
        _PREP.search(raw)
        or _DURING.search(raw)
        or _DEMONSTRATIVE_SCOPE.search(raw)
        or _ORDINAL_WORD.search(raw)
        or _ORDINAL_NUM.search(raw)
        or _SCOPED_AMOUNT.search(raw)
        or _DOCS.search(raw)
    )


def deposit_blocks_bulk_document_mutation(
    text: str, *, explicit_document_ids: list[int] | None = None
) -> bool:
    """Refuse folder-wide delete/move when a deposit, security payment, novation, or subrogation scope is present.

    Chat treated «удали все документы за задаток в этой папке» as
    wipe-the-folder because «все документы» matched wants_all and «в этой папке»
    (or a case number, or «текущ» / «открыт») selected the case. «удали документы
    1-го задатка» took the first digit as a document id. The same path hits
    «за обеспечительный платеж», «за новацию», and «за суброгацию».
    """
    if explicit_document_ids:
        return False
    return looks_like_deposit_scoped_document_request(text)
