"""Intent matching for unsorted auto-sort chat (no Postgres / app.main)."""

from __future__ import annotations

_SORT_VERBS = ("разбери", "переразбери", "разложи")
_UNSORTED_MARKERS = ("неразобран", "unsorted")
_QUESTION_MARKERS = (
    "как ",
    "что ",
    "покажи",
    "расскажи",
    "объясни",
    "подскажи",
    "можно ли",
)
_MOVE_DESTINATION_MARKERS = ("перенеси", "перемести", "в папк")


def looks_like_reclassify_unsorted_request(text: str) -> bool:
    """True only for an explicit command to auto-sort the unsorted inbox.

    Targeted moves («перенеси неразобранные в папку …») and questions
    («как разложить неразобранное?») must not run auto-sort: that path
    immediately refiles every unsorted document by extracted case numbers
    and tags, creating folders as needed.
    """
    t = (text or "").lower()
    mentions_unsorted = any(k in t for k in _UNSORTED_MARKERS)
    if any(k in t for k in _QUESTION_MARKERS):
        return False
    if "автосорт" in t:
        return True
    if not mentions_unsorted:
        return False
    if any(k in t for k in _MOVE_DESTINATION_MARKERS):
        return False
    return any(k in t for k in _SORT_VERBS)
