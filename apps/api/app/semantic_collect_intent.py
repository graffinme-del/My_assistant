"""Intent detection for semantic matter collect.

Kept free of FastAPI/SQLAlchemy imports so unit tests can lock routing
without booting the API (create_all / Postgres).
"""

from __future__ import annotations

# Phrases that mean "sort / collect into a folder", not merely name a case.
_COLLECT_VERBS = (
    "отсортируй",
    "отсортир",
    "по смыслу",
    "по контекст",
    "самостоятельно",
    "консолидир",
    "сверни в одну папку",
    "перенеси подходящ",
    "перенесите подходящ",
    "просмотри всю папку",
    "просмотри папку",
    "просмотрите папку",
    "оставь только документ",
    "оставь в папке только",
    "собери все документ",
    "соберите все документ",
    "в одну папку по делу",
)

_COLLECT_TRIGGERS = _COLLECT_VERBS + (
    "относящиеся к делу",
    "относящиеся к папк",
    "все что относится",
    "всё что относится",
    "всех что относится",
    "по номеру дел",
    "по номерам дел",
)

_LOCATOR_ONLY_TRIGGERS = ("по номеру дел", "по номерам дел")

_DOC_NOUNS = ("документ", "файл", "материал", "архив", "пдф", "pdf")

_DELETE_VERBS = ("удали", "удалить", "стереть", "убери", "убрать")

_LIST_OR_COUNT_MARKERS = (
    "покажи",
    "покажите",
    "список",
    "выведи",
    "перечисли",
    "перечень",
    "какие документ",
    "какие файлы",
    "дай список",
    "сколько",
)

_EXECUTE_VERBS = (
    "перенеси",
    "перенесите",
    "отсортируй",
    "отсортируйте",
    "выполни",
    "собери",
    "соберите",
    "консолидир",
)


def _strip_negated_related_phrases(text: str) -> str:
    """«не относящиеся к делу» is a delete/filter phrase, not collect."""
    t = text
    for needle in (
        "не относящиеся к делу",
        "не относящиеся к папк",
        "не относится к делу",
        "не относятся к делу",
    ):
        t = t.replace(needle, " ")
    return t


def _has_explicit_collect_verb(t: str) -> bool:
    return any(v in t for v in _COLLECT_VERBS)


def _is_delete_list_or_count_command(t: str) -> bool:
    if not any(n in t for n in _DOC_NOUNS):
        return False
    if any(v in t for v in _DELETE_VERBS):
        return True
    if any(v in t for v in _LIST_OR_COUNT_MARKERS):
        return True
    return False


def looks_like_semantic_matter_collect_request(text: str) -> bool:
    """Перенос по смыслу/контексту в целевую папку со всех остальных."""
    t = (text or "").lower()
    t_triggers = _strip_negated_related_phrases(t)
    if not any(x in t_triggers for x in _COLLECT_TRIGGERS):
        return False
    if not any(x in t for x in _DOC_NOUNS):
        return False
    if "содержащ" in t and "создай папк" in t:
        return False
    # List / delete / count must not auto-move unless the user also asked to sort.
    if _is_delete_list_or_count_command(t) and not _has_explicit_collect_verb(t):
        return False
    other_triggers = [x for x in _COLLECT_TRIGGERS if x not in _LOCATOR_ONLY_TRIGGERS]
    locator_only = any(x in t_triggers for x in _LOCATOR_ONLY_TRIGGERS) and not any(
        x in t_triggers for x in other_triggers
    )
    if locator_only and not _has_explicit_collect_verb(t):
        return False
    return True


def wants_semantic_collect_preview_only(text: str) -> bool:
    """Явный запрос только показать кандидатов без переноса."""
    t = (text or "").lower()
    if "не только список" in t or "не только покажи" in t:
        return False
    if any(
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
    ):
        return True
    # Bare «покажи … по смыслу» is a preview, not an execute, unless a collect verb is present.
    if any(m in t for m in ("покажи", "покажите", "выведи", "список")) and not any(
        v in t for v in _EXECUTE_VERBS
    ):
        return True
    return False
