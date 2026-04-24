"""Сбор документов из всех папок в целевое дело по смыслу текста и номерам (LLM)."""

from __future__ import annotations

import json
import re
from collections import defaultdict
from typing import Any

from sqlalchemy.orm import Session

from .ai_service import llm_system_user
from .case_number import arbitr_case_number_lookup_keys, normalize_arbitr_case_number
from .config import settings
from .models import Case, CaseEvent, CaseTag, Conversation, Document, PendingMovePlan


def _strip_json_fence(raw: str) -> str:
    s = (raw or "").strip()
    m = re.search(r"```(?:json)?\s*([\s\S]*?)```", s, re.IGNORECASE)
    if m:
        return m.group(1).strip()
    return s


def _doc_snippet(doc: Document, limit: int = 720) -> str:
    t = (doc.extracted_text or "").strip()
    t = re.sub(r"\s+", " ", t)[:limit]
    return t if t else "(текст не извлечён)"


def _normalize_quotes(s: str) -> str:
    """«Умные» и типографские кавычки → обычные, чтобы парсер не ломался."""
    return (
        (s or "")
        .replace("\u201c", '"')
        .replace("\u201d", '"')
        .replace("\u201e", '"')
        .replace("\u00ab", "«")
        .replace("\u00bb", "»")
    )


def _all_quoted_chunks(text: str) -> list[str]:
    t = _normalize_quotes(text or "")
    out: list[str] = []
    for a, b in re.findall(r'«([^»]+)»|"([^"]+)"', t):
        chunk = (a or b).strip()
        if len(chunk) >= 2:
            out.append(chunk)
    for m in re.finditer(r"'([^']{2,})'", t):
        out.append(m.group(1).strip())
    return out


_VERB_AFTER_I = re.compile(
    r"^\s*(?:напиши|отправь|создай|покажи|дай|сделай|скажи|сообщи|добавь|удали|повтори|уточни)",
    re.IGNORECASE,
)


def _trim_unquoted_hint_fragment(raw: str) -> str:
    s = (raw or "").strip().strip("\"'«»")
    s = re.sub(r"\s+", " ", s)
    for sep in (" и ", " или "):
        if sep in s:
            left, right = s.split(sep, 1)
            if _VERB_AFTER_I.match(right or ""):
                s = left.strip()
                break
    parts = s.split()
    if len(parts) > 12:
        s = " ".join(parts[:12])
    if len(s) > 120:
        s = s[:120].rsplit(" ", 1)[0]
    return s.strip()


def _unquoted_collect_target_hints(t: str) -> list[str]:
    """Название цели без кавычек: в папку / в дело (в порядке появления)."""
    hints: list[str] = []
    dest_patterns = (
        r"перенеси(?:те)?[\s\S]{0,520}?\bв\s+папк[уеиоа]\s+([^.!?\n]+)",
        r"собери(?:те)?[\s\S]{0,520}?\bв\s+папк[уеиоа]\s+([^.!?\n]+)",
        r"\bв\s+папк[уеиоа]\s+([^.!?\n]+)",
        r"\bв\s+дело\s+([^.!?\n]+)",
    )
    for pat in dest_patterns:
        for m in re.finditer(pat, t, flags=re.IGNORECASE):
            h = _trim_unquoted_hint_fragment(m.group(1))
            if len(h) >= 2:
                hints.append(h)
    return hints


def _unquoted_relation_target_hints(t: str) -> list[str]:
    """по делу / к делу / относящиеся к делу — если явной цели «в папку» нет."""
    hints: list[str] = []
    for pat in (
        r"\bпо\s+делу\s+([^.!?\n]+)",
        r"\bк\s+делу\s+([^.!?\n]+)",
        r"\bотносящ(?:иеся)?\s+к\s+делу\s+([^.!?\n]+)",
    ):
        for m in re.finditer(pat, t, flags=re.IGNORECASE):
            h = _trim_unquoted_hint_fragment(m.group(1))
            if len(h) >= 2:
                hints.append(h)
    return hints


def _unquoted_source_from_prosmotr(text: str) -> str:
    t = _normalize_quotes(text or "")
    m = re.search(
        r"просмотр(?:и|ите)\s+(?:всю\s+)?папк[уеиоа]\s+([^.!?\n,;:]+)",
        t,
        flags=re.IGNORECASE,
    )
    if not m:
        return ""
    return _trim_unquoted_hint_fragment(m.group(1))


def parse_semantic_collect_target_hint(text: str) -> str:
    """
    Целевая папка: явное «в папку …» (с кавычками или без), иначе последняя кавычка,
    иначе «по делу …» / «к делу …» без кавычек.
    """
    t = _normalize_quotes(text or "")
    for pat in (
        r'в\s+папк[уеиоа]\s+["«]([^"»]+)["»]',
        r'в\s+дело\s+["«]([^"»]+)["»]',
        r'перенеси(?:те)?[^.!?\n]*?\s+в\s+папк[уеиоа]\s+["«]([^"»]+)["»]',
        r'собери(?:те)?[^.!?\n]*?\s+в\s+папк[уеиоа]\s+["«]([^"»]+)["»]',
    ):
        m = re.search(pat, t, flags=re.IGNORECASE | re.DOTALL)
        if m:
            return m.group(1).strip()
    udest = _unquoted_collect_target_hints(t)
    if udest:
        return udest[-1]
    chunks = _all_quoted_chunks(t)
    if chunks:
        return chunks[-1].strip()
    urel = _unquoted_relation_target_hints(t)
    if urel:
        return urel[-1]
    return ""


def resolve_optional_source_case_only(
    db: Session,
    text: str,
    target: Case,
) -> Case | None:
    """Ограничить разбор одной папкой: две кавычки, «просмотри папку …» или номер до «в папку»."""
    from .main import extract_move_source_case_number, find_case_by_hint

    all_cases = db.query(Case).all()

    chunks = _all_quoted_chunks(text or "")
    if len(chunks) >= 2:
        first = chunks[0].strip()
        last = chunks[-1].strip()
        if first.lower() != last.lower():
            src = find_case_by_hint(all_cases, first, db=db)
            if src and src.id != target.id:
                return src

    pro = _unquoted_source_from_prosmotr(text or "")
    if pro:
        src = find_case_by_hint(all_cases, pro, db=db)
        if src and src.id != target.id:
            return src

    raw_num = extract_move_source_case_number(text or "")
    if raw_num:
        src = db.query(Case).filter(Case.case_number == raw_num).first()
        if src and src.id != target.id:
            return src
    return None


def wants_semantic_collect_preview_only(text: str) -> bool:
    """Явный запрос только показать кандидатов без переноса."""
    t = (text or "").lower()
    if "не только список" in t or "не только покажи" in t:
        return False
    return any(
        m in t
        for m in (
            "только список",
            "только покажи",
            "без переноса",
            "не переноси пока",
            "не переносить пока",
            "сначала покажи",
            "сначала список",
            "покажи кандидат",
            "только кандидат",
            "предпросмотр",
            "без автоматического переноса",
        )
    )


_TAG_KIND_ORDER = {"participant": 0, "judge": 1, "alias": 2, "keyword": 3}

_STOP_TOKENS = frozenset(
    {
        "банк",
        "суд",
        "дело",
        "год",
        "копия",
        "лист",
        "страница",
        "город",
        "улица",
        "номер",
        "дата",
        "москва",
        "россия",
    }
)


def _load_case_tags_for_collect(db: Session, case_id: int, *, limit: int = 120) -> list[CaseTag]:
    rows = (
        db.query(CaseTag)
        .filter(CaseTag.case_id == case_id)
        .order_by(CaseTag.id.asc())
        .limit(limit)
        .all()
    )
    rows.sort(key=lambda t: (_TAG_KIND_ORDER.get(t.kind, 9), (t.value or "").lower()))
    return rows


def _tokens_from_tag_value(value: str) -> list[str]:
    out: list[str] = []
    for part in re.split(r"[\s,;]+", (value or "").strip()):
        w = re.sub(r"[^А-ЯЁа-яёA-Za-z\-]", "", part)
        wl = w.lower()
        if len(wl) >= 4 and wl not in _STOP_TOKENS:
            out.append(wl)
    return out


def _ru_token_in_blob(blob_lc: str, word: str) -> bool:
    if len(word) < 4:
        return False
    if word in blob_lc:
        return True
    if len(word) >= 5:
        stem = word.rstrip("аяуюоеёиыь")
        if len(stem) >= 4 and stem in blob_lc:
            return True
    return False


def _doc_matches_case_tags(doc: Document, tags: list[CaseTag]) -> tuple[bool, str]:
    """Совпадение с участниками, алиасами, судьями и длинными ключевыми фразами из карточки."""
    if not tags:
        return False, ""
    blob = f"{doc.filename}\n{(doc.extracted_text or '')[:14000]}"
    blob_lc = blob.lower()

    for t in tags:
        if t.kind != "keyword":
            continue
        v = (t.value or "").strip()
        if len(v) >= 10 and v.lower() in blob_lc:
            shown = f"{v[:70]}…" if len(v) > 70 else v
            return True, f"в материале есть ключевая фраза из карточки ({shown})"

    participant_like = [t for t in tags if t.kind in ("participant", "alias", "judge")]
    if not participant_like:
        participant_like = [t for t in tags if t.kind == "keyword"]

    hits = 0
    names: list[str] = []
    for t in participant_like:
        toks = _tokens_from_tag_value(t.value)
        matched = False
        for tok in toks[:8]:
            if _ru_token_in_blob(blob_lc, tok):
                matched = True
                break
        if matched:
            hits += 1
            names.append((t.value or "").strip()[:55])

    n_pl = len(participant_like)
    need = 2 if n_pl >= 3 else 1
    if hits >= need:
        tail = ", ".join(names[:4])
        return True, f"совпадение лиц/участников из карточки ({hits} из {n_pl}): {tail}"

    return False, ""


def _doc_matches_case_numbers(doc: Document, case: Case | None) -> bool:
    """Номер дела из карточки встречается в имени файла или начале текста PDF."""
    if not case:
        return False
    cn = (case.case_number or "").strip()
    if not cn or cn == "UNSORTED":
        return False
    keys = [k for k in arbitr_case_number_lookup_keys(cn) if k and len(str(k).replace(" ", "")) >= 4]
    if not keys:
        keys = [normalize_arbitr_case_number(cn)]
    blob = f"{doc.filename}\n{(doc.extracted_text or '')[:4000]}"
    blob_nospace = re.sub(r"[\s_]+", "", blob.upper())
    for k in keys:
        ku = str(k).upper().replace(" ", "")
        if len(ku) < 4:
            continue
        if ku in blob.upper().replace(" ", "") or ku in blob_nospace:
            return True
    return False


def _heuristic_semantic_move(
    doc: Document,
    target: Case,
    source_only: Case | None,
    target_tags: list[CaseTag],
) -> tuple[bool, str]:
    if _doc_matches_case_numbers(doc, target):
        return True, "совпадение номера дела с целевой папкой"
    if source_only and _doc_matches_case_numbers(doc, source_only):
        return True, "в материале тот же номер, что у исходной папки"
    ok_t, why_t = _doc_matches_case_tags(doc, target_tags)
    if ok_t:
        return True, why_t
    return False, ""


def _execute_semantic_moves(db: Session, target: Case, docs: list[Document]) -> int:
    """Перенос без PendingMovePlan (сразу после отбора)."""
    n = 0
    for doc in docs:
        old_id = doc.case_id
        if old_id == target.id:
            continue
        doc.case_id = target.id
        db.add(
            CaseEvent(
                case_id=target.id,
                event_type="document_reclassified",
                body=f'Документ "{doc.filename}" перенесён автоматически (семантический сбор).',
            )
        )
        db.add(
            CaseEvent(
                case_id=old_id,
                event_type="document_reclassified",
                body=f'Документ "{doc.filename}" перенесён в «{target.title}» (семантический сбор).',
            )
        )
        n += 1
    if n:
        db.commit()
    return n


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
        "перенеси подходящ",
        "перенесите подходящ",
        "просмотри всю папку",
        "просмотри папку",
        "просмотрите папку",
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
    title = parse_semantic_collect_target_hint(text)
    if not title:
        title = parse_collect_folder_title(text)
    if title:
        return find_case_by_hint(db.query(Case).all(), title, db=db)
    if conversation.active_case_id:
        return db.query(Case).filter(Case.id == conversation.active_case_id).first()
    return None


def _target_profile_lines(target: Case, tags: list[CaseTag]) -> str:
    keys = ", ".join(arbitr_case_number_lookup_keys(target.case_number)) or target.case_number
    blocks: list[str] = [
        f"Название папки: «{target.title}»",
        f"Суд (из карточки): {target.court_name or '—'}",
        f"Номер дела в карточке: {target.case_number}",
        f"Варианты номера для сопоставления: {keys}",
    ]
    summary = (target.summary or "").strip()
    if summary:
        one_line = re.sub(r"\s+", " ", summary)[:2000]
        blocks.append(f"Сводка / суть дела (из карточки):\n{one_line}")

    by_kind: dict[str, list[str]] = defaultdict(list)
    for tg in tags:
        by_kind[tg.kind or "keyword"].append((tg.value or "").strip())

    if by_kind["participant"]:
        blocks.append(
            "Участники и ключевые лица (те же ФИО могут встречаться в материалах с **другими номерами дел**):\n"
            + "\n".join(f"- {v}" for v in by_kind["participant"][:45])
        )
    if by_kind["judge"]:
        blocks.append(
            "Судьи (ориентир; в смежных процессах состав может отличаться):\n"
            + "\n".join(f"- {v}" for v in by_kind["judge"][:20])
        )
    if by_kind["alias"]:
        blocks.append("Алиасы и варианты имён:\n" + "\n".join(f"- {v}" for v in by_kind["alias"][:30]))
    if by_kind["keyword"]:
        blocks.append(
            "Ключевые слова и темы:\n" + "\n".join(f"- {v}" for v in by_kind["keyword"][:40])
        )
    if not tags:
        blocks.append("Теги в карточке не заданы — ориентируйся на название, номер и сводку.")

    return "\n\n".join(blocks)


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
        "Ты помощник по судебному архиву. Нужно решить, относится ли каждый документ **к той же истории дел**, "
        "что и **целевая папка** (одно банкротство / одни и те же стороны / та же экономическая суть).\n"
        "Сопоставляй не только **номер дела** в тексте и имени файла, но и:\n"
        "- **участников** из карточки (должник, кредиторы, представители — ФИО в разных падежах);\n"
        "- **судей** (фамилия может совпадать или отличаться в связанных заседаниях);\n"
        "- **суть и контекст** из сводки целевой папки (банкротство того же лица, те же споры).\n"
        "Разные **номера дел** (А40-…, А41-…) не означают автоматически «чужой документ», если те же люди и та же история.\n"
        "Если документ явно про **другое лицо** или **иное производство без связи** с участниками целевой папки — "
        "`move_to_target`: false.\n"
        "Если **номер** совпадает с целевой карточкой или это явно то же производство — `move_to_target`: true.\n"
        "Если номер другой, но **несколько ключевых участников** из карточки явно фигурируют и контекст тот же (банкротство и т.д.) — "
        "скорее `true`.\n"
        "Если данных мало и связь не видна — `false`.\n"
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
            "Не получилось сопоставить **целевую папку** с карточкой дела. Напишите, куда собрать, например: "
            "«…перенеси подходящие в папку Банкротство Эмиль» или «…в папку А40-12345/2025» — **кавычки не нужны**. "
            "Либо откройте нужную папку слева и добавьте «в текущую папку».",
            None,
        )

    target_tags = _load_case_tags_for_collect(db, target.id)
    profile = _target_profile_lines(target, target_tags)
    source_only = resolve_optional_source_case_only(db, text, target)

    q = db.query(Document, Case).join(Case, Case.id == Document.case_id)
    if source_only:
        q = q.filter(Document.case_id == source_only.id)
    else:
        q = q.filter(Document.case_id != target.id)
    all_rows = q.order_by(Document.id.asc()).limit(max_candidates + 5).all()
    candidates: list[tuple[Document, Case]] = [(d, c) for d, c in all_rows][:max_candidates]
    if not candidates:
        if source_only:
            return (
                f'В папке «{source_only.title}» ({source_only.case_number}) нет документов для отбора '
                f'или она совпадает с целевой.',
                target,
            )
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
        move = False
        reason = ""
        if doc.id in decisions:
            move, reason = decisions[doc.id]
        if move:
            to_move.append(doc)
            reasons[doc.id] = reason
            continue
        ok_h, why_h = _heuristic_semantic_move(doc, target, source_only, target_tags)
        if ok_h:
            to_move.append(doc)
            reasons[doc.id] = why_h

    if not to_move:
        where = f'в папке «{source_only.title}»' if source_only else "в других папках"
        return (
            f"По смыслу текста **не нашлось** документов {where}, которые можно уверенно отнести к карточке "
            f'«{target.title}». Проверьте распознавание PDF или уточните формулировку (ФИО, номер дела).',
            target,
        )

    scope_line = (
        f"Область разбора: **только** папка «{source_only.title}» ({source_only.case_number})."
        if source_only
        else "Область разбора: все папки **кроме** целевой."
    )

    preview_only = wants_semantic_collect_preview_only(text)
    if not preview_only:
        moved_n = _execute_semantic_moves(db, target, to_move)
        lines = [
            f'**Семантический сбор** — перенёс **{moved_n}** документ(ов) в «{target.title}» ({target.case_number}).',
            "",
            scope_line,
            f"Просмотрено кандидатов: {len(candidates)}; отобрано к переносу: **{len(to_move)}**.",
            "",
            "Перенос выполнен **сразу**, чтобы не приходилось сверять список вручную. "
            "Если нужен только предпросмотр без переноса — напишите фразу **«только список»** или **«без переноса»** в том же запросе.",
            "",
            "_Фрагмент перенесённых (до 15):_",
        ]
        for idx, doc in enumerate(to_move[:15], start=1):
            why = reasons.get(doc.id, "")
            if len(why) > 120:
                why = why[:118] + "…"
            lines.append(f"{idx}. [{doc.id}] {doc.filename} — _{why}_")
        if len(to_move) > 15:
            lines.append(f"... и ещё {len(to_move) - 15}.")
        if len(candidates) >= max_candidates:
            lines.append("")
            lines.append(
                f"_(Просмотрено не более {max_candidates} документов; при необходимости повторите запрос.)_"
            )
        return "\n".join(lines), target

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

    lines = [
        f'**Семантический сбор** (только список) в папку «{target.title}» ({target.case_number}).',
        "",
        scope_line,
        "Ниже документы, которые модель считает относящимися к этому делу по тексту и контексту.",
        f"Кандидатов просмотрено: {len(candidates)}; к переносу отобрано: **{len(to_move)}**.",
        "",
        "Чтобы выполнить перенос, ответьте: `Да, перенеси все` или `Да, перенеси все, кроме 3, 7`",
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
