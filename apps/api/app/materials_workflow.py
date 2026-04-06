"""
Работа с материалами по делу: черновики процессуальных документов, сравнение текстов, извлечение сроков в задачи.
"""

from __future__ import annotations

import json
import re
from datetime import date
from typing import Any

from sqlalchemy.orm import Session

from .ai_service import llm_system_user
from .config import settings
from .models import Case, CaseEvent, Document, Task

_MAX_DOC_CHARS = 12000
_MAX_COMBINED_CONTEXT = 24000


def parse_document_id_list(text: str, available_ids: set[int]) -> list[int]:
    """Номера документов: [12], документ 3, явные числа из доступных id."""
    found: list[int] = []
    seen: set[int] = set()
    for m in re.finditer(r"\[(\d+)\]|(?:документ|док\.|файл)\s*#?\s*(\d+)", text, re.IGNORECASE):
        g = int(next(x for x in m.groups() if x))
        if g in available_ids and g not in seen:
            seen.add(g)
            found.append(g)
    if not found:
        for m in re.finditer(r"\b(\d{1,6})\b", text):
            i = int(m.group(1))
            if i in available_ids and i not in seen:
                seen.add(i)
                found.append(i)
    return found[:24]


def infer_draft_kind(text: str) -> str:
    t = text.lower()
    pairs = [
        ("отзыв", "отзыв"),
        ("возражен", "возражения"),
        ("ходатайств", "ходатайство"),
        ("жалоб", "жалоба"),
        ("апелляц", "апелляционная жалоба"),
        ("кассац", "кассационная жалоба"),
        ("исков", "исковое заявление"),
        ("заявлени", "заявление"),
    ]
    for key, label in pairs:
        if key in t:
            return label
    return "процессуальный документ"


def looks_like_materials_draft_request(text: str) -> bool:
    t = text.lower()
    if not any(
        k in t
        for k in [
            "составь",
            "составьте",
            "подготовь",
            "подготовьте",
            "напиши",
            "напишите",
            "черновик",
            "сформируй",
            "сформируйте",
        ]
    ):
        return False
    return any(
        k in t
        for k in [
            "отзыв",
            "возражен",
            "ходатайств",
            "жалоб",
            "апелляц",
            "кассац",
            "исков",
            "заявлени",
            "процессуальн",
        ]
    )


def looks_like_compare_documents_request(text: str) -> bool:
    t = text.lower()
    if not any(
        k in t
        for k in [
            "сравни",
            "сравнение",
            "что изменилось",
            "отличия",
            "различия",
            " diff",
            "дифф",
        ]
    ):
        return False
    return (
        "документ" in t
        or "[" in text
        or bool(re.search(r"\b\d+\s+(?:и|с)\s+\d+\b", t))
        or bool(re.search(r"\bдва\s+документ", t))
    )


def looks_like_extract_deadlines_request(text: str) -> bool:
    t = text.lower()
    return any(
        k in t
        for k in [
            "извлеки сроки",
            "сроки из текста",
            "сроки из сообщ",
            "дедлайн из",
            "дедлайны из",
            "поставь задачи по срокам",
            "создай задачи по срокам",
            "создай напоминания по срокам",
            "какие сроки в тексте",
            "выдели сроки",
        ]
    )


def _docs_by_ids(docs: list[Document], ids: list[int]) -> list[Document]:
    by_id = {d.id: d for d in docs}
    return [by_id[i] for i in ids if i in by_id]


def _trim(s: str, n: int) -> str:
    s = (s or "").strip()
    if len(s) <= n:
        return s
    return s[: n - 20] + "\n… [текст обрезан]"


async def handle_materials_draft_request(
    db: Session,
    case: Case,
    all_docs: list[Document],
    text: str,
) -> str:
    if not settings.openai_api_key.strip():
        return "Для черновиков нужен OPENAI_API_KEY в настройках API."

    available = {d.id for d in all_docs}
    ids = parse_document_id_list(text, available)
    if not ids:
        if len(all_docs) == 0:
            return "В деле нет загруженных документов с текстом — сначала добавьте файлы."
        if len(all_docs) <= 5:
            ids = [d.id for d in sorted(all_docs, key=lambda d: d.created_at)[-5:]]
        else:
            return (
                "Укажите номера документов по делу, например: "
                "«Составь отзыв по документам [3], [7] и [12]» — или перечислите: документ 3, 7 и 12."
            )

    selected = _docs_by_ids(all_docs, ids)
    kind = infer_draft_kind(text)
    parts: list[str] = []
    for doc in selected:
        parts.append(f"--- Документ [{doc.id}] {doc.filename} ---\n{_trim(doc.extracted_text or '', _MAX_DOC_CHARS)}")
    bundle = "\n\n".join(parts)
    if len(bundle) > _MAX_COMBINED_CONTEXT:
        bundle = bundle[: _MAX_COMBINED_CONTEXT] + "\n… [контекст обрезан]"

    system = (
        "Ты помощник юриста по оформлению процессуальных материалов. "
        "Пользователь просит структурированный черновик на русском языке. "
        "Не давай юридических консультаций и не оценивай перспективы дела. "
        "Используй только факты из переданных выдержек документов; не выдумывай стороны, даты и суммы. "
        "Если данных не хватает — укажи в конце блок «Нужно уточнить:» с перечнем недостающих сведений. "
        "В начале кратко перечисли, на основе каких файлов (номера в скобках) сделан черновик."
    )
    user = (
        f"Дело: «{case.title}», номер {case.case_number}.\n"
        f"Тип запрошенного документа: {kind}.\n"
        f"Запрос пользователя:\n{text[:2000]}\n\n"
        f"Материалы:\n{bundle}"
    )
    try:
        draft = await llm_system_user(system, user, timeout=120.0)
    except Exception as exc:
        return f"Не удалось сгенерировать черновик: {exc}"
    if not draft.strip():
        return "Модель вернула пустой ответ. Попробуйте сократить число документов или повторить запрос."

    db.add(
        CaseEvent(
            case_id=case.id,
            event_type="materials_draft",
            body=f"[{kind}]\n{draft[:39000]}",
        )
    )
    db.commit()
    return (
        f"Черновик «{kind}» сохранён в деле (событие materials_draft). "
        f"Основан на документах: {', '.join(f'[{i}]' for i in ids)}.\n\n{draft}"
    )


async def handle_compare_documents_request(
    db: Session,
    case: Case,
    all_docs: list[Document],
    text: str,
) -> str:
    if not settings.openai_api_key.strip():
        return "Для сравнения нужен OPENAI_API_KEY."

    available = {d.id for d in all_docs}
    ids = parse_document_id_list(text, available)
    if len(ids) < 2:
        return (
            "Нужны два документа по номерам в этом деле. Пример: "
            "«Сравни документы [12] и [45]» или «сравни документ 3 и 7»."
        )
    a, b = ids[0], ids[1]
    selected = _docs_by_ids(all_docs, [a, b])
    if len(selected) != 2:
        return "Не удалось найти оба документа в текущем деле."
    da, doc_b = selected[0], selected[1]

    ta = _trim(da.extracted_text or "", _MAX_DOC_CHARS)
    tb = _trim(doc_b.extracted_text or "", _MAX_DOC_CHARS)
    system = (
        "Ты помощник для сравнения двух текстовых версий судебных или договорных документов. "
        "Ответь по-русски: 1) краткое резюме отличий; 2) маркированный список существенных изменений "
        "(что добавлено, удалено, изменено по смыслу); 3) если тексты почти совпадают — так и напиши. "
        "Не придумывай факты, опирайся только на переданные тексты."
    )
    user = (
        f"Дело: «{case.title}».\n"
        f"Документ A [{da.id}] {da.filename}:\n{ta}\n\n"
        f"Документ B [{doc_b.id}] {doc_b.filename}:\n{tb}"
    )
    try:
        out = await llm_system_user(system, user, timeout=120.0)
    except Exception as exc:
        return f"Не удалось сравнить: {exc}"
    if not out.strip():
        return "Пустой ответ модели."

    db.add(
        CaseEvent(
            case_id=case.id,
            event_type="materials_compare",
            body=f"Сравнение [{a}] vs [{b}]:\n{out[:39000]}",
        )
    )
    db.commit()
    return f"Сравнение документов [{a}] и [{b}] (сохранено в деле).\n\n{out}"


def _parse_iso_date(raw: str | None) -> date | None:
    if not raw or not str(raw).strip():
        return None
    s = str(raw).strip()[:32]
    try:
        return date.fromisoformat(s[:10])
    except ValueError:
        return None


async def handle_extract_deadlines_request(db: Session, case: Case, text: str) -> str:
    if not settings.openai_api_key.strip():
        return "Для извлечения сроков нужен OPENAI_API_KEY."

    system = (
        "Ты извлекаешь из текста юриста сроки, дедлайны и обязанности с датами. "
        "Верни ТОЛЬКО валидный JSON без markdown и пояснений:\n"
        '{"tasks":[{"title":"краткое название задачи","due_date":"YYYY-MM-DD или null","details":"1 строка контекста"}]}\n'
        "Если даты нет в тексте — due_date: null. Не выдумывай даты. "
        "Не больше 12 задач. title — до 200 символов."
    )
    user = f"Дело: «{case.title}» ({case.case_number}).\n\nТекст:\n{text[:12000]}"
    try:
        raw = await llm_system_user(system, user, timeout=90.0)
    except Exception as exc:
        return f"Не удалось разобрать сроки: {exc}"

    payload: dict[str, Any] = {}
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        m = re.search(r"\{[\s\S]*\}", raw)
        if m:
            try:
                payload = json.loads(m.group(0))
            except json.JSONDecodeError:
                payload = {}
    tasks_raw = payload.get("tasks") if isinstance(payload, dict) else None
    if not isinstance(tasks_raw, list) or not tasks_raw:
        return (
            "Не удалось извлечь структурированные сроки (ожидался JSON с полем tasks). "
            f"Сырой ответ модели:\n{raw[:1500]}"
        )

    created = 0
    lines: list[str] = []
    for item in tasks_raw[:12]:
        if not isinstance(item, dict):
            continue
        title = str(item.get("title") or "").strip()[:200]
        if not title:
            continue
        due = _parse_iso_date(item.get("due_date"))
        details = str(item.get("details") or "").strip()[:2000]
        task = Task(
            case_id=case.id,
            title=title,
            description=details or "Создано из извлечения сроков по тексту в чате",
            priority="high" if due else "medium",
            status="open",
            due_date=due,
        )
        db.add(task)
        created += 1
        lines.append(f"- {title}" + (f" → до {due.isoformat()}" if due else ""))

    db.add(
        CaseEvent(
            case_id=case.id,
            event_type="materials_deadlines",
            body=f"Извлечено задач: {created}\n" + "\n".join(lines)[:8000],
        )
    )
    db.commit()

    if created == 0:
        return "Модель не вернула задач с непустыми названиями. Уточните текст или повторите запрос."
    return (
        f"Создано задач: {created}. Событие сохранено в деле (materials_deadlines).\n"
        + "\n".join(lines)
    )
