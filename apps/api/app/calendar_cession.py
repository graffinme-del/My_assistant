"""Bailiff, enforcement-fee, accord, and assignment scope.

Do not treat «за судебного пристава» / «за исполнительский сбор» /
«за отступное» / «за уступку права» / «за цессию» as a folder wipe, and
do not treat «1-го судебного пристава» / «100 исполнительского сбора» /
«12,5 отступного» / «1-й цессии» as a document id.

A folder titled «Судебный пристав», «Исполнительский сбор», «Отступное»,
«Цессия», or «Уступка права» does not match. «без цессии» does not match.
Bare «банкротство» does not match.

«исполнительный лист» and «исполнительное производство» are different
guards. «судебный приказ» is a different guard. «отступление» and
«приставка» are not these phrases. Bare «сбор» and bare «права» are not.
"""

from __future__ import annotations

import re

# Longer adjective endings first so «ыми» wins over «ым».
_ADJ_END = (
    r"(?:ыми|ими|ого|его|ому|ему|ых|их|ая|яя|ое|ее|ую|юю|ые|ие|ый|ий|ой|ым|им|ом|ем)"
)
_ADJ_WORD = rf"(?:[а-яё]{{3,}}-)?[а-яё]{{3,}}{_ADJ_END}"

# «судебный пристав» / «пристав-исполнитель» / «ФССП».
# «приставка» and «приставленный» do not match: the noun must end.
_SUD = rf"судебн{_ADJ_END}"
_PRISTAV = r"пристав(?:ами|ах|ам|ов|ом|у|е|ы|а)?"
_BAILIFF_OFFICER = rf"{_PRISTAV}(?:\s*-\s*исполнител[а-яё]*)?"
_BAILIFF = rf"(?:{_SUD}\s+(?:{_ADJ_WORD}\s+){{0,2}}{_BAILIFF_OFFICER}|{_BAILIFF_OFFICER}|(?<![a-zа-яё])(?:фссп|fssp))"

# «исполнительский сбор». Bare «сбор» / «сборник» do not match.
# «исполнительный лист» has no «сбор».
_FEE_ADJ = rf"(?:исполнительск|исполнительн){_ADJ_END}"
_SBOR = r"сбор(?:ами|ах|ам|ов|ом|у|е|ы|а)?"
_FEE = rf"{_FEE_ADJ}\s+(?:{_ADJ_WORD}\s+){{0,2}}{_SBOR}"

# «отступное». «отступление» has no «отступн».
_ACCORD = rf"отступн{_ADJ_END}"

# «уступка» / «цессия» / «цедент» / «цессионарий».
# «процесс» has no «цесси». Bare «права» is not a target.
_USTUP = r"уступк(?:ами|ах|ам|ой|ою|у|е|и|а)"
_CESSIONARY = r"цессионар(?:иями|иях|иям|иев|ием|ию|ии|ия|ий|ами|ах|ам|ов|ом|у|е|а|ы)?"
_CESSION_ADJ = rf"цессионн{_ADJ_END}"
_CEDENT = r"цедент(?:ами|ах|ам|ов|ом|у|е|ы|а)?"
_CESSIA = r"цесси(?:ями|ях|ям|ею|ей|ю|и|я|й)"
_ASSIGN = rf"(?:{_CESSIONARY}|{_CESSION_ADJ}|{_CEDENT}|{_CESSIA}|{_USTUP})"

_TARGET = rf"(?:{_BAILIFF}|{_FEE}|{_ACCORD}|{_ASSIGN})"

_DEMONSTRATIVE = (
    r"(?:этими|этих|этот|этого|этому|этой|этом|эта|эту|эти|это|"
    r"прошл\w{0,4}|текущ\w{0,4}|данн\w{0,4}|сво\w{0,4})\s+"
)

_WORD_ORDINAL = (
    r"(?:перв(?:ое|ого|ому|ым|ом|ая|ую|ой|ый|ые|ых|ыми)|втор(?:ое|ого|ому|ым|ом|ая|ую|ой|ый|ые|ых|ыми)|"
    r"трет(?:ье|ьего|ьему|ьим|ьем|ья|ью|ьей|ий|ьи|ьих|ьими)|четв[её]рт(?:ое|ого|ому|ым|ом|ая|ую|ой|ый|ые|ых|ыми))"
)

_WHOLE = r"(?<![а-яё])(?:всеми|всех|всему|всего|всей|всем|весь|вся|всё|все|всю)"

# Words that sit between the preposition and the bailiff / fee / accord / assignment.
# «папке» and «делу» are not here, so a folder titled «Цессия» does not match.
_NOUN_QUAL = (
    r"(?<![а-яё])(?:постановлени(?:ями|ях|ям|ем|ею|ю|и|е|я|й)?"
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
    "Не удаляю файлы по виду «судебный пристав» / «исполнительский сбор» / "
    "«отступное» / «уступка права» / «цессия» вроде «за судебного пристава» / "
    "«за исполнительский сбор» / «за отступное» / «за цессию» / "
    "«1-го судебного пристава» — "
    "это не номер документа и не команда очистить всю папку. "
    "Укажите id: «удали документ 214» или «удали документы [12] [18]». "
    "Чтобы очистить открытую папку целиком, напишите «удали все документы в этой папке» "
    "без этих слов."
)

MOVE_REFUSED_REPLY = (
    "Не переношу все файлы папки по виду «судебный пристав» / «исполнительский сбор» / "
    "«отступное» / «уступка права» / «цессия» вроде «за судебного пристава» / "
    "«за исполнительский сбор» / «за отступное» / «за цессию». "
    "Укажите id: «перенеси документ 214 в дело …». "
    "Чтобы перенести всю открытую папку, напишите без этих слов: "
    "«перенеси все документы в папку …»."
)


def _prepare(text: str) -> str:
    return (text or "").replace("ё", "е").replace("Ё", "Е")


def mask_cession_ordinals(text: str) -> str:
    """Replace «1-го судебного пристава» so the digit is not a document id.

    Amounts run first so «12,5 отступного» is one token. The ordinal pass
    would otherwise keep «12» and only hide the «5».
    """
    raw = _prepare(text)
    masked = _SCOPED_AMOUNT.sub(" ", raw)
    return _ORDINAL_NUM.sub(" ", masked)


def looks_like_cession_scoped_document_request(text: str) -> bool:
    """True when the user scoped files to a bailiff, fee, accord, or assignment."""
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


def cession_blocks_bulk_document_mutation(
    text: str, *, explicit_document_ids: list[int] | None = None
) -> bool:
    """Refuse folder-wide delete/move when a bailiff, fee, accord, or assignment scope is present.

    Chat treated «удали все документы за судебного пристава в этой папке» as
    wipe-the-folder because «все документы» matched wants_all and «в этой папке»
    (or a case number) selected the case. «удали документы 1-го судебного
    пристава» took the first digit as a document id. The same path hits
    «за исполнительский сбор», «за отступное», and «за цессию».
    """
    if explicit_document_ids:
        return False
    return looks_like_cession_scoped_document_request(text)
