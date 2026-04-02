"""Нормализация номеров арбитражных дел — отдельный модуль без тяжёлых зависимостей."""


def normalize_arbitr_case_number(value: str) -> str:
    """Единый вид номера арбитражного дела (латинская A в начале, без пробелов)."""
    s = (value or "").replace(" ", "").replace("\n", "").replace("\\", "")
    if len(s) >= 3 and s[0] in ("\u0410", "\u0430"):
        s = "A" + s[1:]
    elif len(s) >= 3 and s[0] in ("A", "a"):
        s = "A" + s[1:]
    return s
