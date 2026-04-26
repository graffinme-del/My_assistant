from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

import httpx

from .case_number import normalize_arbitr_case_number
from .config import settings
from .models import Case


MOY_ARBITR_QUERY_PREFIX = "moy_arbitr_"


DEFAULT_MOY_ARBITR_BASE_URL = "https://my.arbitr.ru"


@dataclass
class MoyArbitrSection:
    title: str
    reason: str


@dataclass
class MoyArbitrSearchRequest:
    query_type: str
    query_value: str
    run_mode: str = "preview"


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


def looks_like_moy_arbitr_search_command(text: str) -> bool:
    lowered = (text or "").casefold()
    if not any(m in lowered for m in ("мой арбитр", "моем арбитре", "моём арбитре", "my.arbitr")):
        return False
    return any(
        m in lowered
        for m in (
            "найди",
            "поищи",
            "поиск",
            "скачай",
            "загрузи",
            "материалы",
            "документы",
            "проверь",
            "участник",
            "инн",
            "огрн",
        )
    )


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


def _normalize_digits(value: str) -> str:
    return re.sub(r"\D+", "", value or "")


def parse_moy_arbitr_search_request(text: str) -> MoyArbitrSearchRequest | None:
    raw = text or ""
    lowered = raw.casefold()
    if not looks_like_moy_arbitr_search_command(raw):
        return None

    case_number = extract_moy_arbitr_case_number(raw)
    if case_number:
        return MoyArbitrSearchRequest(
            query_type="moy_arbitr_case_number",
            query_value=case_number,
            run_mode="download" if any(w in lowered for w in ("скачай", "загрузи", "материалы", "документы")) else "preview",
        )

    m_inn = re.search(r"\bинн\b[:\s]*([\d\s]{10,15})", raw, flags=re.IGNORECASE)
    if m_inn:
        inn = _normalize_digits(m_inn.group(1))
        if inn:
            return MoyArbitrSearchRequest(
                query_type="moy_arbitr_inn",
                query_value=inn,
                run_mode="download" if any(w in lowered for w in ("скачай", "загрузи")) else "preview",
            )

    m_ogrn = re.search(r"\bогрн\b[:\s]*([\d\s]{12,18})", raw, flags=re.IGNORECASE)
    if m_ogrn:
        ogrn = _normalize_digits(m_ogrn.group(1))
        if ogrn:
            return MoyArbitrSearchRequest(
                query_type="moy_arbitr_ogrn",
                query_value=ogrn,
                run_mode="download" if any(w in lowered for w in ("скачай", "загрузи")) else "preview",
            )

    for pat in (
        r"участник[ауе]?\s+дел[ау]?\s+(?:'([^']+)'|\"([^\"]+)\"|«([^»]+)»|([А-ЯЁA-Z0-9][^.\n!?;]{2,160}))",
        r"по\s+участник[ауе]?\s+(?:'([^']+)'|\"([^\"]+)\"|«([^»]+)»|([А-ЯЁA-Z0-9][^.\n!?;]{2,160}))",
        r"по\s+данным\s+(?:'([^']+)'|\"([^\"]+)\"|«([^»]+)»|([А-ЯЁA-Z0-9][^.\n!?;]{2,160}))",
    ):
        m = re.search(pat, raw, flags=re.IGNORECASE)
        if m:
            val = next((g for g in m.groups() if g and str(g).strip()), "")
            val = re.sub(r"\s+", " ", val).strip(" :.-\"'«»")
            if len(val) >= 3:
                return MoyArbitrSearchRequest(
                    query_type="moy_arbitr_participant_name",
                    query_value=val,
                    run_mode="download" if any(w in lowered for w in ("скачай", "загрузи")) else "preview",
                )

    for marker in ("по организации", "организацию", "организации", "компанию", "по компании"):
        idx = lowered.find(marker)
        if idx >= 0:
            candidate = raw[idx + len(marker):].strip(" :.-\"'«»")
            candidate = re.sub(r"\s+", " ", candidate)
            if len(candidate) >= 3:
                return MoyArbitrSearchRequest(
                    query_type="moy_arbitr_organization_name",
                    query_value=candidate[:160],
                    run_mode="download" if any(w in lowered for w in ("скачай", "загрузи")) else "preview",
                )
    return None


def is_moy_arbitr_query_type(query_type: str | None) -> bool:
    return bool(query_type and str(query_type).startswith(MOY_ARBITR_QUERY_PREFIX))


def strip_moy_arbitr_query_prefix(query_type: str) -> str:
    if is_moy_arbitr_query_type(query_type):
        return query_type[len(MOY_ARBITR_QUERY_PREFIX):]
    return query_type


def format_moy_arbitr_search_queued_reply(req: MoyArbitrSearchRequest, *, job_id: int, created: bool) -> str:
    mode = "загрузку материалов" if req.run_mode == "download" else "поиск"
    if not created:
        return (
            f"Такой поиск в «Мой Арбитр» уже выполняется или стоит в очереди (задача №{job_id}) "
            f"по запросу «{req.query_value}». Дубликат не создавался."
        )
    return (
        f"Запустил фоновый {mode} в «Мой Арбитр» (задача №{job_id}) по запросу «{req.query_value}». "
        "Воркер будет использовать сохранённую браузерную сессию. Если вход через Госуслуги истёк или ещё не сохранён, "
        "задача попросит ручной вход и не будет хранить пароль."
    )


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
