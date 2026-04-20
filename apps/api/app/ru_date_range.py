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

    Сначала слова «сегодня»/«вчера»/«позавчера», затем ДД.ММ.ГГГГ — чтобы номера дел
    вроде «…/2025» не перехватывались как календарная дата.
    """
    raw = (text or "").strip()
    if not raw:
        return None
    lowered = raw.lower()

    # 1) Относительные дни (устойчивее \b для кириллицы в разных окружениях)
    today = datetime.now(assistant_timezone()).date()
    if re.search(r"(?<![а-яё])позавчера(?![а-яё])", lowered, re.IGNORECASE):
        return _utc_naive_bounds_for_local_day(today - timedelta(days=2))
    if re.search(r"(?<![а-яё])сегодня(?![а-яё])", lowered, re.IGNORECASE):
        return _utc_naive_bounds_for_local_day(today)
    if re.search(r"(?<![а-яё])вчера(?![а-яё])", lowered, re.IGNORECASE):
        return _utc_naive_bounds_for_local_day(today - timedelta(days=1))

    # 2) Явная дата ДД.ММ.ГГГГ или ДД.ММ.ГГ (точки или слэши)
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

    return None


def describe_calendar_period_ru(text: str) -> str | None:
    """Короткая подпись для ответа пользователю; None если период не распознан."""
    raw = (text or "").strip()
    if not raw:
        return None
    lowered = raw.lower()
    if re.search(r"(?<![а-яё])позавчера(?![а-яё])", lowered, re.IGNORECASE):
        return "позавчера"
    if re.search(r"(?<![а-яё])сегодня(?![а-яё])", lowered, re.IGNORECASE):
        return "сегодня"
    if re.search(r"(?<![а-яё])вчера(?![а-яё])", lowered, re.IGNORECASE):
        return "вчера"
    m = _RE_DMY.search(raw)
    if m:
        return f"{m.group(1)}.{m.group(2)}.{m.group(3)}"
    return None
