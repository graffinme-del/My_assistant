"""Intent matching for semantic document collect. No FastAPI/Postgres imports."""

from __future__ import annotations

import re

# «просмотри папку …» is a review/list phrase unless a destination or move verb follows.
_REVIEW_FOLDER_TRIGGERS = (
    "просмотри всю папку",
    "просмотри папку",
    "просмотрите папку",
)

_COLLECT_TRIGGERS = (
    "отсортируй",
    "отсортир",
    "по смыслу",
    "по контекст",
    "самостоятельно",
    "относящиеся к делу",
    "относящиеся к папк",
    "все что относится",
    "всё что относится",
    "всех что относится",
    "оставь только документ",
    "оставь в папке только",
    "собери все документ",
    "соберите все документ",
    "консолидир",
    "сверни в одну папку",
    "в одну папку по делу",
    "по номеру дел",
    "по номерам дел",
    "перенеси подходящ",
    "перенесите подходящ",
    *_REVIEW_FOLDER_TRIGGERS,
)

_COLLECT_TRIGGERS_EXCEPT_REVIEW = tuple(
    x for x in _COLLECT_TRIGGERS if x not in _REVIEW_FOLDER_TRIGGERS
)

_DOC_NOUNS = ("документ", "файл", "материал", "архив", "пдф", "pdf")

_DEST_AFTER_REVIEW = re.compile(r"\bв\s+(?:папк|дело\b)", re.IGNORECASE)
_MOVE_AFTER_REVIEW = ("перенеси", "перенесите", "отсортируй", "собери", "соберите")


def review_folder_has_collect_destination(text: str) -> bool:
    """True when «просмотри папку А в папку Б» (or an explicit move verb) names a destination."""
    t = (text or "").lower()
    for marker in _REVIEW_FOLDER_TRIGGERS:
        idx = t.find(marker)
        if idx < 0:
            continue
        tail = t[idx + len(marker) :]
        if _DEST_AFTER_REVIEW.search(tail):
            return True
        if any(v in tail for v in _MOVE_AFTER_REVIEW):
            return True
    return False


def is_review_folder_without_collect_destination(text: str) -> bool:
    """Review/list a folder; no second folder and no collect/move verb."""
    t = (text or "").lower()
    if not any(x in t for x in _REVIEW_FOLDER_TRIGGERS):
        return False
    if any(x in t for x in _COLLECT_TRIGGERS_EXCEPT_REVIEW):
        return False
    return not review_folder_has_collect_destination(t)


def looks_like_semantic_matter_collect_request(text: str) -> bool:
    """Перенос по смыслу/контексту в целевую папку со всех остальных."""
    t = (text or "").lower()
    if not any(x in t for x in _COLLECT_TRIGGERS):
        return False
    if not any(x in t for x in _DOC_NOUNS):
        return False
    if "содержащ" in t and "создай папк" in t:
        return False
    if is_review_folder_without_collect_destination(t):
        return False
    return True


def wants_semantic_collect_preview_only(text: str) -> bool:
    """Явный запрос только показать кандидатов без переноса."""
    t = (text or "").lower()
    if "не только список" in t or "не только покажи" in t:
        return False
    if is_review_folder_without_collect_destination(t):
        return True
    return any(
        m in t
        for m in (
            "только список",
            "только покажи",
            "без переноса",
            "не переноси пока",
            "не переносить пока",
            "сначала покажи",
            "сначала список",
            "покажи кандидат",
            "только кандидат",
            "предпросмотр",
            "без автоматического переноса",
        )
    )
