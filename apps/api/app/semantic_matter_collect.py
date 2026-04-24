"""Сбор документов из всех папок в целевое дело по смыслу текста и номерам (LLM)."""

from __future__ import annotations

import json
import re
from typing import Any

from sqlalchemy.orm import Session

from .ai_service import llm_system_user
from .case_number import arbitr_case_number_lookup_keys, normalize_arbitr_case_number
from .config import settings
from .models import Case, CaseTag, Conversation, Document, PendingMovePlan


def _strip_json_fence(raw: str) -> str:
    s = (raw or "").strip()
    m = re.search(r"```(?:json)?\s*([\s\S]*?)```", s, re.IGNORECASE)
    if m:
        return m.group(1).strip()
    return s


def _doc_snippet(doc: Document, limit: int = 480) -> str:
    t = (doc.extracted_text or "").strip()
    t = re.sub(r"\s+", " ", t)[:limit]
    return t if t else "(текст не извлечён)"


def looks_like_semantic_matter_collect_request(text: str) -> bool:
    """Перенос по смыслу/контексту во целевую папку со всех остальных."""
    t = (text or "").lower()
    triggers = (
        "отсортируй",
        "отсортир",
        "по смыслу",
        "по контекст",
        "самостоятельно",
        "относящиеся к делу",
        "относящиеся к папк",
        "все что относится",
        "всё что относится",
        "всех что относится",
        "оставь только документ",
        "оставь в папке только",
        "собери все документ",
        "соберите все документ",
        "консолидир",
        "сверни в одну папку",
        "в одну папку по делу",
        "по номеру дел",
        "по номерам дел",
    )
    if not any(x in t for x in triggers):
        return False
    if not any(x in t for x in ("документ", "файл", "материал", "архив", "пдф", "pdf")):
        return False
    if "содержащ" in t and "создай папк" in t:
        return False
    return True


def resolve_target_case_for_collect(
    db: Session,
    conversation: Conversation,
    text: str,
) -> Case | None:
    from .main import find_case_by_hint, parse_collect_folder_title

    t = (text or "").lower()
    if any(
        k in t
        for k in (
            "текущ",
            "эта папка",
            "это дело",
            "открытую папку",
            "активн",
            "эту папку",
        )
    ):
        if conversation.active_case_id:
            c = db.query(Case).filter(Case.id == conversation.active_case_id).first()
            if c:
                return c
    title = parse_collect_folder_title(text)
    if title:
        return find_case_by_hint(db.query(Case).all(), title, db=db)
    if conversation.active_case_id:
        return db.query(Case).filter(Case.id == conversation.active_case_id).first()
    return None


def _target_profile_lines(db: Session, target: Case) -> str:
    tags = db.query(CaseTag).filter(CaseTag.case_id == target.id).limit(24).all()
    tag_line = ", ".join(f"{tg.kind}:{tg.value}" for tg in tags) or "нет"
    keys = ", ".join(arbitr_case_number_lookup_keys(target.case_number)) or target.case_number
    return (
        f"Название папки: «{target.title}»\n"
        f"Номер дела в карточке: {target.case_number}\n"
        f"Варианты номера для сопоставления: {keys}\n"
        f"Теги и алиасы: {tag_line}"
    )


async def _llm_classify_batch(
    *,
    target: Case,
    target_profile: str,
    user_instruction: str,
    batch: list[tuple[Document, Case]],
) -> dict[int, tuple[bool, str]]:
    if not settings.openai_api_key.strip() or not batch:
        return {}
    lines: list[str] = []
    for doc, src_case in batch:
        lines.append(
            f"- document_id={doc.id} | сейчас: «{src_case.title}» ({src_case.case_number}) "
            f"| файл: {doc.filename}\n  фрагмент: {_doc_snippet(doc)}"
        )
    system = (
        "Ты помощник по судебному архиву. Нужно решить, относится ли каждый документ **к тому же делу/истории**, "
        "что и **целевая папка** (банкротство, цепочка процессов вокруг одного лица и т.д.).\n"
        "Смотри номер дела во фрагменте и в имени файла, стороны, предмет, связь с номером целевой папки.\n"
        "Если документ явно относится к **другому** самостоятельному делу (другой базовый номер без связи с целевым) — "
        "`move_to_target`: false.\n"
        "Если неясно или мало текста — консервативно false.\n"
        "Верни **только JSON**: "
        '{"decisions":[{"document_id":число,"move_to_target":true/false,"reason":"кратко по-русски"}]}'
    )
    user_block = (
        f"{target_profile}\n\n"
        f"Запрос пользователя:\n{user_instruction[:1200]}\n\n"
        "Кандидаты:\n" + "\n".join(lines)
    )
    raw = await llm_system_user(system, user_block, timeout=140.0, max_tokens=3500)
    if not raw.strip():
        return {}
    try:
        data: dict[str, Any] = json.loads(_strip_json_fence(raw))
    except json.JSONDecodeError:
        return {}
    allowed = {doc.id for doc, _ in batch}
    out: dict[int, tuple[bool, str]] = {}
    for row in data.get("decisions") or []:
        if not isinstance(row, dict):
            continue
        try:
            did = int(row.get("document_id"))
        except (TypeError, ValueError):
            continue
        if did not in allowed:
            continue
        move = bool(row.get("move_to_target"))
        reason = str(row.get("reason") or "").strip()[:350]
        out[did] = (move, reason)
    return out


async def preview_semantic_collect_into_case(
    db: Session,
    conversation: Conversation,
    text: str,
    *,
    max_candidates: int = 220,
    batch_size: int = 11,
) -> tuple[str, Case | None]:
    if not settings.openai_api_key.strip():
        return (
            "Для сортировки **по смыслу** нужен LLM (OPENAI_API_KEY). "
            "Или используйте перенос по ключевым словам: «Создай папку … перенеси документы, содержащие: …».",
            None,
        )

    target = resolve_target_case_for_collect(db, conversation, text)
    if not target:
        return (
            "Укажите целевую папку в кавычках, например: "
            "«отсортируй документы и собери всё по делу в папку «Банкротство Эмиль»» "
            "или откройте нужное дело слева и повторите запрос с формулировкой «в текущую папку».",
            None,
        )

    profile = _target_profile_lines(db, target)
    all_rows = (
        db.query(Document, Case)
        .join(Case, Case.id == Document.case_id)
        .filter(Document.case_id != target.id)
        .order_by(Document.id.asc())
        .limit(max_candidates + 5)
        .all()
    )
    candidates: list[tuple[Document, Case]] = [(d, c) for d, c in all_rows][:max_candidates]
    if not candidates:
        return (
            f'В других папках нет документов для переноса в «{target.title}» ({target.case_number}) — всё уже здесь или архив пуст.',
            target,
        )

    decisions: dict[int, tuple[bool, str]] = {}
    for i in range(0, len(candidates), batch_size):
        part = await _llm_classify_batch(
            target=target,
            target_profile=profile,
            user_instruction=text,
            batch=candidates[i : i + batch_size],
        )
        decisions.update(part)

    to_move: list[Document] = []
    reasons: dict[int, str] = {}
    for doc, _src in candidates:
        if doc.id not in decisions:
            continue
        move, reason = decisions[doc.id]
        if move:
            to_move.append(doc)
            reasons[doc.id] = reason

    if not to_move:
        return (
            "По смыслу текста **не нашлось** документов в других папках, которые можно уверенно отнести к этой карточке. "
            "Проверьте распознавание PDF или уточните формулировку (ФИО, номер дела).",
            target,
        )

    db.query(PendingMovePlan).filter(PendingMovePlan.case_id == target.id).delete()
    db.add(
        PendingMovePlan(
            case_id=target.id,
            title=target.title,
            keywords_json=json.dumps(
                ["__semantic_collect__", normalize_arbitr_case_number(target.case_number)],
                ensure_ascii=False,
            ),
            doc_ids_json=json.dumps([d.id for d in to_move], ensure_ascii=False),
        )
    )
    db.commit()

    lines: list[str] = [
        f'**Семантический сбор** в папку «{target.title}» ({target.case_number}).',
        "",
        "Проанализированы документы из **других** папок (не из целевой). Ниже те, что модель считает относящимися к этому делу по тексту и контексту.",
        f"Кандидатов просмотрено: {len(candidates)}; к переносу отобрано: **{len(to_move)}**.",
        "",
        "Проверьте список и ответьте: `Да, перенеси все` или `Да, перенеси все, кроме 3, 7`",
        "",
    ]
    for idx, doc in enumerate(to_move[:55], start=1):
        why = reasons.get(doc.id, "")
        if len(why) > 160:
            why = why[:158] + "…"
        lines.append(f"{idx}. [{doc.id}] {doc.filename} — _{why}_")
    if len(to_move) > 55:
        lines.append(f"... и ещё {len(to_move) - 55}.")
    if len(candidates) >= max_candidates:
        lines.append("")
        lines.append(
            f"_(Просмотрено не более {max_candidates} документов вне целевой папки; при необходимости повторите после переноса.)_"
        )
    return "\n".join(lines), target
