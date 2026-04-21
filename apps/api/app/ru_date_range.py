"""Распознавание календарных формулировок в русских запросах для фильтрации по UTC в БД.

Поддерживаются: сегодня/вчера/позавчера, ДД.ММ.ГГГГ, относительные периоды
(«за последние 10 дней», «за последний месяц», «за прошлый месяц», «за последний год», …).
"""

from __future__ import annotations

import calendar
import os
import re
from datetime import date, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo


def assistant_timezone() -> ZoneInfo:
    return ZoneInfo(os.getenv("ASSISTANT_DATE_TZ", "Europe/Moscow"))


def _utc_naive_bounds_for_local_day(d: date) -> tuple[datetime, datetime]:
    """Границы [start, end) в наивном UTC для сравнения с полями, сохранёнными как utcnow()."""
    tz = assistant_timezone()
    start_local = datetime.combine(d, time.min, tzinfo=tz)
    end_local = start_local + timedelta(days=1)
    start_utc = start_local.astimezone(timezone.utc).replace(tzinfo=None)
    end_utc = end_local.astimezone(timezone.utc).replace(tzinfo=None)
    return start_utc, end_utc


def _utc_naive_bounds_for_local_range_inclusive(start_d: date, end_d: date) -> tuple[datetime, datetime]:
    """Закрытый интервал дат [start_d, end_d] в локальной зоне → [start_utc, next_midnight_after_end)."""
    if end_d < start_d:
        start_d, end_d = end_d, start_d
    tz = assistant_timezone()
    start_local = datetime.combine(start_d, time.min, tzinfo=tz)
    end_local = datetime.combine(end_d + timedelta(days=1), time.min, tzinfo=tz)
    start_utc = start_local.astimezone(timezone.utc).replace(tzinfo=None)
    end_utc = end_local.astimezone(timezone.utc).replace(tzinfo=None)
    return start_utc, end_utc


_RE_DMY = re.compile(
    r"(?<!\d)(\d{1,2})[./](\d{1,2})[./](\d{4}|\d{2})(?!\d)",
    re.UNICODE,
)

# «за последние 10 дней», «за последние 3 дня», «последние 5 суток»
_RE_LAST_N_DAYS = re.compile(
    r"(?:за|с)\s+последни[ея]\s+(\d{1,3})\s+(?:дн(?:ей|я|ём)?|день|суток)\b",
    re.IGNORECASE,
)
_RE_LAST_N_DAYS_SHORT = re.compile(
    r"\bпоследни[ея]\s+(\d{1,3})\s+(?:дн(?:ей|я|ём)?|день|суток)\b",
    re.IGNORECASE,
)
# «за 10 дней» (без слова «последние»)
_RE_ZA_N_DNEY = re.compile(
    r"за\s+(\d{1,3})\s+(?:дн(?:ей|я|ём)?|день|суток)\b",
    re.IGNORECASE,
)

_RE_LAST_N_WEEKS = re.compile(
    r"(?:за|с)\s+последни[ея]\s+(\d{1,2})\s+недел",
    re.IGNORECASE,
)
_RE_LAST_N_WEEKS_SHORT = re.compile(
    r"\bпоследни[ея]\s+(\d{1,2})\s+недел",
    re.IGNORECASE,
)

_RE_LAST_N_MONTHS = re.compile(
    r"(?:за|с)\s+последни[ея]\s+(\d{1,2})\s+(?:месяц|месяца|месяцев)\b",
    re.IGNORECASE,
)

_RE_LAST_N_YEARS = re.compile(
    r"(?:за|с)\s+последни[ея]\s+(\d{1,2})\s+(?:лет|года|год|годов)\b",
    re.IGNORECASE,
)

# Календарный прошлый месяц / год
_RE_PREV_MONTH = re.compile(
    r"(?:за|в)\s+прошлый\s+месяц\b|в\s+прошлом\s+месяце\b",
    re.IGNORECASE,
)
_RE_PREV_YEAR = re.compile(
    r"(?:за|в)\s+прошлый\s+год\b|в\s+прошлом\s+году\b",
    re.IGNORECASE,
)

# Скользящие «последний месяц / год» (не календарные)
_RE_ROLLING_LAST_MONTH = re.compile(
    r"за\s+последний\s+месяц\b",
    re.IGNORECASE,
)
_RE_ROLLING_LAST_YEAR = re.compile(
    r"за\s+последний\s+год\b",
    re.IGNORECASE,
)

_RE_LAST_WEEK = re.compile(
    r"за\s+последнюю\s+неделю\b|за\s+последн(?:ие|яя)\s+7\s+дн",
    re.IGNORECASE,
)
_RE_WEEK_SIMPLE = re.compile(
    r"(?<![а-яё])за\s+неделю\b(?![а-яё])",
    re.IGNORECASE,
)

_RE_HALF_YEAR = re.compile(
    r"за\s+последни[ея]\s+полгода\b|за\s+полгода\b",
    re.IGNORECASE,
)


def _roll_days_end_today(today: date, n: int) -> tuple[date, date]:
    n = max(1, min(n, 3660))
    return today - timedelta(days=n - 1), today


def _add_months(d: date, delta_months: int) -> date:
    """Добавить delta_months к дате (день обрезается по длине месяца)."""
    m = d.month - 1 + delta_months
    y = d.year + m // 12
    m = m % 12 + 1
    last = calendar.monthrange(y, m)[1]
    day = min(d.day, last)
    return date(y, m, day)


def _prev_calendar_month(today: date) -> tuple[date, date]:
    first_this = date(today.year, today.month, 1)
    last_prev = first_this - timedelta(days=1)
    first_prev = date(last_prev.year, last_prev.month, 1)
    return first_prev, last_prev


def _prev_calendar_year(today: date) -> tuple[date, date]:
    y = today.year - 1
    return date(y, 1, 1), date(y, 12, 31)


def _parse_calendar_period_ru_impl(text: str) -> tuple[tuple[datetime, datetime], str] | None:
    raw = (text or "").strip()
    if not raw:
        return None
    lowered = raw.lower()
    today = datetime.now(assistant_timezone()).date()

    if re.search(r"(?<![а-яё])позавчера(?![а-яё])", lowered, re.IGNORECASE):
        b = _utc_naive_bounds_for_local_day(today - timedelta(days=2))
        return b, "позавчера"
    if re.search(r"(?<![а-яё])сегодня(?![а-яё])", lowered, re.IGNORECASE):
        b = _utc_naive_bounds_for_local_day(today)
        return b, "сегодня"
    if re.search(r"(?<![а-яё])вчера(?![а-яё])", lowered, re.IGNORECASE):
        b = _utc_naive_bounds_for_local_day(today - timedelta(days=1))
        return b, "вчера"

    m = _RE_LAST_N_DAYS.search(lowered) or _RE_LAST_N_DAYS_SHORT.search(
        lowered
    ) or _RE_ZA_N_DNEY.search(lowered)
    if m:
        n = int(m.group(1))
        s, e = _roll_days_end_today(today, n)
        return _utc_naive_bounds_for_local_range_inclusive(s, e), f"последние {n} дн."

    m = _RE_LAST_N_WEEKS.search(lowered) or _RE_LAST_N_WEEKS_SHORT.search(lowered)
    if m:
        w = int(m.group(1))
        days = max(1, w * 7)
        s, e = _roll_days_end_today(today, days)
        return (
            _utc_naive_bounds_for_local_range_inclusive(s, e),
            f"последние {w} нед.",
        )

    m = _RE_LAST_N_MONTHS.search(lowered)
    if m:
        k = int(m.group(1))
        k = max(1, min(k, 120))
        start_d = today
        for _ in range(k):
            start_d = _add_months(start_d, -1)
        return (
            _utc_naive_bounds_for_local_range_inclusive(start_d, today),
            f"последние {k} мес.",
        )

    m = _RE_LAST_N_YEARS.search(lowered)
    if m:
        ky = int(m.group(1))
        ky = max(1, min(ky, 30))
        try:
            start_d = date(today.year - ky, today.month, today.day)
        except ValueError:
            start_d = date(today.year - ky, today.month, 28)
        return (
            _utc_naive_bounds_for_local_range_inclusive(start_d, today),
            f"последние {ky} г.",
        )

    if _RE_HALF_YEAR.search(lowered):
        s, e = _roll_days_end_today(today, 182)
        return _utc_naive_bounds_for_local_range_inclusive(s, e), "последние полгода"

    if _RE_LAST_WEEK.search(lowered) or _RE_WEEK_SIMPLE.search(lowered):
        s, e = _roll_days_end_today(today, 7)
        return _utc_naive_bounds_for_local_range_inclusive(s, e), "последняя неделя"

    if _RE_PREV_MONTH.search(lowered):
        s_d, e_d = _prev_calendar_month(today)
        label = f"прошлый месяц ({s_d.month:02d}.{s_d.year})"
        return _utc_naive_bounds_for_local_range_inclusive(s_d, e_d), label

    if _RE_ROLLING_LAST_MONTH.search(lowered):
        s, e = _roll_days_end_today(today, 30)
        return _utc_naive_bounds_for_local_range_inclusive(s, e), "последний месяц (30 дн.)"

    if _RE_PREV_YEAR.search(lowered):
        s_d, e_d = _prev_calendar_year(today)
        label = f"прошлый год ({s_d.year})"
        return _utc_naive_bounds_for_local_range_inclusive(s_d, e_d), label

    if _RE_ROLLING_LAST_YEAR.search(lowered):
        s, e = _roll_days_end_today(today, 365)
        return _utc_naive_bounds_for_local_range_inclusive(s, e), "последний год (365 дн.)"

    m = _RE_DMY.search(raw)
    if m:
        dd, mm, ystr = int(m.group(1)), int(m.group(2)), m.group(3)
        year = int(ystr)
        if len(ystr) == 2:
            year = 2000 + year if year < 70 else 1900 + year
        try:
            d = date(year, mm, dd)
        except ValueError:
            d = None
        if d is not None:
            b = _utc_naive_bounds_for_local_day(d)
            return b, f"{m.group(1)}.{m.group(2)}.{m.group(3)}"

    return None


def parse_calendar_period_ru(text: str) -> tuple[datetime, datetime] | None:
    """
    Полуинтервал [start_utc, end_utc) в наивном UTC для SQL-фильтра, или None.

    Учитывается локальный часовой пояс ассистента (по умолчанию Europe/Moscow).
    Сначала относительные дни и скользящие периоды, затем одна дата ДД.ММ.ГГГГ —
    чтобы номера дел вроде «…/2025» не перехватывались как календарная дата, если
    в том же тексте есть явный период (он матчится раньше по порядку проверок).
    """
    r = _parse_calendar_period_ru_impl(text)
    return r[0] if r else None


def describe_calendar_period_ru(text: str) -> str | None:
    """Короткая подпись для ответа пользователю; None если период не распознан."""
    r = _parse_calendar_period_ru_impl(text)
    return r[1] if r else None
