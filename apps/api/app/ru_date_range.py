"""Распознавание календарных формулировок в русских запросах (сегодня, вчера, ДД.ММ.ГГГГ) для фильтрации по UTC в БД."""

from __future__ import annotations

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


_RE_DMY = re.compile(
    r"(?<!\d)(\d{1,2})[./](\d{1,2})[./](\d{4}|\d{2})(?!\d)",
    re.UNICODE,
)


def parse_calendar_period_ru(text: str) -> tuple[datetime, datetime] | None:
    """
    Если в тексте есть явная дата или «сегодня»/«вчера»/«позавчера» — вернуть
    полуинтервал [start_utc, end_utc) для SQL-фильтра. Иначе None.

    Одна календарная дата в локальном часовом поясе ассистента (по умолчанию Москва).
    """
    raw = (text or "").strip()
    if not raw:
        return None
    lowered = raw.lower()

    # Явная дата ДД.ММ.ГГГГ или ДД.ММ.ГГ
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
            return _utc_naive_bounds_for_local_day(d)

    # Порядок: «позавчера» раньше «вчера» (подстрока внутри слова не ловим — границы слова)
    today = datetime.now(assistant_timezone()).date()
    if re.search(r"(?i)\bпозавчера\b", lowered):
        return _utc_naive_bounds_for_local_day(today - timedelta(days=2))
    if re.search(r"(?i)\bсегодня\b", lowered):
        return _utc_naive_bounds_for_local_day(today)
    if re.search(r"(?i)\bвчера\b", lowered):
        return _utc_naive_bounds_for_local_day(today - timedelta(days=1))

    return None


def describe_calendar_period_ru(text: str) -> str | None:
    """Короткая подпись для ответа пользователю; None если период не распознан."""
    raw = (text or "").strip()
    if not raw:
        return None
    lowered = raw.lower()
    m = _RE_DMY.search(raw)
    if m:
        return f"{m.group(1)}.{m.group(2)}.{m.group(3)}"
    if re.search(r"(?i)\bпозавчера\b", lowered):
        return "позавчера"
    if re.search(r"(?i)\bсегодня\b", lowered):
        return "сегодня"
    if re.search(r"(?i)\bвчера\b", lowered):
        return "вчера"
    return None
