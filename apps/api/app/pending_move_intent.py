"""Heuristics for confirming / cancelling a PendingMovePlan from chat text.

Confirmation must be explicit. Broad Russian words like «кроме», «убери»,
«не относится», or bare «подтверждаю» must NOT apply a pending mass-move —
that caused silent relocation of documents after an unrelated follow-up.
"""

from __future__ import annotations

import re


def looks_like_pending_move_confirmation(text: str) -> bool:
    t = (text or "").lower()
    if any(
        k in t
        for k in (
            "да, перенеси",
            "да перенеси",
            "ок, перенеси",
            "окей, перенеси",
            "перенеси все",
        )
    ):
        return True
    # «подтверждаю» alone is too common; require transfer wording.
    if "подтверждаю" in t and ("перенес" in t or "перенос" in t):
        return True
    return False


def looks_like_pending_move_cancel(text: str) -> bool:
    """Explicit discard of the pending list (does not move documents)."""
    t = (text or "").lower()
    if any(
        k in t
        for k in (
            "отмени перенос",
            "отменить перенос",
            "отмена переноса",
            "сбрось список переноса",
            "сбросить список переноса",
            "не надо переносить",
            "не переноси ничего",
            "не переноси документы",
        )
    ):
        return True
    if re.search(r"\bне\s+переноси\b", t) and not re.search(r"\d", t):
        # Bare «не переноси» / «не переноси всё» without exclusion numbers → cancel.
        return True
    return False


def looks_like_pending_move_rejection(text: str) -> bool:
    """
    Legacy name kept for callers/tests.

    Previously matched bare «кроме» / «убери» / «не относится» and incorrectly
    *applied* the pending plan. Exclusion phrasing is handled inside
    ``apply_pending_move_plan`` when the user confirms («да, перенеси … кроме 3»).
    This helper is now only true for explicit cancel phrasing.
    """
    return looks_like_pending_move_cancel(text)
