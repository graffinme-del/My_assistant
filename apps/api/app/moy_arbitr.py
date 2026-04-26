from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

import httpx

from .case_number import normalize_arbitr_case_number
from .config import settings
from .models import Case


DEFAULT_MOY_ARBITR_BASE_URL = "https://my.arbitr.ru"


@dataclass
class MoyArbitrSection:
    title: str
    reason: str


def _base_url() -> str:
    return (settings.moy_arbitr_base_url or DEFAULT_MOY_ARBITR_BASE_URL).rstrip("/")


def looks_like_moy_arbitr_command(text: str) -> bool:
    lowered = (text or "").casefold()
    explicit_markers = (
        "мой арбитр",
        "моем арбитре",
        "моём арбитре",
        "my.arbitr",
        "my arbitr",
    )
    if any(marker in lowered for marker in explicit_markers):
        return True
    filing_markers = (
        "подать в арбитраж",
        "подать документы в арбитраж",
        "подать документы в суд",
        "электронная подача",
        "направить документы в арбитраж",
        "отправить документы в арбитраж",
    )
    return any(marker in lowered for marker in filing_markers)


def extract_moy_arbitr_case_number(text: str) -> str:
    raw = text or ""
    m = re.search(
        r"(?:дел[ауо]?|дела|номер)\s+№?\s*([АA]\d{1,4}-\d{1,7}/\d{2,4}|\d{1,2}-\d{1,7}/\d{2,4})",
        raw,
        flags=re.IGNORECASE,
    )
    if not m:
        m = re.search(r"№?\s*([АA]\d{1,4}-\d{1,7}/\d{2,4})", raw, flags=re.IGNORECASE)
    if not m:
        return ""
    return normalize_arbitr_case_number(m.group(1))


def _active_case_number(active_case: Case | None) -> str:
    if not active_case or not active_case.case_number:
        return ""
    cn = normalize_arbitr_case_number(active_case.case_number)
    if re.match(r"^A\d{1,4}-\d{1,7}/\d{2,4}", cn, flags=re.IGNORECASE):
        return cn
    return ""


def choose_moy_arbitr_section(text: str, case_number: str = "") -> MoyArbitrSection:
    lowered = (text or "").casefold()
    if any(w in lowered for w in ("банкрот", "несостоятельн")):
        return MoyArbitrSection("Банкротство", "для документов по делам о банкротстве")
    if any(w in lowered for w in ("апелляц", "апелляционная жалоба")):
        return MoyArbitrSection("Апелляционная жалоба", "для обжалования решения в апелляции")
    if any(w in lowered for w in ("кассац", "кассационная жалоба")):
        return MoyArbitrSection("Кассационная жалоба", "для кассационного обжалования")
    if any(w in lowered for w in ("надзор", "верховн")):
        return MoyArbitrSection("Кассационные и надзорные жалобы в ВС РФ", "для обращений в Верховный Суд РФ")
    if any(w in lowered for w in ("иск", "заявлени", "первичн")) and not case_number:
        return MoyArbitrSection("Иск (заявление)", "для первичного обращения без номера существующего дела")
    if any(w in lowered for w in ("отзыв", "возражен", "ходатайств", "приобщ", "текущее", "документы по делу")):
        return MoyArbitrSection("Документы по делам", "для текущих документов по уже существующему делу")
    if case_number:
        return MoyArbitrSection("Документы по делам", "номер дела известен, значит нужен раздел текущих документов")
    return MoyArbitrSection("Заявления и жалобы", "для выбора типа нового обращения")


def moy_arbitr_connection_status() -> dict[str, Any]:
    base_url = _base_url()
    status: dict[str, Any] = {
        "enabled": bool(settings.moy_arbitr_enabled),
        "base_url": base_url,
        "reachable": None,
        "status_code": None,
        "auth_mode": "external_browser_esia_or_signature",
        "can_submit_automatically": False,
        "notes": [
            "«Мой Арбитр» использует личный кабинет, Госуслуги и/или УКЭП.",
            "Ассистент не хранит пароль, токен Госуслуг или ключ электронной подписи.",
            "Автоматическая отправка документов отключена: финальное подписание и отправка выполняются пользователем.",
        ],
    }
    if not settings.moy_arbitr_enabled:
        return status
    try:
        with httpx.Client(timeout=float(settings.moy_arbitr_timeout_sec or 10), follow_redirects=True) as client:
            response = client.get(base_url)
        status["reachable"] = 200 <= response.status_code < 500
        status["status_code"] = response.status_code
    except Exception as exc:
        status["reachable"] = False
        status["error"] = str(exc)[:500]
    return status


def format_moy_arbitr_status_reply() -> str:
    status = moy_arbitr_connection_status()
    if not status["enabled"]:
        return (
            "Коннектор «Мой Арбитр» отключен настройкой MOY_ARBITR_ENABLED=0. "
            "Чтобы включить: задайте MOY_ARBITR_ENABLED=true и при необходимости MOY_ARBITR_BASE_URL."
        )
    reachable = status.get("reachable")
    if reachable is True:
        availability = f"сайт доступен (HTTP {status.get('status_code')})."
    elif reachable is False:
        err = status.get("error")
        availability = f"сайт сейчас не проверился: {err or 'нет ответа'}."
    else:
        availability = "доступность сайта ещё не проверялась."
    return (
        f"Подключение к «Мой Арбитр» настроено: {status['base_url']} — {availability}\n"
        "Важно: сервис работает через личный кабинет/Госуслуги/УКЭП, поэтому ассистент помогает подготовить пакет "
        "и выбрать раздел, а финальную авторизацию, подпись и отправку выполняет пользователь в браузере."
    )


def format_moy_arbitr_chat_reply(text: str, *, active_case: Case | None = None) -> str:
    lowered = (text or "").casefold()
    if any(w in lowered for w in ("статус", "проверь", "доступ", "подключ", "настрой")):
        return format_moy_arbitr_status_reply()

    case_number = extract_moy_arbitr_case_number(text) or _active_case_number(active_case)
    section = choose_moy_arbitr_section(text, case_number=case_number)
    base_url = _base_url()
    lines = [
        f"Откройте «Мой Арбитр»: {base_url}",
        f"Рекомендуемый раздел: «{section.title}» ({section.reason}).",
    ]
    if case_number:
        lines.append(f"Номер дела для ввода: {case_number}.")
    elif active_case:
        lines.append(
            "В активной папке нет распознанного арбитражного номера дела; перед подачей проверьте номер вручную."
        )
    lines.extend(
        [
            "Что может сделать ассистент здесь: собрать список файлов из папки, подготовить черновик сопроводительного текста, "
            "проверить наличие номера дела и подсказать порядок загрузки.",
            "Что не выполняется автоматически: вход через Госуслуги, подписание УКЭП и финальная отправка в суд.",
        ]
    )
    return "\n".join(lines)
