"""Preview vs execute intent for cross-folder duplicate cleanup chat.

Substring checks like ``\"удали\" in text`` also match preview phrasing
(«что удалишь», «что удалится»), which previously turned a preview request
into an immediate hard-delete.
"""

from __future__ import annotations

PREVIEW_PHRASES: tuple[str, ...] = (
    "только список",
    "без удаления",
    "не удаляй",
    "превью",
    "покажи план",
    "что удалишь",
    "что удалится",
)

EXECUTE_STEMS: tuple[str, ...] = (
    "удали",
    "убери",
    "почисти",
    "сотри",
    "выполни удаление",
    "да, удали",
)

KEEP_ONE_PHRASES: tuple[str, ...] = (
    "оставь од",
    "один экземпляр",
    "одну копию",
    "одна копия",
)

SHOW_WORDS: tuple[str, ...] = ("покажи", "выведи")


def without_preview_phrases(text: str) -> str:
    remainder = (text or "").lower()
    for phrase in sorted(PREVIEW_PHRASES, key=len, reverse=True):
        remainder = remainder.replace(phrase, " ")
    return remainder


def has_duplicate_cleanup_listed_preview_phrase(text: str) -> bool:
    t = (text or "").lower()
    return any(phrase in t for phrase in PREVIEW_PHRASES)


def has_duplicate_cleanup_preview_intent(text: str) -> bool:
    t = (text or "").lower()
    if has_duplicate_cleanup_listed_preview_phrase(t):
        return True
    return any(word in t for word in SHOW_WORDS)


def has_duplicate_cleanup_execute_stem(text: str) -> bool:
    remainder = without_preview_phrases(text)
    return any(stem in remainder for stem in EXECUTE_STEMS)


def has_duplicate_cleanup_keep_one_intent(text: str) -> bool:
    t = (text or "").lower()
    return any(phrase in t for phrase in KEEP_ONE_PHRASES)


def has_duplicate_cleanup_execute_intent(text: str) -> bool:
    return has_duplicate_cleanup_execute_stem(text) or has_duplicate_cleanup_keep_one_intent(text)


def is_duplicate_cleanup_dry_run(text: str) -> bool:
    """True when the user asked to list/plan, not to delete extra copies."""
    if not has_duplicate_cleanup_preview_intent(text):
        return False
    return not has_duplicate_cleanup_execute_intent(text)
