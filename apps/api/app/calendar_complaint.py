"""Complaint/petition/expert/security-measures chat scope.

Do not treat «за жалобу» / «за заявление» / «за экспертизу» / «за обеспечение»
as a folder wipe.
"""

from __future__ import annotations

import re

# Noun after a time preposition: «за жалобу», «на заявлении», «по экспертизе»,
# «за обеспечение», «за обеспечительные меры».
# Trailing (?![а-яё]) is applied at the call site so «жалобщик» / «заявленный»
# / «эксперт» / «обеспеченный» do not steal the noun slot.
_COMPLAINT_NOUN = (
    r"(?:жалоб(?:ами|ам|ах|ою|ой|а|у|е|ы)?"
    r"|заявлен(?:ие|ия|ию|ием|ии|ий|иям|иями|иях)"
    r"|экспертиз(?:ами|ам|ах|ою|ой|а|ы|е|у)?"
    r"|обеспечен(?:ие|ия|ию|ием|ии|ий|иям|иями|иях)"
    r"|обеспечительн(?:ый|ого|ому|ым|ом|ая|ую|ой|ое|ые|ых|ыми)\s+мер(?:ами|ам|ах|ой|а|у|е|ы)?)"
)

# Optional qualifier before the noun: «апелляционная жалоба», «исковое заявление».
# Do not reuse these as adj+docs — «судебные документы» must stay an unscoped wipe.
_COMPLAINT_ADJ = (
    r"(?:(?:апелляционн(?:ый|ая|ое|ые|ого|ому|ым|ом|ую|ой|ых|ыми))"
    r"|(?:кассационн(?:ый|ая|ое|ые|ого|ому|ым|ом|ую|ой|ых|ыми))"
    r"|(?:надзорн(?:ый|ая|ое|ые|ого|ому|ым|ом|ую|ой|ых|ыми))"
    r"|(?:частн(?:ый|ая|ое|ые|ого|ому|ым|ом|ую|ой|ых|ыми))"
    r"|(?:исков(?:ой|ая|ое|ые|ого|ому|ым|ом|ую|ых|ыми))"
    r"|(?:экспертн(?:ый|ая|ое|ые|ого|ому|ым|ом|ую|ой|ых|ыми))"
    r"|(?:обеспечительн(?:ый|ая|ое|ые|ого|ому|ым|ом|ую|ой|ых|ыми))"
    r"|(?:жалобн(?:ый|ая|ое|ые|ого|ому|ым|ом|ую|ой|ых|ыми)))"
)

_DEMONSTRATIVE = (
    r"(?:это|эти|этих|этими|этот|этой|этом|эта|эту|"
    r"прошл\w{0,4}|текущ\w{0,4}|данн\w{0,4}|сво\w{0,4})\s+"
)

_WORD_ORDINAL = (
    r"(?:перв(?:ое|ого|ому|ым|ом|ая|ую|ой|ый|ые|ых|ыми)|втор(?:ое|ого|ому|ым|ом|ая|ую|ой|ый|ые|ых|ыми)|"
    r"трет(?:ье|ьего|ьему|ьим|ьем|ья|ью|ьей|ий|ьи|ьих|ьими)|четв[её]рт(?:ое|ого|ому|ым|ом|ая|ую|ой|ый|ые|ых|ыми))"
)

_MODIFIER = rf"(?:{_WORD_ORDINAL}|{_COMPLAINT_ADJ})"

# Wrap the demonstrative: `{_DEMONSTRATIVE}?` would make only the trailing `\s+` optional.
_PREP_COMPLAINT = re.compile(
    rf"(?:за|на|в|во|по)\s+(?:{_DEMONSTRATIVE})?(?:(?<![а-яё]){_MODIFIER}\s+)?(?<![а-яё]){_COMPLAINT_NOUN}(?![а-яё])",
    re.IGNORECASE,
)

_DURING_COMPLAINT = re.compile(
    rf"во\s+время\s+(?:{_DEMONSTRATIVE})?(?:{_MODIFIER}\s+)?{_COMPLAINT_NOUN}(?![а-яё])",
    re.IGNORECASE,
)

_DEMONSTRATIVE_COMPLAINT = re.compile(
    rf"(?:эти|этих|этими|этот|этого|этом|эта|эту|этой|"
    r"прошлые|прошлых|прошлый|прошлая|прошлую|прошлое|"
    r"текущие|текущих|текущий|текущая|текущую|текущее|"
    r"данные|данных)\s+"
    rf"(?:{_MODIFIER}\s+)?{_COMPLAINT_NOUN}(?![а-яё])",
    re.IGNORECASE,
)

_ORDINAL_COMPLAINT_WORD = re.compile(
    rf"(?:за|в|во|на|по)\s+{_WORD_ORDINAL}\s+(?:{_COMPLAINT_ADJ}\s+)?{_COMPLAINT_NOUN}(?![а-яё])"
    rf"|\b{_WORD_ORDINAL}\s+(?:{_COMPLAINT_ADJ}\s+)?{_COMPLAINT_NOUN}(?![а-яё])",
    re.IGNORECASE,
)

# «1-й жалобы», «1-го заявления», «1-й экспертизы», «1-го обеспечения».
_ORDINAL_COMPLAINT_NUM = re.compile(
    r"\b\d{1,2}(?:-?(?:го|му|ой|ую|й|е|я|ю|о|м|х|ем))?\s*"
    r"(?:жалоб|заявлен|экспертиз|обеспечен|обеспечительн)",
    re.IGNORECASE,
)

# «документы жалобы» / «документы заявления» — genitive scope,
# not a folder titled «Жалоба» / «Заявление».
_COMPLAINT_DOCS = re.compile(
    rf"(?:документ|файл)\w*\s+(?:{_MODIFIER}\s+)?{_COMPLAINT_NOUN}(?![а-яё])",
    re.IGNORECASE,
)

# «жалобные документы» / «экспертные документы» / «обеспечительные документы».
_COMPLAINT_ADJ_DOCS = re.compile(
    r"(?<![а-яё])(?:жалобн(?:ый|ая|ое|ые|ого|ому|ым|ом|ую|ой|ых|ыми)|"
    r"экспертн(?:ый|ая|ое|ые|ого|ому|ым|ом|ую|ой|ых|ыми)|"
    r"обеспечительн(?:ый|ая|ое|ые|ого|ому|ым|ом|ую|ой|ых|ыми))\s+(?:документ|файл)",
    re.IGNORECASE,
)

DELETE_REFUSED_COMPLAINT = (
    "Не удаляю файлы по жалобе / заявлению / экспертизе / "
    "обеспечению вроде «за жалобу» / «за заявление» / "
    "«за экспертизу» / «за обеспечение» / "
    "«1-й жалобы» — это не номер документа и не команда очистить всю папку. "
    "Укажите id: «удали документ 214» или «удали документы [12] [18]». "
    "Чтобы очистить открытую папку целиком, напишите «удали все документы в этой папке» "
    "без жалобы, заявления, экспертизы и обеспечения."
)

MOVE_REFUSED_COMPLAINT = (
    "Не переношу все файлы папки по жалобе / заявлению / экспертизе / "
    "обеспечению вроде «за жалобу» / «за заявление» / "
    "«за экспертизу» / «за обеспечение». "
    "Укажите id: «перенеси документ 214 в дело …». "
    "Чтобы перенести всю открытую папку, напишите без жалобы и заявления: "
    "«перенеси все документы в папку …»."
)


def mask_complaint_ordinals(text: str) -> str:
    """Replace «1-й жалобы» so the leading digit cannot be parsed as a document id."""
    return _ORDINAL_COMPLAINT_NUM.sub(" ", text or "")


def looks_like_complaint_scoped_document_request(text: str) -> bool:
    """True when the user scoped files to a complaint, petition, expert review, or interim measures."""
    raw = text or ""
    if (
        _PREP_COMPLAINT.search(raw)
        or _DURING_COMPLAINT.search(raw)
        or _DEMONSTRATIVE_COMPLAINT.search(raw)
        or _ORDINAL_COMPLAINT_WORD.search(raw)
        or _ORDINAL_COMPLAINT_NUM.search(raw)
        or _COMPLAINT_DOCS.search(raw)
        or _COMPLAINT_ADJ_DOCS.search(raw)
    ):
        return True
    return False


def complaint_blocks_bulk_document_mutation(
    text: str, *, explicit_document_ids: list[int] | None = None
) -> bool:
    """Refuse folder-wide delete/move when a complaint/petition scope is present and no explicit [id] was given.

    Chat used to treat «удали все документы за жалобу в этой папке» as wipe-the-folder because
    «все документы» matched wants_all and the complaint phrase was ignored. «удали документы
    1-й жалобы» took the first digit as a document id.
    """
    if explicit_document_ids:
        return False
    return looks_like_complaint_scoped_document_request(text)
