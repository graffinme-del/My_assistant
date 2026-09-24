"""Reconciliation-act / balance / charter / order chat scope.

Do not treat «за акт сверки» / «за баланс» / «за устав» / «за приказ»
as a folder wipe, and do not treat «1-го приказа» as document id 1.
"""

from __future__ import annotations

import re

# «акт сверки» (all cases), then баланс / устав / приказ, then bare «сверка».
# «акт сверки» is first so the collocation wins over the shorter «сверки» stem.
# Trailing (?![а-яё]) is applied at the call site so «уставший», «приказание»,
# «актуальный», and «балансир» do not match.
_CORP_NOUN = (
    r"(?:акт(?:ами|ам|ах|ов|ом|у|е|ы|а)?\s+свер(?:ками|кам|ках|кою|кой|ку|ке|ки|ка|ок)"
    r"|баланс(?:ами|ам|ах|ов|ом|у|е|ы|а)?"
    r"|устав(?:ами|ам|ах|ов|ом|у|е|ы|а)?"
    r"|приказ(?:ами|ам|ах|ов|ом|у|е|ы|а)?"
    r"|свер(?:ками|кам|ках|кою|кой|ку|ке|ки|ка|ок))"
)

_DEMONSTRATIVE = (
    r"(?:этими|этих|этот|этого|этому|этой|этом|эта|эту|эти|это|"
    r"прошл\w{0,4}|текущ\w{0,4}|данн\w{0,4}|сво\w{0,4})\s+"
)

_WORD_ORDINAL = (
    r"(?:перв(?:ое|ого|ому|ым|ом|ая|ую|ой|ый|ые|ых|ыми)|втор(?:ое|ого|ому|ым|ом|ая|ую|ой|ый|ые|ых|ыми)|"
    r"трет(?:ье|ьего|ьему|ьим|ьем|ья|ью|ьей|ий|ьи|ьих|ьими)|четв[её]рт(?:ое|ого|ому|ым|ом|ая|ую|ой|ый|ые|ых|ыми))"
)

# One qualifier word: «бухгалтерский баланс», «годовой акт сверки», «итоговый приказ».
_ADJ_WORD = (
    r"[а-яё]{3,}(?:ый|ий|ой|ая|яя|ое|ее|ые|ие|ого|его|ому|ему|ым|им|ом|ем|ую|юю|ых|их|ыми|ими)"
)

_QUAL = rf"(?:{_DEMONSTRATIVE}|{_WORD_ORDINAL}\s+|{_ADJ_WORD}\s+)"

_PREP_CORP = re.compile(
    rf"(?<![а-яё])(?:за|на|в|во|по)\s+(?:{_QUAL}){{0,3}}(?<![а-яё]){_CORP_NOUN}(?![а-яё])",
    re.IGNORECASE,
)

_DURING_CORP = re.compile(
    rf"во\s+время\s+(?:{_QUAL}){{0,3}}(?<![а-яё]){_CORP_NOUN}(?![а-яё])",
    re.IGNORECASE,
)

_DEMONSTRATIVE_CORP = re.compile(
    rf"(?:этими|этих|этот|этого|этому|этой|этом|эта|эту|эти|"
    r"прошлые|прошлых|прошлый|прошлого|прошлая|прошлую|прошлое|"
    r"текущие|текущих|текущий|текущего|текущая|текущую|текущее|"
    r"данные|данных|данного)\s+"
    rf"(?:{_QUAL}){{0,2}}(?<![а-яё]){_CORP_NOUN}(?![а-яё])",
    re.IGNORECASE,
)

_ORDINAL_CORP_WORD = re.compile(
    rf"(?:за|в|во|на|по)\s+{_WORD_ORDINAL}\s+(?:{_QUAL}){{0,2}}(?<![а-яё]){_CORP_NOUN}(?![а-яё])"
    rf"|\b{_WORD_ORDINAL}\s+(?:{_QUAL}){{0,2}}(?<![а-яё]){_CORP_NOUN}(?![а-яё])",
    re.IGNORECASE,
)

# «1-го приказа», «1-й баланс», «1-го акта сверки». Two digits so ids like 214 stay ids.
_ORDINAL_CORP_NUM = re.compile(
    rf"\b\d{{1,2}}(?:-?(?:го|му|ой|ую|й|е|я|ю|о|м|х|ем))?\s*(?:{_QUAL}){{0,2}}(?<![а-яё]){_CORP_NOUN}(?![а-яё])",
    re.IGNORECASE,
)

# «документы приказа» / «документы акта сверки» — genitive scope, not a folder titled «Приказ».
_CORP_DOCS = re.compile(
    rf"(?:документ|файл)\w*\s+(?:{_QUAL}){{0,3}}(?<![а-яё]){_CORP_NOUN}(?![а-яё])",
    re.IGNORECASE,
)

# «балансовые документы» / «уставные документы» / «приказные документы».
_CORP_ADJ_DOCS = re.compile(
    r"(?<![а-яё])(?:балансов(?:ый|ая|ое|ые|ого|ому|ым|ом|ую|ой|ых|ыми)|"
    r"уставн(?:ый|ая|ое|ые|ого|ому|ым|ом|ую|ой|ых|ыми)|"
    r"приказн(?:ый|ая|ое|ые|ого|ому|ым|ом|ую|ой|ых|ыми)|"
    r"сверочн(?:ый|ая|ое|ые|ого|ому|ым|ом|ую|ой|ых|ыми))\s+(?:документ|файл)",
    re.IGNORECASE,
)

DELETE_REFUSED_CORPORATE = (
    "Не удаляю файлы по акту сверки / балансу / уставу / приказу "
    "вроде «за акт сверки» / «за баланс» / «за устав» / «за приказ» / "
    "«1-го приказа» — это не номер документа и не команда очистить всю папку. "
    "Укажите id: «удали документ 214» или «удали документы [12] [18]». "
    "Чтобы очистить открытую папку целиком, напишите «удали все документы в этой папке» "
    "без акта сверки, баланса, устава и приказа."
)

MOVE_REFUSED_CORPORATE = (
    "Не переношу все файлы папки по акту сверки / балансу / уставу / приказу "
    "вроде «за акт сверки» / «за баланс» / «за устав» / «за приказ». "
    "Укажите id: «перенеси документ 214 в дело …». "
    "Чтобы перенести всю открытую папку, напишите без приказа и баланса: "
    "«перенеси все документы в папку …»."
)


def mask_corporate_ordinals(text: str) -> str:
    """Replace «1-го приказа» so the leading digit cannot be parsed as a document id."""
    return _ORDINAL_CORP_NUM.sub(" ", text or "")


def looks_like_corporate_scoped_document_request(text: str) -> bool:
    """True when the user scoped files to a reconciliation act, balance, charter, or order."""
    raw = text or ""
    if (
        _PREP_CORP.search(raw)
        or _DURING_CORP.search(raw)
        or _DEMONSTRATIVE_CORP.search(raw)
        or _ORDINAL_CORP_WORD.search(raw)
        or _ORDINAL_CORP_NUM.search(raw)
        or _CORP_DOCS.search(raw)
        or _CORP_ADJ_DOCS.search(raw)
    ):
        return True
    return False


def corporate_blocks_bulk_document_mutation(
    text: str, *, explicit_document_ids: list[int] | None = None
) -> bool:
    """Refuse folder-wide delete/move when a reconciliation/balance/charter/order scope is present.

    Chat used to treat «удали все документы за акт сверки в этой папке» as wipe-the-folder because
    «все документы» matched wants_all and the document-type phrase was ignored. «удали документы
    1-го приказа» took the first digit as a document id.
    """
    if explicit_document_ids:
        return False
    return looks_like_corporate_scoped_document_request(text)
