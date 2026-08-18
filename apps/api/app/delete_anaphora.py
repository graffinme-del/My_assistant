"""Resolve «этот документ» / «эти документы» against [id] markers in the last assistant reply.

Singular phrasing must not hard-delete every listed file. The heuristic delete path
(`handle_delete_documents_chat`) and the chat-tools router both used every `[id]` from
the previous assistant message, so a search hit list plus «удали этот документ» wiped
the whole result set (and the files on disk).
"""

from __future__ import annotations

_SINGULAR_MARKERS = (
    "этот документ",
    "эту документ",
    "этот файл",
    "эту загрузку",
    "тот документ",
    "тот файл",
)

_PLURAL_MARKERS = (
    "эти документы",
    "эти файлы",
)

_LIST_MARKERS = (
    "найденн",
    "из результата",
    "из списка",
    "показанн",
    "выше ",
)


def looks_like_document_delete_anaphora(text: str) -> bool:
    """True when the user refers to a previously shown document instead of naming an id."""
    t = (text or "").lower()
    return any(k in t for k in _SINGULAR_MARKERS + _PLURAL_MARKERS + _LIST_MARKERS)


def is_singular_document_anaphora(text: str) -> bool:
    """«Этот документ» (one file). Plural «эти документы» wins when both appear."""
    t = (text or "").lower()
    has_singular = any(k in t for k in _SINGULAR_MARKERS)
    has_plural = any(k in t for k in _PLURAL_MARKERS)
    return has_singular and not has_plural


def clarification_for_ambiguous_anaphora(ids: list[int]) -> str:
    uniq = sorted({int(x) for x in ids if int(x) > 0})
    shown = uniq[:20]
    listed = ", ".join(f"[{i}]" for i in shown)
    extra = f" и ещё {len(uniq) - 20}" if len(uniq) > 20 else ""
    return (
        f"В предыдущем ответе несколько документов: {listed}{extra}. "
        "«Этот документ» — один файл; уточните номер, например: «удали документ 214». "
        "Чтобы удалить все перечисленные: «удали эти документы»."
    )


def resolve_anaphora_document_ids(text: str, extracted_ids: list[int]) -> tuple[list[int], str | None]:
    """Map anaphora + extracted [id]s to a delete set.

    Returns (ids, error). On singular phrasing with more than one id, ids is empty and
    error asks the user to pick a number — callers must not delete.
    """
    ids = sorted({int(x) for x in extracted_ids if int(x) > 0})
    if not looks_like_document_delete_anaphora(text):
        return ids, None
    if not is_singular_document_anaphora(text):
        return ids, None
    if len(ids) <= 1:
        return ids, None
    return [], clarification_for_ambiguous_anaphora(ids)
