"""Detect «the folder that is open», not every «текущ» / «открыт» / «в этой».

`handle_delete_documents_chat` used to treat those substrings as the active case.
«удали все документы по текущей задолженности», «за текущий ремонт», «после открытия»,
and «в этой ситуации» then hard-deleted every file in the open folder.

Real folder references stay: «в этой папке», «из этой папки», «в текущей папке»,
«текущего дела», «в открытой папке», «открытом деле», «это дело».
"""

from __future__ import annotations

import re

# «же», «самой» — not an arbitrary word, so «текущей задолженности» stays out.
_PARTICLE = r"(?:же|вот|сам(?:ыми|ого|ому|ое|ая|ую|ой|ые|ых|ым|ом|ый))"

# «папка/папке/папку/…». «делопроизводство» does not match: «дело» must end.
_PAPKA = r"папк(?:ами|ах|ам|ою|ой|ок|у|и|е|а|о)?"
_DELO = r"дел(?:ами|ах|ам|ов|ом|о|а|у|е|ы)?"
_FOLDER = rf"(?:{_PAPKA}|{_DELO})(?![а-яё])"

_THIS_FOLDER = re.compile(
    rf"(?:в\s+|из\s+)?(?<![а-яё])этой(?:\s+{_PARTICLE}){{0,2}}\s+{_FOLDER}",
    re.IGNORECASE,
)
_CURRENT_OR_OPEN_FOLDER = re.compile(
    rf"(?<![а-яё])(?:текущ\w*|открыт\w*)(?:\s+{_PARTICLE}){{0,2}}\s+{_FOLDER}",
    re.IGNORECASE,
)
# «это дело», not «это делопроизводство».
_THIS_CASE = re.compile(r"(?<![а-яё])это\s+дело(?![а-яё])", re.IGNORECASE)


def looks_like_active_folder_reference(text: str) -> bool:
    """True when the phrase points at the open folder or case."""
    low = (text or "").lower().replace("ё", "е")
    return bool(
        _THIS_FOLDER.search(low)
        or _CURRENT_OR_OPEN_FOLDER.search(low)
        or _THIS_CASE.search(low)
    )
