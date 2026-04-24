"""Сквозная хронология по теме/лицу через все папки (дела): поиск документов и связное повествование."""

from __future__ import annotations

import json
import re
from datetime import date
from typing import Any

from sqlalchemy.orm import Session

from .ai_service import llm_system_user
from .config import settings
from .models import Case, Document


def _strip_json_fence(raw: str) -> str:
    s = (raw or "").strip()
    m = re.search(r"```(?:json)?\s*([\s\S]*?)```", s, re.IGNORECASE)
    if m:
        return m.group(1).strip()
    return s


def _fallback_matter_hints(text: str) -> list[str]:
    from .main import _extract_delete_target_phrases, extract_case_hint_from_folder_phrase

    out: list[str] = []
    seen: set[str] = set()

    def add(s: str) -> None:
        v = (s or "").strip().strip(".,;:")
        if len(v) < 3:
            return
        k = v.lower()
        if k in seen:
            return
        seen.add(k)
        out.append(v)

    for p in _extract_delete_target_phrases(text):
        add(p)
    fh = (extract_case_hint_from_folder_phrase(text or "") or "").strip()
    if fh:
        add(fh)
    for a, b in re.findall(r'"([^"]+)"|«([^»]+)»', text or ""):
        add((a or b).strip())
    for pat in (
        r"банкротств[аео]?\s+([А-ЯЁа-яё][А-ЯЁа-яё'\-\s]{4,120}?)(?=\s*[.,;!?\n]|$)",
        r"по\s+делу\s+банкротств[аео]?\s+([А-ЯЁа-яё][А-ЯЁа-яё'\-\s]{4,120}?)(?=\s*[.,;!?\n]|$)",
        r"делу\s+банкротств[аео]?\s+([А-ЯЁа-яё][А-ЯЁа-яё'\-\s]{4,120}?)(?=\s*[.,;!?\n]|$)",
    ):
        m = re.search(pat, text or "", re.I)
        if m:
            add(m.group(1).strip())
    return out


async def extract_matter_search_hints(user_message: str) -> list[str]:
    phrases: list[str] = []
    seen: set[str] = set()

    def add(s: str) -> None:
        v = (s or "").strip()
        if len(v) < 3:
            return
        k = v.lower()
        if k in seen:
            return
        seen.add(k)
        phrases.append(v)

    for p in _fallback_matter_hints(user_message):
        add(p)

    if settings.openai_api_key.strip():
        system = (
            "Из сообщения пользователя выдели короткие поисковые фразы для нахождения PDF/документов в архиве "
            "(ФИО в разных формах, только фамилия, инициалы с фамилией, название организации, редкие идентификаторы). "
            "Игнорируй служебные слова вроде «дай», «расклад», «все папки». "
            "Верни только JSON: {\"phrases\":[\"...\", ...]} — от 2 до 10 фраз, без текста вне JSON."
        )
        raw = await llm_system_user(system, (user_message or "")[:4500], timeout=55.0)
        if raw.strip():
            try:
                data: dict[str, Any] = json.loads(_strip_json_fence(raw))
                for p in data.get("phrases") or []:
                    add(str(p).strip())
            except json.JSONDecodeError:
                pass
    return phrases


def _earliest_date_in_doc(doc: Document) -> date | None:
    blob = f"{doc.filename}\n{doc.extracted_text or ''}"[:12000]
    found: list[date] = []
    for m in re.finditer(r"\b(\d{1,2})\.(\d{1,2})\.(\d{2,4})\b", blob):
        day, month, yraw = int(m.group(1)), int(m.group(2)), m.group(3)
        year = int(yraw)
        if year < 100:
            year += 2000
        try:
            found.append(date(year, month, day))
        except ValueError:
            continue
    return min(found) if found else None


def _sort_docs_timeline(docs: list[Document]) -> list[Document]:
    def key(d: Document) -> tuple[date, date, int]:
        ed = _earliest_date_in_doc(d)
        ca = d.created_at.date() if d.created_at else date(1970, 1, 1)
        primary = ed or ca
        return (primary, ca, d.id)

    return sorted(docs, key=key)


def _collect_documents_union(db: Session, hints: list[str]) -> list[Document]:
    from .main import _collect_documents_matching_delete_hints

    collected: dict[int, Document] = {}
    for h in hints:
        h = (h or "").strip()
        if len(h) < 3:
            continue
        for d in _collect_documents_matching_delete_hints(db, [h]):
            collected[d.id] = d
    return list(collected.values())


def _format_doc_bundle_for_llm(
    docs: list[Document],
    cases_map: dict[int, Case],
    *,
    start_index: int = 1,
) -> str:
    parts: list[str] = []
    for i, doc in enumerate(docs, start=start_index):
        c = cases_map.get(doc.case_id)
        cnum = c.case_number if c else "?"
        ctitle = c.title if c else "?"
        frag = (doc.extracted_text or "").strip()
        frag = re.sub(r"\s+", " ", frag)[:650]
        if not frag:
            frag = "(текст не извлечён — ориентируйся на имя файла)"
        parts.append(
            f"[{i}] Папка: «{ctitle}» ({cnum}) | Файл: {doc.filename}\n"
            f"Загружен в систему: {doc.created_at.isoformat() if doc.created_at else '?'}\n"
            f"Фрагмент: {frag}"
        )
    return "\n\n".join(parts)


async def build_cross_folder_matter_narrative(db: Session, user_message: str) -> str:
    hints = await extract_matter_search_hints(user_message)
    if not hints:
        return (
            "Не удалось понять, о ком или о чём искать по всем папкам. "
            "Напишите, например: Дай полный расклад по банкротству Касумов Эмиль Алиевич "
            "или по делу Банкротство Эмиль — кавычки не обязательны."
        )

    docs = _collect_documents_union(db, hints)
    if not docs:
        return (
            f"По фразам «{'», «'.join(hints[:6])}» в документах всех папок ничего не нашлось. "
            "Проверьте написание ФИО или загрузите PDF с распознанным текстом."
        )

    docs = _sort_docs_timeline(docs)
    total_found = len(docs)
    max_in_prompt = 72
    trimmed = docs[:max_in_prompt]
    skipped = total_found - len(trimmed)

    case_ids = {d.case_id for d in trimmed}
    cases_map = {c.id: c for c in db.query(Case).filter(Case.id.in_(case_ids)).all()}

    bundle = _format_doc_bundle_for_llm(trimmed, cases_map)
    folders_line = ", ".join(
        f"«{cases_map[cid].title}» ({cases_map[cid].case_number})"
        for cid in sorted(case_ids, key=lambda x: (cases_map[x].case_number or ""))
    )

    header = (
        f"Запрос: {user_message.strip()[:500]}\n"
        f"Поисковые фразы: {', '.join(hints[:10])}\n"
        f"Найдено документов: {total_found} в {len(case_ids)} папках.\n"
        f"Папки: {folders_line}\n"
    )
    if skipped > 0:
        header += f"В анализ переданы первые {len(trimmed)} документов по хронологии (ещё {skipped} не вошли — уточните запрос).\n"

    if not settings.openai_api_key.strip():
        lines = [
            header,
            "LLM не настроен — ниже сухой список в порядке ориентировочной хронологии:",
            "",
        ]
        for i, doc in enumerate(trimmed, start=1):
            c = cases_map.get(doc.case_id)
            lines.append(
                f"{i}. [{doc.id}] {doc.filename} — «{c.title if c else '?'}» ({c.case_number if c else '?'})"
            )
        return "\n".join(lines)

    system = (
        "Ты помощник по архиву судебных материалов. По фрагментам из РАЗНЫХ папок (разные номера дел) "
        "собери одну связную хронологическую историю по запросу пользователя (часто — банкротство или цепочка споров вокруг одного лица).\n"
        "Строгие правила:\n"
        "1) Используй только факты, которые прямо следуют из фрагментов или имён файлов. Не выдумывай даты, суммы, решения и участников.\n"
        "2) Выровняй повествование по времени. Если дата в тексте неясна, осторожно пометь это («дата в материалах не выделена») и опирайся на дату загрузки только как слабый ориентир.\n"
        "3) В ключевых пунктах указывай источник: номер из списка [n], имя файла и папку (номер дела).\n"
        "4) Если фрагменты разрозненные или противоречивы — прямо скажи, чего не хватает.\n"
        "5) Пользователь просит «полную картину» и допускает эмоциональный тон: можно мягко передать тяжесть ситуации "
        "**только через перечисление фактов** (отказы, срывы сроков, конкурсная масса и т.д.), без мелодрамы и без юридических оценок «кто прав».\n"
        "6) Объём — развёрнутый: несколько секций с подзаголовками по этапам, если данные позволяют.\n"
        "7) В конце кратко перечисли, каких типов документов в выборке не видно (если это заметно)."
    )

    user_block = header + "\nДокументы и фрагменты:\n\n" + bundle

    try:
        story = await llm_system_user(
            system,
            user_block,
            timeout=200.0,
            max_tokens=9000,
        )
    except Exception as exc:
        story = f"Модель недоступна ({exc}). Список документов по времени:\n\n" + _format_doc_bundle_for_llm(
            trimmed, cases_map
        )

    if not (story or "").strip():
        story = "Модель вернула пустой ответ. Ниже сырые фрагменты:\n\n" + bundle

    appendix = (
        f"\n\n---\n**Опора:** {total_found} документ(ов), папок: {len(case_ids)}. "
        f"Идентификаторы в выборке: {', '.join(str(d.id) for d in trimmed[:35])}"
        + (f" … +{len(trimmed) - 35}" if len(trimmed) > 35 else "")
        + "."
    )
    return (story or "").strip() + appendix
