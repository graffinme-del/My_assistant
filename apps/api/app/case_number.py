"""Нормализация номеров арбитражных дел — отдельный модуль без тяжёлых зависимостей."""

import re


def normalize_arbitr_case_number(value: str) -> str:
    """Единый вид номера арбитражного дела (латинская A в начале, без пробелов)."""
    s = (value or "").replace(" ", "").replace("\n", "").replace("\\", "")
    if len(s) >= 3 and s[0] in ("\u0410", "\u0430"):
        s = "A" + s[1:]
    elif len(s) >= 3 and s[0] in ("A", "a"):
        s = "A" + s[1:]
    return s


def arbitr_case_number_lookup_keys(value: str) -> list[str]:
    """
    Варианты одного номера для поиска в БД: в папках часто A40-19021/25, в имени файла — A40-19021-2025.
    """
    s = normalize_arbitr_case_number((value or "").strip())
    if not s:
        return []
    out: list[str] = []
    seen: set[str] = set()

    def add(x: str) -> None:
        x = normalize_arbitr_case_number(x)
        if x and x not in seen:
            seen.add(x)
            out.append(x)

    add(s)
    m = re.match(r"^(A\d{1,4}-\d{1,7})/(\d{2,4})$", s, flags=re.IGNORECASE)
    if not m:
        return out
    base, yr = m.group(1), m.group(2)
    if len(yr) == 4 and yr.isdigit():
        add(f"{base}/{yr[2:4]}")
    elif len(yr) == 2 and yr.isdigit():
        add(f"{base}/20{yr}")
    return out
