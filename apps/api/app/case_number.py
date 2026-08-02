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


def extract_case_number(text: str) -> str | None:
    """
    Extract a court case number from free text or a filename.

    Supported shapes (intentionally narrow — bare N/YYYY matches invoices,
    page marks like 3/15, and dates like 01/2025 and must not auto-file docs):
    - А40-12345/2026 / A40-12345/2026
    - 2-123/2026 (magistrate / general jurisdiction style)
    - A40-19021-2025_....pdf (KAD filename with year after a hyphen)
    """
    # Examples:
    # - А40-12345/2026
    # - 2-123/2026
    # - A40-19021-2025_дата_....pdf (имя файла из КАД: год через дефис)
    m_fn = re.search(
        r"([АA]\d{1,4})-(\d{1,7})-(\d{2,4})(?=[_\.\s\[\]\-]|$)",
        text or "",
        flags=re.IGNORECASE,
    )
    if m_fn:
        p1 = m_fn.group(1)
        if len(p1) >= 1 and p1[0] in "\u0410\u0430":
            p1 = "A" + p1[1:]
        elif len(p1) >= 1 and p1[0] in "aA":
            p1 = "A" + p1[1:]
        raw = f"{p1}-{m_fn.group(2)}/{m_fn.group(3)}"
        return normalize_arbitr_case_number(raw)
    patterns = [
        r"([АA]\d{1,4}\s*-\s*\d{1,7}\s*/\s*\d{2,4})",
        r"(\d{1,2}\s*-\s*\d{1,7}\s*/\s*\d{2,4})",
    ]
    for p in patterns:
        m = re.search(p, text or "", flags=re.IGNORECASE)
        if m:
            raw = m.group(1) if m.lastindex else m.group(0)
            raw = raw.replace(" ", "").replace("\n", "")
            raw = raw.replace("\\", "")
            return normalize_arbitr_case_number(raw)
    return None


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
