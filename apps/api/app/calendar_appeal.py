"""Appeal/cassation/review chat scope: do not treat «за апелляцию» as a folder wipe."""

from __future__ import annotations

import re

# Noun after a time preposition: «за апелляцию», «на кассации», «по рассмотрению».
# Trailing (?![а-яё]) is applied at the call site so «апелляционный» does not steal the noun slot.
_APPEAL_NOUN = (
    r"(?:апелляци(?:я|и|ю|ей|ям|ями|ях)?"
    r"|кассаци(?:я|и|ю|ей|ям|ями|ях)?"
    r"|рассмотрени(?:е|я|ю|ем|и|й|ям|ями|ях)?"
    r"|разбирательств(?:о|а|у|ом|е|ами|ах)?)"
)

_APPEAL_ADJ = (
    r"(?:(?:апелляционн(?:ый|ая|ое|ые|ого|ому|ым|ом|ую|ой|ых|ыми))"
    r"|(?:кассационн(?:ый|ая|ое|ые|ого|ому|ым|ом|ую|ой|ых|ыми))"
    r"|(?:судебн(?:ый|ая|ое|ые|ого|ому|ым|ом|ую|ой|ых|ыми)))"
)

# «апелляционная жалоба» / «кассационную жалобу» — instance + complaint, not bare «жалоба».
_COMPLAINT_NOUN = r"(?:жалоб(?:а|ы|у|е|ой|ам|ами|ах)?)"
_COMPLAINT_ADJ = (
    r"(?:(?:апелляционн(?:ый|ая|ое|ые|ого|ому|ым|ом|ую|ой|ых|ыми))"
    r"|(?:кассационн(?:ый|ая|ое|ые|ого|ому|ым|ом|ую|ой|ых|ыми)))"
)

_DEMONSTRATIVE = (
    r"(?:это|эти|этих|этими|этот|этой|этом|эта|эту|"
    r"прошл\w{0,4}|текущ\w{0,4}|данн\w{0,4}|сво\w{0,4})\s+"
)

# Wrap the demonstrative: `{_DEMONSTRATIVE}?` would make only the trailing `\s+` optional.
_PREP_APPEAL = re.compile(
    rf"(?:за|на|в|во|по)\s+(?:{_DEMONSTRATIVE})?(?:(?<![а-яё]){_APPEAL_ADJ}\s+)?(?<![а-яё]){_APPEAL_NOUN}(?![а-яё])",
    re.IGNORECASE,
)

_PREP_COMPLAINT = re.compile(
    rf"(?:за|на|в|во|по)\s+(?:{_DEMONSTRATIVE})?(?<![а-яё]){_COMPLAINT_ADJ}\s+(?<![а-яё]){_COMPLAINT_NOUN}(?![а-яё])",
    re.IGNORECASE,
)

_DURING_APPEAL = re.compile(
    rf"во\s+время\s+(?:{_DEMONSTRATIVE})?(?:{_APPEAL_ADJ}\s+)?{_APPEAL_NOUN}(?![а-яё])",
    re.IGNORECASE,
)

_DURING_COMPLAINT = re.compile(
    rf"во\s+время\s+(?:{_DEMONSTRATIVE})?{_COMPLAINT_ADJ}\s+{_COMPLAINT_NOUN}(?![а-яё])",
    re.IGNORECASE,
)

_DEMONSTRATIVE_APPEAL = re.compile(
    rf"(?:эти|этих|этими|этот|этого|этом|эта|эту|этой|"
    r"прошлые|прошлых|прошлый|прошлая|прошлую|прошлое|"
    r"текущие|текущих|текущий|текущая|текущую|текущее|"
    r"данные|данных)\s+"
    rf"(?:{_APPEAL_ADJ}\s+)?{_APPEAL_NOUN}(?![а-яё])",
    re.IGNORECASE,
)

_WORD_ORDINAL = (
    r"(?:перв(?:ое|ого|ому|ым|ом|ая|ую|ой|ый|ые|ых|ыми)|втор(?:ое|ого|ому|ым|ом|ая|ую|ой|ый|ые|ых|ыми)|"
    r"трет(?:ье|ьего|ьему|ьим|ьем|ья|ью|ьей|ий|ьи|ьих|ьими)|четв[её]рт(?:ое|ого|ому|ым|ом|ая|ую|ой|ый|ые|ых|ыми))"
)

_ORDINAL_APPEAL_WORD = re.compile(
    rf"(?:за|в|во|на|по)\s+{_WORD_ORDINAL}\s+(?:{_COMPLAINT_ADJ}\s+)?(?:{_APPEAL_NOUN}|{_COMPLAINT_NOUN})(?![а-яё])"
    rf"|\b{_WORD_ORDINAL}\s+(?:{_COMPLAINT_ADJ}\s+)?(?:{_APPEAL_NOUN}|{_COMPLAINT_NOUN})(?![а-яё])",
    re.IGNORECASE,
)

# «1-й апелляции», «1-го рассмотрения», «1-й апелляционной жалобы» — not a document id.
_ORDINAL_APPEAL_NUM = re.compile(
    r"\b\d{1,2}(?:-?(?:го|му|ой|ую|й|е|я|ю|о|м|х|ем))?\s*"
    r"(?:апелляци|кассаци|рассмотрени|разбирательств|апелляционн|кассационн)",
    re.IGNORECASE,
)

# «документы апелляции» / «документы судебного разбирательства» — genitive scope,
# not a folder titled «Апелляция».
_APPEAL_DOCS = re.compile(
    rf"(?:документ|файл)\w*\s+(?:{_APPEAL_ADJ}\s+)?{_APPEAL_NOUN}(?![а-яё])",
    re.IGNORECASE,
)

_COMPLAINT_DOCS = re.compile(
    rf"(?:документ|файл)\w*\s+{_COMPLAINT_ADJ}\s+{_COMPLAINT_NOUN}(?![а-яё])",
    re.IGNORECASE,
)

# «апелляционные документы» / «кассационные документы» — adj + files, not «судебные документы».
_APPEAL_ADJ_DOCS = re.compile(
    rf"(?<![а-яё]){_COMPLAINT_ADJ}\s+(?:документ|файл)",
    re.IGNORECASE,
)

DELETE_REFUSED_APPEAL = (
    "Не удаляю файлы по апелляции/кассации/рассмотрению вроде «за апелляцию» / "
    "«за кассацию» / «за рассмотрение» / «за судебное разбирательство» / "
    "«1-й апелляции» — это не номер документа и не команда очистить всю папку. "
    "Укажите id: «удали документ 214» или «удали документы [12] [18]». "
    "Чтобы очистить открытую папку целиком, напишите «удали все документы в этой папке» "
    "без апелляции, кассации, рассмотрения и разбирательства."
)

MOVE_REFUSED_APPEAL = (
    "Не переношу все файлы папки по апелляции/кассации/рассмотрению вроде "
    "«за апелляцию» / «за кассацию» / «за рассмотрение» / «за судебное разбирательство». "
    "Укажите id: «перенеси документ 214 в дело …». "
    "Чтобы перенести всю открытую папку, напишите без апелляции: "
    "«перенеси все документы в папку …»."
)


def mask_appeal_ordinals(text: str) -> str:
    """Replace «1-й апелляции» so the leading digit cannot be parsed as a document id."""
    return _ORDINAL_APPEAL_NUM.sub(" ", text or "")


def looks_like_appeal_scoped_document_request(text: str) -> bool:
    """True when the user scoped files to an appeal, cassation, review, or court proceeding."""
    raw = text or ""
    if (
        _PREP_APPEAL.search(raw)
        or _PREP_COMPLAINT.search(raw)
        or _DURING_APPEAL.search(raw)
        or _DURING_COMPLAINT.search(raw)
        or _DEMONSTRATIVE_APPEAL.search(raw)
        or _ORDINAL_APPEAL_WORD.search(raw)
        or _ORDINAL_APPEAL_NUM.search(raw)
        or _APPEAL_DOCS.search(raw)
        or _COMPLAINT_DOCS.search(raw)
        or _APPEAL_ADJ_DOCS.search(raw)
    ):
        return True
    return False


def appeal_blocks_bulk_document_mutation(
    text: str, *, explicit_document_ids: list[int] | None = None
) -> bool:
    """Refuse folder-wide delete/move when an appeal/cassation/review scope is present and no explicit [id] was given.

    Chat used to treat «удали все документы за апелляцию в этой папке» as wipe-the-folder because
    «все документы» matched wants_all and the appeal phrase was ignored. «удали документы
    1-й апелляции» took the first digit as a document id.
    """
    if explicit_document_ids:
        return False
    return looks_like_appeal_scoped_document_request(text)
