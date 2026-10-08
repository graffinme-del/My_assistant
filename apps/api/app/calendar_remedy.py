"""Damages / compensation / seizure / injunction / inventory / settlement / verdict scope.

Do not treat «за убытки» / «за компенсацию» / «за арест» / «за запрет» /
«за опись» / «за мировую» / «за приговор» as a folder wipe, and do not treat
«1-го убытка» / «1-й компенсации» / «1-го ареста» / «1-го приговора» as document id 1.

A folder titled «Убытки» or «Приговор» does not match.
«без убытков», «арестовать», «запретить», «описание», «описка», «компенсировать»,
«убыть», and «мировоззрение» do not match.
«Полис» / «штраф» / «гарантия» / «соглашение» remain separate guards.
Bare «взыскание» without «убытки» is not this guard.
"""

from __future__ import annotations

import re

# «взыскание убытков» is the usual collocation. Bare «взыскание» is not matched.
_LOSS_PREFIX = r"(?:взыскани(?:ями|ях|ям|ем|ею|ю|и|е|я)\s+)?"
# «убыток». «убыть» / «убытие» do not match: the ending is required and is not «ь».
_LOSSES = rf"{_LOSS_PREFIX}убыт(?:ками|ках|кам|ков|ком|ка|ку|ке|ки|ок)"

# «компенсация». «компенсировать» does not contain this stem.
_COMPENSATION = r"компенсаци(?:ями|ях|ям|ей|ею|ю|и|я)"

# «наложение ареста» / «наложение запрета». Bare «наложение» is not matched.
_IMPOSE = r"(?:наложени(?:ями|ях|ям|ем|ею|ю|и|е|я)\s+)?"
# «арест». «арестовать» / «арестант» do not match.
_ARREST = rf"{_IMPOSE}арест(?:ами|ах|ам|ов|ом|а|у|е|ы)?"
# «запрет». «запретить» / «запрещено» do not match.
_BAN = rf"{_IMPOSE}запрет(?:ами|ах|ам|ов|ом|а|у|е|ы)?"

# «опись». «описание» / «описать» / «описывать» / «описка» do not match.
_INVENTORY = r"опис(?:ьями|ями|ьях|ях|ьям|ям|ью|ей|и|ь)"

# «вынесение приговора». Bare «вынесение» is not matched. «приговорить» does not match.
_VERDICT_PREFIX = r"(?:вынесени(?:ями|ях|ям|ем|ею|ю|и|е|я)\s+)?"
_VERDICT = rf"{_VERDICT_PREFIX}приговор(?:ами|ах|ам|ов|ом|а|у|е|ы)?"

# «мировая» / «мировое соглашение». «мировоззрение» does not match.
_SETTLEMENT = r"миров(?:ыми|ого|ому|ых|ая|ую|ое|ым|ом|ою|ые|ой)"

_TARGET = rf"(?:{_VERDICT}|{_ARREST}|{_BAN}|{_LOSSES}|{_COMPENSATION}|{_INVENTORY}|{_SETTLEMENT})"

_LOSS_ADJ = r"убыточн(?:ыми|ый|ая|ое|ые|ого|ому|ым|ом|ую|ой|ых)"
_COMP_ADJ = r"компенсационн(?:ыми|ый|ая|ое|ые|ого|ому|ым|ом|ую|ой|ых)"
_ARREST_ADJ = r"арестн(?:ыми|ый|ая|ое|ые|ого|ому|ым|ом|ую|ой|ых)"
_BAN_ADJ = r"запретн(?:ыми|ый|ая|ое|ые|ого|ому|ым|ом|ую|ой|ых)"
_INV_ADJ = r"описн(?:ыми|ый|ая|ое|ые|ого|ому|ым|ом|ую|ой|ых)"
_VERDICT_ADJ = r"приговорн(?:ыми|ый|ая|ое|ые|ого|ому|ым|ом|ую|ой|ых)"
_ADJ = rf"(?:{_LOSS_ADJ}|{_COMP_ADJ}|{_ARREST_ADJ}|{_BAN_ADJ}|{_INV_ADJ}|{_VERDICT_ADJ}|{_SETTLEMENT})"

_DEMONSTRATIVE = (
    r"(?:этими|этих|этот|этого|этому|этой|этом|эта|эту|эти|это|"
    r"прошл\w{0,4}|текущ\w{0,4}|данн\w{0,4}|сво\w{0,4})\s+"
)

_WORD_ORDINAL = (
    r"(?:перв(?:ое|ого|ому|ым|ом|ая|ую|ой|ый|ые|ых|ыми)|втор(?:ое|ого|ому|ым|ом|ая|ую|ой|ый|ые|ых|ыми)|"
    r"трет(?:ье|ьего|ьему|ьим|ьем|ья|ью|ьей|ий|ьи|ьих|ьими)|четв[её]рт(?:ое|ого|ому|ым|ом|ая|ую|ой|ый|ые|ых|ыми))"
)

# One qualifier word: «моральную компенсацию», «обеспечительный арест», «обвинительный приговор».
_ADJ_WORD = (
    r"(?:[а-яё]{3,}-)?[а-яё]{3,}(?:ыми|ими|ый|ий|ой|ая|яя|ое|ее|ые|ие|ого|его|ому|ему|ым|им|ом|ем|ую|юю|ых|их)"
)

_QUAL = rf"(?:{_DEMONSTRATIVE}|{_WORD_ORDINAL}\s+|{_ADJ_WORD}\s+)"

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

# «1-го убытка», «1-й компенсации», «1-го приговора».
# Two digits so ids like 214 stay ids. (?!\d) so a longer number is not sliced.
_ORDINAL_NUM = re.compile(
    rf"\b\d{{1,2}}(?!\d)(?:-?{_ORDINAL_SUFFIX})?\s*(?:{_QUAL}){{0,2}}(?<![а-яё]){_TARGET}(?![а-яё])",
    re.IGNORECASE,
)

# «документы убытков» — genitive scope, not a folder titled «Убытки».
_DOCS = re.compile(
    rf"(?:документ|файл)\w*\s+(?:{_QUAL}){{0,3}}(?<![а-яё]){_TARGET}(?![а-яё])",
    re.IGNORECASE,
)

# «убыточные документы» / «документы компенсационные».
_ADJ_DOCS = re.compile(
    rf"(?:(?<![а-яё]){_ADJ}\s+(?:документ|файл)\w*|(?:документ|файл)\w*\s+(?<![а-яё]){_ADJ})(?![а-яё])",
    re.IGNORECASE,
)

DELETE_REFUSED_REPLY = (
    "Не удаляю файлы по виду «убытки» / «компенсация» / «арест» / «запрет» / "
    "«опись» / «мировая» / «приговор» "
    "вроде «за убытки» / «за компенсацию» / «за арест» / «за приговор» / "
    "«1-го убытка» / «1-го приговора» — "
    "это не номер документа и не команда очистить всю папку. "
    "Укажите id: «удали документ 214» или «удали документы [12] [18]». "
    "Чтобы очистить открытую папку целиком, напишите «удали все документы в этой папке» "
    "без этих слов."
)

MOVE_REFUSED_REPLY = (
    "Не переношу все файлы папки по виду «убытки» / «компенсация» / «арест» / «запрет» / "
    "«опись» / «мировая» / «приговор» "
    "вроде «за убытки» / «за компенсацию» / «за арест» / «за приговор». "
    "Укажите id: «перенеси документ 214 в дело …». "
    "Чтобы перенести всю открытую папку, напишите без этих слов: "
    "«перенеси все документы в папку …»."
)


def mask_remedy_ordinals(text: str) -> str:
    """Replace «1-го убытка» / «1-го приговора» so the digit is not a document id."""
    return _ORDINAL_NUM.sub(" ", text or "")


def looks_like_remedy_scoped_document_request(text: str) -> bool:
    """True when the user scoped files to убытки / компенсация / арест / запрет / опись / мировая / приговор."""
    raw = text or ""
    if (
        _PREP.search(raw)
        or _DURING.search(raw)
        or _DEMONSTRATIVE_SCOPE.search(raw)
        or _ORDINAL_WORD.search(raw)
        or _ORDINAL_NUM.search(raw)
        or _DOCS.search(raw)
        or _ADJ_DOCS.search(raw)
    ):
        return True
    return False


def remedy_blocks_bulk_document_mutation(
    text: str, *, explicit_document_ids: list[int] | None = None
) -> bool:
    """Refuse folder-wide delete/move when a remedy or enforcement scope is present.

    Chat treated «удали все документы за убытки в этой папке» as wipe-the-folder
    because «все документы» matched wants_all and the document-type phrase was
    ignored. «удали документы 1-го убытка» took the first digit as a document id.
    The same path hits компенсация, арест, запрет, опись, мировая, and приговор.
    """
    if explicit_document_ids:
        return False
    return looks_like_remedy_scoped_document_request(text)
