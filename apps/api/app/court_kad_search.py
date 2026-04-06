from __future__ import annotations

import re
from dataclasses import dataclass

from .case_number import normalize_arbitr_case_number


@dataclass
class CourtSearchRequest:
    query_type: str
    query_value: str
    run_mode: str = "preview"
    parser_year_min: int | None = None
    parser_year_max: int | None = None


def normalize_query_value(value: str) -> str:
    return re.sub(r"\s+", " ", (value or "").strip())


def normalize_case_number(value: str) -> str:
    raw = normalize_query_value(value).replace(" ", "").replace("\\", "")
    return normalize_arbitr_case_number(raw)


def normalize_inn(value: str) -> str:
    return re.sub(r"\D+", "", value or "")


def normalize_ogrn(value: str) -> str:
    return re.sub(r"\D+", "", value or "")


def parse_parser_year_range_from_text(text: str) -> tuple[int | None, int | None]:
    """
    Извлекает период лет из фраз вроде «за 2026 год», «с 2024 по 2026», «2026 год».
    Возвращает (min_year, max_year) или (None, None).
    """
    raw = text or ""
    m = re.search(r"с\s+(\d{4})\s+по\s+(\d{4})", raw, flags=re.IGNORECASE)
    if m:
        y1, y2 = int(m.group(1)), int(m.group(2))
        return (min(y1, y2), max(y1, y2))
    m = re.search(r"(?:за|в)\s+(\d{4})\s*г?", raw, flags=re.IGNORECASE)
    if m:
        y = int(m.group(1))
        return (y, y)
    m = re.search(r"(\d{4})\s*год[ау]?", raw, flags=re.IGNORECASE)
    if m:
        y = int(m.group(1))
        return (y, y)
    return (None, None)


def _with_years(req: CourtSearchRequest, text: str) -> CourtSearchRequest:
    ymin, ymax = parse_parser_year_range_from_text(text)
    if ymin is None:
        return req
    y2 = ymax if ymax is not None else ymin
    return CourtSearchRequest(
        query_type=req.query_type,
        query_value=req.query_value,
        run_mode=req.run_mode,
        parser_year_min=ymin,
        parser_year_max=y2,
    )


def parse_court_search_request(text: str) -> CourtSearchRequest | None:
    raw = normalize_query_value(text)
    lowered = raw.lower()

    m_card_url = re.search(r"(https?://kad\.arbitr\.ru/Card/[a-fA-F0-9\-]+)", raw, flags=re.IGNORECASE)
    if m_card_url:
        return _with_years(
            CourtSearchRequest(query_type="card_url", query_value=m_card_url.group(1).split("?")[0].rstrip("/")),
            raw,
        )

    m_case = re.search(
        r"(?:дел[ауо]?|дела)\s+№?\s*([АA]\d{1,4}-\d{1,7}/\d{2,4}|\d{1,2}-\d{1,7}/\d{2,4})",
        raw,
        flags=re.IGNORECASE,
    )
    case_markers = [
        "скачай документы дела",
        "скачай все документы дела",
        "скачай документы по делу",
        "скачай все документы по делу",
        "скачай материалы дела",
        "скачай все материалы дела",
        "скачай все файлы",
        "скачай файлы",
        "файлы дела",
        "файлы по делу",
        "с сайта арбитражного суда",
        "найди дело",
        "найди и скачай",
        "найди из кад",
        "скачай из кад",
        "поставь на отслеживание дело",
    ]
    if any(marker in lowered for marker in case_markers) and m_case:
        return _with_years(
            CourtSearchRequest(query_type="case_number", query_value=normalize_case_number(m_case.group(1))),
            raw,
        )

    # «Скачай файлы … А40-…/2020 за 2026» (номер без слова «дело»)
    if "скачай" in lowered and re.search(r"(?:за|в)\s+\d{4}", raw, flags=re.IGNORECASE):
        m_num = re.search(
            r"№?\s*([АA]\d{1,4}-\d{1,7}/\d{2,4}|\d{1,2}-\d{1,7}/\d{2,4})",
            raw,
            flags=re.IGNORECASE,
        )
        if m_num:
            return _with_years(
                CourtSearchRequest(query_type="case_number", query_value=normalize_case_number(m_num.group(1))),
                raw,
            )

    m_inn = re.search(r"\bинн\b[:\s]*([\d\s]{10,15})", lowered, flags=re.IGNORECASE)
    if m_inn:
        return _with_years(
            CourtSearchRequest(query_type="inn", query_value=normalize_inn(m_inn.group(1))),
            raw,
        )

    m_ogrn = re.search(r"\bогрн\b[:\s]*([\d\s]{12,18})", lowered, flags=re.IGNORECASE)
    if m_ogrn:
        return _with_years(
            CourtSearchRequest(query_type="ogrn", query_value=normalize_ogrn(m_ogrn.group(1))),
            raw,
        )

    # Участник / ФИО: только вместе с явным запросом к КАД (иначе ложные срабатывания)
    kad_context_markers = (
        "кад",
        "kad.arbitr",
        "арбитраж",
        "найди и скачай",
        "найди из кад",
        "найди в кад",
        "скачай из кад",
        "скачай с кад",
        "скачай все материалы",
        "материалы дела",
        "все материалы дела",
    )
    if any(m in lowered for m in kad_context_markers):
        m_quoted = re.search(
            r"по\s+данным\s+(?:'([^']+)'|\"([^\"]+)\"|«([^»]+)»)",
            raw,
            flags=re.IGNORECASE,
        )
        name_val = ""
        if m_quoted:
            name_val = (m_quoted.group(1) or m_quoted.group(2) or m_quoted.group(3) or "").strip()
        if not name_val:
            m_plain = re.search(
                r"по\s+данным\s+([А-ЯЁ][А-Яа-яЁё]+(?:\s+[А-Яа-яЁё]+){0,5})(?=[\s.!?,;]|$)",
                raw,
                flags=re.IGNORECASE,
            )
            if m_plain:
                name_val = m_plain.group(1).strip()
        if not name_val:
            m_u = re.search(
                r"участник[ауе]?\s+дел[ау]?\s+(?:'([^']+)'|\"([^\"]+)\"|«([^»]+)»|([А-ЯЁ][А-Яа-яЁё]+(?:\s+[А-Яа-яЁё]+){0,5}))",
                raw,
                flags=re.IGNORECASE,
            )
            if m_u:
                name_val = (
                    (m_u.group(1) or m_u.group(2) or m_u.group(3) or m_u.group(4) or "").strip()
                )
        name_val = normalize_query_value(name_val)
        if len(name_val) >= 3:
            return _with_years(
                CourtSearchRequest(query_type="participant_name", query_value=name_val),
                raw,
            )

    org_markers = [
        "по организации",
        "организацию",
        "организации",
        "компанию",
        "по компании",
        "поставь на отслеживание организацию",
    ]
    if any(marker in lowered for marker in org_markers):
        candidate = raw
        for marker in org_markers:
            idx = lowered.find(marker)
            if idx >= 0:
                candidate = raw[idx + len(marker):].strip(" :.-\"«»")
                break
        if candidate:
            return _with_years(
                CourtSearchRequest(query_type="organization_name", query_value=candidate),
                raw,
            )
    return None


def looks_like_court_download_count_question(text: str) -> bool:
    """«Сколько скачали» — короткий ответ по факту, не простыня по задачам."""
    lowered = (text or "").lower()
    if "скачай" in lowered or "найди дел" in lowered or "поставь на отслеживание" in lowered:
        return False
    return any(
        p in lowered
        for p in (
            "сколько документ",
            "сколько файлов",
            "сколько скачано",
            "сколько удалось",
            "сколько успешно",
            "сколько всего скачал",
            "сколько уже скачал",
        )
    )


def looks_like_kad_downloaded_documents_list(text: str) -> bool:
    """Пользователь просит список/названия файлов, сохранённых из КАД — не статус задач."""
    lowered = (text or "").lower()
    if "скачай" in lowered or "найди дел" in lowered or "поставь на отслеживание" in lowered:
        return False
    list_intent = any(
        p in lowered
        for p in (
            "покажи",
            "покажите",
            "выведи",
            "перечисли",
            "список",
            "какие документы",
            "какие файлы",
            "все документы",
            "все файлы",
            "названия файлов",
            "реестр",
            "перечень",
            "открой список",
        )
    )
    if not list_intent:
        return False
    kad_context = any(
        k in lowered
        for k in (
            "кад",
            "kad.arbitr",
            "арбитраж",
            "картотек",
            "из кад",
            "с кад",
            "скачан",
            "скачанн",
            "удалось скачать",
            "удалось сохранить",
            "фонов",
            "загрузк",
        )
    )
    return kad_context


def looks_like_court_download_status_question(text: str) -> bool:
    """Вопросы о ходе/ошибках фоновой загрузки из КАД — развёрнутый статус по задачам."""
    if looks_like_court_download_count_question(text) or looks_like_kad_downloaded_documents_list(text):
        return False
    lowered = (text or "").lower()
    if "скачай" in lowered or "найди дел" in lowered or "поставь на отслеживание" in lowered:
        return False
    if any(
        p in lowered
        for p in (
            "статус скачивания",
            "статус загрузки",
            "статус задачи кад",
            "статус фоновой",
            "как там скачивание",
            "как идёт скачивание",
            "как идет скачивание",
            "как идёт загрузка",
            "как идет загрузка",
            "ты скачал",
            "скачал ли ты",
            "скачал ли",
            "загрузил ли",
            "получилось скачать",
            "удалось скачать",
            "что с загрузкой",
            "документы скачались",
            "скачались ли",
            "бот скачал",
            "воркер скачал",
        )
    ):
        return True
    if "?" in lowered and "документ" in lowered and ("кад" in lowered or "суд" in lowered or "задач" in lowered):
        return True
    return False


def looks_like_court_search_command(text: str) -> bool:
    if looks_like_kad_downloaded_documents_list(text):
        return True
    if looks_like_court_download_count_question(text):
        return True
    if looks_like_court_download_status_question(text):
        return True
    lowered = text.lower()
    if "kad.arbitr.ru" in lowered and "/card/" in lowered:
        return True
    return any(
        marker in lowered
        for marker in [
            "скачай документы дела",
            "скачай все документы дела",
            "скачай документы по делу",
            "скачай все документы по делу",
            "скачай материалы дела",
            "скачай все материалы дела",
            "скачай все файлы",
            "скачай файлы",
            "скачай из кад",
            "скачай с кад",
            "файлы дела",
            "файлы по делу",
            "с сайта арбитражного суда",
            "найди дела по",
            "найди дело",
            "найди и скачай",
            "найди из кад",
            "найди в кад",
            "поставь на отслеживание дело",
            "поставь на отслеживание инн",
            "поставь на отслеживание огрн",
            "поставь на отслеживание организацию",
            "статус синхронизации",
            "статус скачивания",
            "статус загрузки",
            "что нового скачано за ночь",
            "отчет по задаче",
            "отчёт по задаче",
            "список файлов по задаче",
            "вывести список файлов по задаче",
        ]
    )
