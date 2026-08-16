"""Heuristics for confirming / cancelling a PendingSemanticPlan from chat.

Confirmation must name the semantic merge. Broad Russian «подтверждаю» /
«согласен» plus a stray «смысл» or «по сути» must not merge folders — that
deleted source case cards after an unrelated follow-up.
"""

from __future__ import annotations


def looks_like_semantic_plan_confirm(text: str) -> bool:
    t = (text or "").lower()
    if "отмен" in t:
        return False
    phrases = (
        "да, объединить по смыслу",
        "да объединить по смыслу",
        "да, объедини по смыслу",
        "да объедини по смыслу",
        "ок, объединить по смыслу",
        "ок объединить по смыслу",
        "подтверждаю смысловое объединение",
        "подтверждаю смысловое объединен",
        "выполни смысловое объединение",
        "выполнить смысловое объединение",
        "примени смысловое объединение",
        "применить смысловое объединение",
        "примени смысловой план",
        "применить смысловой план",
        "выполни смысловой план",
        "выполнить смысловой план",
    )
    return any(p in t for p in phrases)


def looks_like_semantic_plan_cancel(text: str) -> bool:
    t = (text or "").lower()
    return (
        ("отмен" in t and "смысл" in t)
        or "отмени смыслов" in t
        or "сбрось смыслов" in t
        or "сбросить смыслов" in t
    )
