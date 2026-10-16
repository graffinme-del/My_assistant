"""Advance, cash-deposit, letter-of-credit, and factoring scope.

Do not treat «за аванс» / «за депозит» / «за аккредитив» / «за факторинг»
as a folder wipe, and do not treat «1-го аванса» / «100 депозита» /
«12,5 аккредитива» / «214-го факторинга» as a document id.

A folder titled «Аванс», «Депозит», «Аккредитив», or «Факторинг» does not
match. «без аванса» does not match. Bare «банкротство» does not match.
«авансцена», «авангард», «депозитарий», and bare «фактор» do not match.
«задаток» and «обеспечительный платеж» do not match.
"""

from __future__ import annotations

import re

# Longer adjective endings first so «ыми» wins over «ым».
_ADJ_END = (
    r"(?:ыми|ими|ого|его|ому|ему|ых|их|ая|яя|ое|ее|ую|юю|ые|ие|ый|ий|ой|ым|им|ом|ем)"
)
_ADJ_WORD = rf"(?:[а-яё]{{3,}}-)?[а-яё]{{3,}}{_ADJ_END}"

# «авансовый». The noun «авансов» has no adjective ending after it.
_ADVANCE_ADJ = rf"авансов{_ADJ_END}"
# «аванс» / «аванса» / «авансом». «авансцена» fails the trailing boundary.
_ADVANCE_NOUN = r"аванс(?:ами|ах|ам|ов|ом|е|а|у|ы)?"
# «авансирование». The verb «авансировать» has no «ни».
_ADVANCE_FINANCING = r"авансировани(?:ями|ях|ям|ем|ею|ю|и|е|я|й)?"
_ADVANCE = rf"(?:{_ADVANCE_ADJ}|{_ADVANCE_FINANCING}|{_ADVANCE_NOUN})"

# «депозитный». «депозитарий» / «депозитарный» fail the noun boundary.
_DEPOSIT_ADJ = rf"депозитн{_ADJ_END}"
_DEPOSIT_NOUN = r"депозит(?:ами|ах|ам|ов|ом|е|а|у|ы)?"
_DEPOSIT = rf"(?:{_DEPOSIT_ADJ}|{_DEPOSIT_NOUN})"

# «аккредитив» / «аккредитивный».
_LC_ADJ = rf"аккредитивн{_ADJ_END}"
_LC_NOUN = r"аккредитив(?:ами|ах|ам|ов|ом|е|а|у|ы)?"
_LC = rf"(?:{_LC_ADJ}|{_LC_NOUN})"

# «факторинг» / «факторинговый». Bare «фактор» has no «инг».
_FACTOR_ADJ = rf"факторингов{_ADJ_END}"
_FACTOR_NOUN = r"факторинг(?:ами|ах|ам|ов|ом|е|а|у)?"
_FACTOR = rf"(?:{_FACTOR_ADJ}|{_FACTOR_NOUN})"

_TARGET = rf"(?:{_ADVANCE}|{_DEPOSIT}|{_LC}|{_FACTOR})"

_DEMONSTRATIVE = (
    r"(?:этими|этих|этот|этого|этому|этой|этом|эта|эту|эти|это|"
    r"прошл\w{0,4}|текущ\w{0,4}|данн\w{0,4}|сво\w{0,4})\s+"
)

_WORD_ORDINAL = (
    r"(?:перв(?:ое|ого|ому|ым|ом|ая|ую|ой|ый|ые|ых|ыми)|втор(?:ое|ого|ому|ым|ом|ая|ую|ой|ый|ые|ых|ыми)|"
    r"трет(?:ье|ьего|ьему|ьим|ьем|ья|ью|ьей|ий|ьи|ьих|ьими)|четв[её]рт(?:ое|ого|ому|ым|ом|ая|ую|ой|ый|ые|ых|ыми))"
)

_WHOLE = r"(?<![а-яё])(?:всеми|всех|всему|всего|всей|всем|весь|вся|всё|все|всю)"

# Words that sit between the preposition and the advance / deposit / credit / factoring.
# «папке» and «делу» are not here, so a folder titled «Аванс» does not match.
_NOUN_QUAL = (
    r"(?<![а-яё])(?:не)?(?:"
    r"постановлени(?:ями|ях|ям|ем|ею|ю|и|е|я|й)?"
    r"|отсутстви(?:ями|ях|ям|ем|ею|ю|и|е|я|й)?"
    r"|перечислени(?:ями|ях|ям|ем|ею|ю|и|е|я|й)?"
    r"|обслуживани(?:ями|ях|ям|ем|ею|ю|и|е|я|й)?"
    r"|зачислени(?:ями|ях|ям|ем|ею|ю|и|е|я|й)?"
    r"|внесени(?:ями|ях|ям|ем|ею|ю|и|е|я|й)?"
    r"|удержани(?:ями|ях|ям|ем|ею|ю|и|е|я|й)?"
    r"|наличи(?:ями|ях|ям|ем|ею|ю|и|е|я|й)?"
    r"|получени(?:ями|ях|ям|ем|ею|ю|и|е|я|й)?"
    r"|открыти(?:ями|ях|ям|ем|ею|ю|и|е|я|й)?"
    r"|покрыти(?:ями|ях|ям|ем|ею|ю|и|е|я|й)?"
    r"|списани(?:ями|ях|ям|ем|ею|ю|и|е|я|й)?"
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
    r"|перевод(?:ами|ах|ам|ов|ом|е|а|у|ы)?"
    r"|уплат(?:ами|ах|ам|ою|ой|у|е|ы|а)?"
    r"|оплат(?:ами|ах|ам|ою|ой|у|е|ы|а)?"
    r"|отмен(?:ами|ах|ам|ою|ой|у|е|ы|а)?"
    r"|выдач(?:ами|ах|ам|ею|ей|у|е|и|а)?"
    r"|сумм(?:ами|ах|ам|ою|ой|у|е|ы|а)?"
    r"|служб(?:ами|ах|ам|ою|ой|у|е|ы|а)?"
    r"|договор(?:ами|ах|ам|ов|ом|е|а|у|ы)?"
    r"|расчет(?:ами|ах|ам|ов|ом|е|а|у|ы)?"
    r"|размер(?:ами|ах|ам|ов|ом|е|а|у|ы)?"
    r"|запрет(?:ами|ах|ам|ов|ом|е|а|у|ы)?"
    r"|арест(?:ами|ах|ам|ов|ом|е|а|у|ы)?"
    r"|розыск(?:ами|ах|ам|ов|ом|е|а|у|и)?"
    r"|отчет(?:ами|ах|ам|ов|ом|е|а|у|ы)?"
    r"|остат(?:ками|ках|кам|ков|ком|ке|ки|ка|ку|ок)"
    r"|транш(?:ами|ах|ам|ей|ом|у|е|и|а)?"
    r"|счет(?:ами|ах|ам|ов|ом|е|а|у|ы)?"
    r"|част(?:ями|ях|ям|ью|ей|и|ь)"
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
    "Не удаляю файлы по виду «аванс» / «депозит» / "
    "«аккредитив» / «факторинг» вроде «за аванс» / "
    "«за депозит» / «за аккредитив» / «за факторинг» / "
    "«1-го аванса» — "
    "это не номер документа и не команда очистить всю папку. "
    "Укажите id: «удали документ 214» или «удали документы [12] [18]». "
    "Чтобы очистить открытую папку целиком, напишите «удали все документы в этой папке» "
    "без этих слов."
)

MOVE_REFUSED_REPLY = (
    "Не переношу все файлы папки по виду «аванс» / «депозит» / "
    "«аккредитив» / «факторинг» вроде «за аванс» / "
    "«за депозит» / «за аккредитив» / «за факторинг». "
    "Укажите id: «перенеси документ 214 в дело …». "
    "Чтобы перенести всю открытую папку, напишите без этих слов: "
    "«перенеси все документы в папку …»."
)


def _prepare(text: str) -> str:
    return (text or "").replace("ё", "е").replace("Ё", "Е")


def mask_advance_ordinals(text: str) -> str:
    """Replace «1-го аванса» so the digit is not a document id.

    Amounts run first so «12,5 аккредитива» is one token. The ordinal pass
    would otherwise keep «12» and only hide the «5».
    """
    raw = _prepare(text)
    masked = _SCOPED_AMOUNT.sub(" ", raw)
    return _ORDINAL_NUM.sub(" ", masked)


def looks_like_advance_scoped_document_request(text: str) -> bool:
    """True when the user scoped files to an advance, cash deposit, letter of credit, or factoring."""
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


def advance_blocks_bulk_document_mutation(
    text: str, *, explicit_document_ids: list[int] | None = None
) -> bool:
    """Refuse folder-wide delete/move when an advance, deposit, credit, or factoring scope is present.

    Chat treated «удали все документы за аванс в этой папке» as wipe-the-folder
    because «все документы» matched wants_all and «в этой папке» (or a case
    number, or «текущ» / «открыт») selected the case. «удали документы 1-го
    аванса» took the first digit as a document id. The same path hits
    «за депозит», «за аккредитив», and «за факторинг».
    """
    if explicit_document_ids:
        return False
    return looks_like_advance_scoped_document_request(text)
