"""Chat routing for document moves: named-file vs bulk folder dump."""

from __future__ import annotations

import re


def parse_explicit_move_document_ids(text: str) -> list[int]:
    """Ids the user named: [254] or «документ 254» / «файл 4» (not «документы … A40-12345»)."""
    raw = text or ""
    ids: list[int] = []
    seen: set[int] = set()

    def _add(value: int) -> None:
        if value not in seen:
            seen.add(value)
            ids.append(value)

    for m in re.finditer(r"\[(\d+)\]", raw):
        _add(int(m.group(1)))
    if ids:
        return ids
    for m in re.finditer(r"(?:документ|файл)\s+(\d+)\b", raw, flags=re.IGNORECASE):
        _add(int(m.group(1)))
    return ids


def looks_like_named_document_move(text: str) -> bool:
    """User pointed at specific file id(s) — must not dump the whole source folder."""
    return bool(parse_explicit_move_document_ids(text))


def looks_like_bulk_folder_move_request(text: str) -> bool:
    """«Собери / перенеси все документы в папку …» without naming file ids."""
    if looks_like_named_document_move(text):
        return False
    t = (text or "").lower()
    if "содерж" in t:
        return False
    if "создай папк" in t or "создай дело" in t:
        return False
    if ("папк" not in t and "дело" not in t) or not any(k in t for k in ("документ", "файл", "материал")):
        return False
    return any(
        k in t
        for k in (
            "собери",
            "соберите",
            "в отдельную папку",
            "все эти",
            "эти документы",
            "в папку",
            "все документы",
            "перенеси все",
            "перенеси",
            "назови",
            "назовите",
        )
    )


def looks_like_manual_move_request(text: str) -> bool:
    t = (text or "").lower()
    if not any(k in t for k in ("перенеси", "перемести", "привяжи")):
        return False
    if not any(k in t for k in ("документ", "файл", "[")):
        return False
    if not any(k in t for k in ("дело", "папк")):
        return False
    return True


def parse_manual_move_destination_hint(text: str) -> str:
    """Folder/case name after «в дело …» or «в папку …»."""
    raw = text or ""
    m = re.search(r"в\s+(?:дел[оау]|папк[уеауои])\s+(.+)$", raw, flags=re.IGNORECASE)
    if not m:
        return ""
    return m.group(1).strip(" .:-\"'«»")
