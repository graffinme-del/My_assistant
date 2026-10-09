"""Harm / duty / pledge / indexation / interest / recovery scope.

Do not treat «за вред» / «за пошлину» / «за госпошлину» / «за залог» /
«за индексацию» / «за проценты» / «за взыскание» as a folder wipe, and do not
treat «1-го вреда» / «1-й пошлины» / «1-го залога» / «1-го процента» /
«1-го взыскания» as document id 1.

A folder titled «Вред», «Пошлина», «Залог», «Индексация», «Проценты», or
«Взыскание» does not match. «без вреда» / «без пошлины» / «без процентов» /
«без взыскания» do not match.
«Убытки» / «компенсация» / «полис» / «штраф» remain separate guards.
«Вредить», «заложить», «индексировать», «взыскать», and «взыскатель» do not match.
"""

from __future__ import annotations

import re

# «возмещение вреда». Bare «возмещение» is not matched.
_HARM_PREFIX = r"(?:возмещени(?:ями|ях|ям|ем|ею|ю|и|е|я)\s+)?"
# «вред». «вредить» / «навредить» / «вредный» do not match.
_HARM = rf"{_HARM_PREFIX}вред(?:ами|ах|ам|ов|ом|а|у|е|ы)?"

# «пошлина» / «госпошлина». «пошли» (imperative) does not contain this stem.
_DUTY = r"(?:гос)?пошлин(?:ами|ах|ам|ою|ой|у|е|ы|а)?"

# «залог». «заложить» / «залогодатель» do not match.
_PLEDGE = r"залог(?:ами|ах|ам|ов|ом|и|а|у|е)?"

# «индексация». «индексировать» / bare «индекс» do not match.
_INDEX = r"индексаци(?:ями|ях|ям|ею|ей|ю|и|я|й)"

# «процент». «процентный» does not match the noun.
_INTEREST = r"процент(?:ами|ах|ам|ов|ом|ы|а|у|е)?"

# «обращение взыскания». Bare «обращение» is not matched.
# «взыскать» / «взыскатель» do not match.
_RECOVERY_PREFIX = r"(?:обращени(?:ями|ях|ям|ем|ею|ю|й|и|е|я)\s+)?"
_RECOVERY = rf"{_RECOVERY_PREFIX}взыскани(?:ями|ях|ям|ем|ею|ю|й|и|е|я)"

_TARGET = rf"(?:{_RECOVERY}|{_INDEX}|{_HARM}|{_DUTY}|{_PLEDGE}|{_INTEREST})"

_HARM_ADJ = r"вредн(?:ыми|ый|ая|ое|ые|ого|ому|ым|ом|ую|ой|ых)"
_DUTY_ADJ = r"(?:гос)?пошлинн(?:ыми|ый|ая|ое|ые|ого|ому|ым|ом|ую|ой|ых)"
_PLEDGE_ADJ = r"залогов(?:ыми|ый|ая|ое|ые|ого|ому|ым|ом|ую|ой|ых)"
_INDEX_ADJ = r"индексационн(?:ыми|ый|ая|ое|ые|ого|ому|ым|ом|ую|ой|ых)"
_INTEREST_ADJ = r"процентн(?:ыми|ый|ая|ое|ые|ого|ому|ым|ом|ую|ой|ых)"
_ADJ = rf"(?:{_HARM_ADJ}|{_DUTY_ADJ}|{_PLEDGE_ADJ}|{_INDEX_ADJ}|{_INTEREST_ADJ})"

_DEMONSTRATIVE = (
    r"(?:этими|этих|этот|этого|этому|этой|этом|эта|эту|эти|это|"
    r"прошл\w{0,4}|текущ\w{0,4}|данн\w{0,4}|сво\w{0,4})\s+"
)

_WORD_ORDINAL = (
    r"(?:перв(?:ое|ого|ому|ым|ом|ая|ую|ой|ый|ые|ых|ыми)|втор(?:ое|ого|ому|ым|ом|ая|ую|ой|ый|ые|ых|ыми)|"
    r"трет(?:ье|ьего|ьему|ьим|ьем|ья|ью|ьей|ий|ьи|ьих|ьими)|четв[её]рт(?:ое|ого|ому|ым|ом|ая|ую|ой|ый|ые|ых|ыми))"
)

# One qualifier word: «моральный вред», «государственную пошлину».
_ADJ_WORD = (
    r"(?:[а-яё]{3,}-)?[а-яё]{3,}(?:ыми|ими|ый|ий|ой|ая|яя|ое|ее|ые|ие|ого|его|ому|ему|ым|им|ом|ем|ую|юю|ых|их)"
)

# «весь вред», «все проценты». Not an adjective, so _ADJ_WORD does not see it.
_WHOLE = r"(?<![а-яё])(?:всеми|всех|всему|всего|всей|всем|весь|вся|всё|все|всю)"

# «сумма процентов», «размер вреда», «уплата госпошлины», «начисление процентов».
# These are nouns, so the adjective qualifier does not see them.
_AMOUNT_WORD = (
    r"(?<![а-яё])(?:сумм(?:ами|ах|ам|ою|ой|у|е|ы|а)?"
    r"|размер(?:ами|ах|ам|ов|ом|а|у|е|ы)?"
    r"|(?:не)?уплат(?:ами|ах|ам|ою|ой|у|е|ы|а)?"
    r"|начислени(?:ями|ях|ям|ем|ею|ю|и|е|я))"
)

_QUAL = rf"(?:{_DEMONSTRATIVE}|{_WORD_ORDINAL}\s+|{_WHOLE}\s+|{_AMOUNT_WORD}\s+|{_ADJ_WORD}\s+)"

_ORDINAL_SUFFIX = r"(?:го|му|ой|ую|й|е|я|ю|о|м|х|ем)"

_PREP = re.compile(
    rf"(?<![а-яё])(?:под|об|во|со|за|на|по|из|в|с|о)\s+(?:{_QUAL}){{0,3}}(?<![а-яё]){_TARGET}(?![а-яё])",
    re.IGNORECASE,
)

_DURING = re.compile(
    rf"во\s+время\s+(?:{_QUAL}){{0,3}}(?<![а-яё]){_TARGET}(?![а-яё])",
    re.IGNORECASE,
)

_DEMONSTRATIVE_SCOPE = re.compile(
    rf"(?:этими|этих|этот|этого|этому|этой|этом|эта|эту|эти|"
    r"прошлые|прошлых|прошлый|прошлого|прошлая|прошлую|прошлое|"
    r"текущие|текущих|текущий|текущего|текущая|текущую|текущее|"
    r"данные|данных|данного)\s+"
    rf"(?:{_QUAL}){{0,2}}(?<![а-яё]){_TARGET}(?![а-яё])",
    re.IGNORECASE,
)

_ORDINAL_WORD = re.compile(
    rf"(?:об|за|в|во|на|по|с|со|из|о|под)\s+{_WORD_ORDINAL}\s+(?:{_QUAL}){{0,2}}(?<![а-яё]){_TARGET}(?![а-яё])"
    rf"|\b{_WORD_ORDINAL}\s+(?:{_QUAL}){{0,2}}(?<![а-яё]){_TARGET}(?![а-яё])",
    re.IGNORECASE,
)

# «1-го вреда», «1-й пошлины», «1-го процента».
# Two digits so ids like 214 stay ids. (?!\d) so a longer number is not sliced.
_ORDINAL_NUM = re.compile(
    rf"\b\d{{1,2}}(?!\d)(?:-?{_ORDINAL_SUFFIX})?\s*(?:{_QUAL}){{0,2}}(?<![а-яё]){_TARGET}(?![а-яё])",
    re.IGNORECASE,
)

# «документы вреда» — genitive scope, not a folder titled «Вред».
_DOCS = re.compile(
    rf"(?:документ|файл)\w*\s+(?:{_QUAL}){{0,3}}(?<![а-яё]){_TARGET}(?![а-яё])",
    re.IGNORECASE,
)

# «за 100 процентов», «за 12,5 процента». A 1–2 digit amount is already an ordinal.
# 100 and decimals are not, and the id parser would keep them or still wipe the folder.
_INTEREST_AMOUNT = re.compile(
    rf"\b\d+(?:\s*[.,]\s*\d+)?\s*(?:{_QUAL}){{0,2}}(?<![а-яё]){_INTEREST}(?![а-яё])",
    re.IGNORECASE,
)

# «вредные документы» / «документы процентные».
_ADJ_DOCS = re.compile(
    rf"(?:(?<![а-яё]){_ADJ}\s+(?:документ|файл)\w*|(?:документ|файл)\w*\s+(?<![а-яё]){_ADJ})(?![а-яё])",
    re.IGNORECASE,
)

DELETE_REFUSED_REPLY = (
    "Не удаляю файлы по виду «вред» / «пошлина» / «госпошлина» / «залог» / "
    "«индексация» / «проценты» / «взыскание» "
    "вроде «за вред» / «за пошлину» / «за проценты» / «за взыскание» / "
    "«1-го вреда» / «1-го процента» — "
    "это не номер документа и не команда очистить всю папку. "
    "Укажите id: «удали документ 214» или «удали документы [12] [18]». "
    "Чтобы очистить открытую папку целиком, напишите «удали все документы в этой папке» "
    "без этих слов."
)

MOVE_REFUSED_REPLY = (
    "Не переношу все файлы папки по виду «вред» / «пошлина» / «госпошлина» / «залог» / "
    "«индексация» / «проценты» / «взыскание» "
    "вроде «за вред» / «за пошлину» / «за проценты» / «за взыскание». "
    "Укажите id: «перенеси документ 214 в дело …». "
    "Чтобы перенести всю открытую папку, напишите без этих слов: "
    "«перенеси все документы в папку …»."
)


def mask_levy_ordinals(text: str) -> str:
    """Replace «1-го вреда» / «100 процентов» so the digit is not a document id.

    Amounts run first so «12,5 процента» is one token. The ordinal pass would
    otherwise keep «12» and only hide the «5».
    """
    masked = _INTEREST_AMOUNT.sub(" ", text or "")
    return _ORDINAL_NUM.sub(" ", masked)


def looks_like_levy_scoped_document_request(text: str) -> bool:
    """True when the user scoped files to вред / пошлина / залог / индексация / проценты / взыскание."""
    raw = text or ""
    if (
        _PREP.search(raw)
        or _DURING.search(raw)
        or _DEMONSTRATIVE_SCOPE.search(raw)
        or _ORDINAL_WORD.search(raw)
        or _ORDINAL_NUM.search(raw)
        or _INTEREST_AMOUNT.search(raw)
        or _DOCS.search(raw)
        or _ADJ_DOCS.search(raw)
    ):
        return True
    return False


def levy_blocks_bulk_document_mutation(
    text: str, *, explicit_document_ids: list[int] | None = None
) -> bool:
    """Refuse folder-wide delete/move when a levy scope is present.

    Chat treated «удали все документы за вред в этой папке» as wipe-the-folder
    because «все документы» matched wants_all and the document-type phrase was
    ignored. «удали документы 1-го вреда» took the first digit as a document id.
    The same path hits пошлина, госпошлина, залог, индексация, проценты, and взыскание.
    """
    if explicit_document_ids:
        return False
    return looks_like_levy_scoped_document_request(text)
