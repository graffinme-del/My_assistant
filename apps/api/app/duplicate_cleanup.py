"""Межпапочные дубликаты (одинаковое имя файла): выбор копии по **смыслу** текста + контексту папок (LLM), иначе — эвристика."""

from __future__ import annotations

import json
import re
from collections import defaultdict
from typing import Any

from sqlalchemy.orm import Session

from .ai_service import extract_case_number, llm_system_user
from .case_number import arbitr_case_number_lookup_keys, normalize_arbitr_case_number
from .config import settings
from .models import Case, CaseEvent, Document

GROUPS_PER_LLM_BATCH = 10
MAX_SNIPPET_CHARS = 520
MAX_GROUPS_IN_REPLY = 35


def _normalized_filename_key(filename: str) -> str:
    return re.sub(r"\s+", " ", (filename or "").strip().lower())


def _strip_json_fence(raw: str) -> str:
    s = (raw or "").strip()
    m = re.search(r"```(?:json)?\s*([\s\S]*?)```", s, re.IGNORECASE)
    if m:
        return m.group(1).strip()
    return s


def _doc_snippet(doc: Document) -> str:
    t = (doc.extracted_text or "").strip()
    t = re.sub(r"\s+", " ", t)[:MAX_SNIPPET_CHARS]
    return t if t else "(текст PDF не извлечён — ориентируйся на имя файла и папку)"


def gather_cross_folder_duplicate_groups(db: Session) -> dict[str, list[tuple[Document, Case]]]:
    groups: dict[str, list[tuple[Document, Case]]] = defaultdict(list)
    for d in db.query(Document).all():
        c = db.query(Case).filter(Case.id == d.case_id).first()
        if not c:
            continue
        key = _normalized_filename_key(d.filename)
        if len(key) < 4:
            continue
        groups[key].append((d, c))
    return {k: v for k, v in groups.items() if len({cc.id for _, cc in v}) >= 2}


def folder_preference_hint_from_text(text: str) -> str | None:
    for a, b in re.findall(r'"([^"]+)"|«([^»]+)»', text or ""):
        s = (a or b).strip()
        if len(s) >= 2:
            return s
    from .main import extract_case_hint_from_folder_phrase

    u = (extract_case_hint_from_folder_phrase(text or "") or "").strip()
    if len(u) >= 2:
        return u
    return None


def _keep_score(
    doc: Document,
    case: Case,
    db: Session,
    *,
    prefer_folder_substr: str | None,
) -> float:
    score = 0.0
    cn = (case.case_number or "").upper()
    title_l = (case.title or "").lower()

    if cn == "UNSORTED":
        score -= 5000.0
    elif "UNDEF" in cn:
        score -= 800.0
    elif cn.startswith("TAG-"):
        score -= 350.0

    num_fn = extract_case_number(doc.filename)
    if num_fn:
        keys = arbitr_case_number_lookup_keys(num_fn)
        cnorm = normalize_arbitr_case_number(case.case_number)
        if cnorm in keys or case.case_number in keys:
            score += 1200.0
        else:
            for k in keys:
                if k and (k == cnorm or k in cn or k in (case.case_number or "")):
                    score += 1000.0
                    break

    if prefer_folder_substr and prefer_folder_substr.lower() in title_l:
        score += 1500.0

    nd = db.query(Document).filter(Document.case_id == case.id).count()
    score += float(min(nd, 150))

    score -= doc.id * 1e-6
    return score


def pick_keep_document(
    items: list[tuple[Document, Case]],
    db: Session,
    *,
    prefer_folder_substr: str | None,
) -> tuple[Document, Case]:
    best_item = max(
        items,
        key=lambda it: (_keep_score(it[0], it[1], db, prefer_folder_substr=prefer_folder_substr), -it[0].id),
    )
    return best_item


def _heuristic_only_from_text(text: str) -> bool:
    t = (text or "").lower()
    return any(
        k in t
        for k in (
            "без ии",
            "без нейросет",
            "без модел",
            "только по имени",
            "только имя файла",
            "быстро ",
            "только эвристик",
        )
    )


def looks_like_cross_folder_duplicate_cleanup_request(text: str) -> bool:
    """Убрать лишние копии одного имени файла в разных папках."""
    from .main import looks_like_delete_case_folder_request

    t = (text or "").lower()
    dup = any(
        k in t
        for k in (
            "дубликат",
            "дубли",
            "дубль",
            "одинаков",
            "повтор",
            "копии файлов",
            "копий файлов",
            "лишн копи",
            "лишние копии",
            "повторяющ",
        )
    )
    action = any(
        k in t
        for k in (
            "удали",
            "убери",
            "почисти",
            "оставь од",
            "один экземпляр",
            "одну копию",
            "одна копия",
            "сотри",
        )
    )
    # «Удали папку А40-…» — удаление дела, не сценарий дубликатов (раньше ловилось из-за «удали» + «папк»).
    if looks_like_delete_case_folder_request(text) and not dup:
        return False
    preview = any(
        k in t
        for k in (
            "только список",
            "без удаления",
            "не удаляй",
            "превью",
            "покажи план",
            "что удалишь",
            "что удалится",
        )
    )
    if preview and not action:
        return True
    if (("покажи" in t) or ("выведи" in t)) and dup and not action:
        return True
    if action and dup:
        return True
    if action and ("между папк" in t or "между дел" in t):
        return True
    return False


def _build_chunk_user_block(
    chunk: list[tuple[int, str, list[tuple[Document, Case]]]],
    *,
    user_instruction: str,
    prefer_folder_substr: str | None,
) -> str:
    parts: list[str] = []
    if user_instruction.strip():
        parts.append(f"Пожелание пользователя: {user_instruction.strip()[:800]}")
    if prefer_folder_substr:
        parts.append(
            f"Если смысл текста неочевиден, отдайте приоритет копии в папке, в названии которой есть: «{prefer_folder_substr}»."
        )
    parts.append("")
    for gi, fname_key, items in chunk:
        d0 = items[0][0]
        parts.append(f"### Группа {gi}")
        parts.append(f"Имя файла: {d0.filename}")
        for d, c in items:
            parts.append(
                f"- document_id={d.id} | папка «{c.title}» | номер_дела_папки={c.case_number}\n"
                f"  фрагмент: {_doc_snippet(d)}"
            )
        parts.append("")
    return "\n".join(parts)


async def _llm_decide_duplicate_chunk(
    chunk: list[tuple[int, str, list[tuple[Document, Case]]]],
    *,
    user_instruction: str,
    prefer_folder_substr: str | None,
) -> dict[int, tuple[int, str]]:
    if not chunk or not settings.openai_api_key.strip():
        return {}
    system = (
        "Ты аналитик судебного архива. В каждой группе — несколько копий **одного и того же файла** (одинаковое имя) "
        "в разных папках (разные дела).\n"
        "По **содержанию** фрагмента текста, типу документа, номеру дела в тексте/имени файла и логике названия папки "
        "выбери **ровно одну** копию, которую нужно **оставить** (ту, где документ по смыслу относится к этой папке/делу). "
        "Остальные в группе считаются лишними дубликатами.\n"
        "Если текста мало — опирайся на номер дела в имени файла и номер/название папки.\n"
        "Не выдумывай факты, которых нет во фрагменте.\n"
        "Верни **только JSON** без текста вне JSON, формат:\n"
        '{"decisions":[{"group_index":число,"keep_document_id":число,"reason":"кратко по-русски"}]}\n'
        "group_index — как в заголовках «Группа N». keep_document_id — один из перечисленных document_id."
    )
    user_block = _build_chunk_user_block(
        chunk,
        user_instruction=user_instruction,
        prefer_folder_substr=prefer_folder_substr,
    )
    raw = await llm_system_user(system, user_block, timeout=150.0, max_tokens=3500)
    if not raw.strip():
        return {}
    try:
        data: dict[str, Any] = json.loads(_strip_json_fence(raw))
    except json.JSONDecodeError:
        return {}

    out: dict[int, tuple[int, str]] = {}
    id_by_group: dict[int, set[int]] = {
        gi: {d.id for d, _ in items} for gi, _fk, items in chunk
    }
    for row in data.get("decisions") or []:
        if not isinstance(row, dict):
            continue
        try:
            gi = int(row.get("group_index"))
            keep_id = int(row.get("keep_document_id"))
        except (TypeError, ValueError):
            continue
        if gi not in id_by_group or keep_id not in id_by_group[gi]:
            continue
        reason = str(row.get("reason") or "").strip()[:400]
        out[gi] = (keep_id, reason)
    return out


async def handle_cross_folder_duplicate_cleanup_chat(db: Session, text: str) -> tuple[str, Case | None]:
    from .main import delete_documents_hard, get_or_create_unsorted_case

    t = (text or "").lower()
    unsorted_case = get_or_create_unsorted_case(db)
    dry_run = (
        any(
            k in t
            for k in (
                "только список",
                "без удаления",
                "не удаляй",
                "превью",
                "покажи план",
                "что удалишь",
                "что удалится",
            )
        )
        and not any(k in t for k in ("удали", "убери", "почисти", "выполни удаление", "да, удали"))
    ) or ("покажи" in t and not any(k in t for k in ("удали", "убери", "почисти")))

    prefer = folder_preference_hint_from_text(text)
    heuristic_only = _heuristic_only_from_text(text)
    use_llm = bool(settings.openai_api_key.strip()) and not heuristic_only

    groups = gather_cross_folder_duplicate_groups(db)
    if not groups:
        return (
            "Одинаковых имён файла в **разных** папках не найдено — чистить нечего. "
            "(Совпадение только по нормализации пробелов и регистра в имени.)",
            unsorted_case,
        )

    sorted_groups: list[tuple[str, list[tuple[Document, Case]]]] = sorted(
        groups.items(), key=lambda x: (-len(x[1]), x[0])
    )
    n_total = len(sorted_groups)

    llm_decisions: dict[int, tuple[int, str]] = {}
    if use_llm:
        for batch_start in range(0, n_total, GROUPS_PER_LLM_BATCH):
            batch_slice = sorted_groups[batch_start : batch_start + GROUPS_PER_LLM_BATCH]
            chunk: list[tuple[int, str, list[tuple[Document, Case]]]] = [
                (batch_start + j, key, items) for j, (key, items) in enumerate(batch_slice)
            ]
            part = await _llm_decide_duplicate_chunk(
                chunk,
                user_instruction=text,
                prefer_folder_substr=prefer,
            )
            llm_decisions.update(part)

    lines: list[str] = [
        "**План очистки дубликатов** (одно имя файла — несколько папок).",
        "",
    ]
    if use_llm:
        lines.append(
            "Кого **оставить**: модель смотрит **фрагменты распознанного текста** PDF и контекст папки; "
            "лишние копии помечаются на удаление. Если для группы нет валидного ответа модели — используется запасное правило "
            "(номер дела в имени файла ↔ папка, без «UNDEF»/«Неразобранное»)."
        )
    else:
        lines.append(
            "Режим **без анализа текста** (эвристика по имени файла и папке). "
            "Чтобы включить разбор по смыслу, уберите из сообщения фразы вроде «только по имени» / «быстро» и задайте API-ключ LLM."
        )
    lines.append("")
    if prefer:
        lines.append(f"Подсказка по папке из кавычек: «{prefer}».")
        lines.append("")
    if dry_run:
        lines.append("*Превью — файлы **не** удаляются. Для выполнения: «Удали дубликаты между папками».*")
        lines.append("")

    to_remove: list[Document] = []
    n_groups = 0
    fallback_groups = 0

    for gi, (_key, items) in enumerate(sorted_groups):
        reason_llm = ""
        picked_by_llm = False
        if gi in llm_decisions:
            keep_id, reason_llm = llm_decisions[gi]
            id_set = {d.id for d, _ in items}
            if keep_id in id_set:
                keep_d = next(d for d, _ in items if d.id == keep_id)
                keep_c = next(c for d, c in items if d.id == keep_id)
                picked_by_llm = True
            else:
                keep_d, keep_c = pick_keep_document(items, db, prefer_folder_substr=prefer)
                reason_llm = "запасное правило (некорректный id от модели)"
                fallback_groups += 1
        else:
            keep_d, keep_c = pick_keep_document(items, db, prefer_folder_substr=prefer)
            if use_llm:
                fallback_groups += 1
                reason_llm = "запасное правило (нет ответа модели для группы)"
            else:
                reason_llm = "эвристика: номер дела в имени ↔ папка, служебные папки в конце"

        remove = [d for d, _c in items if d.id != keep_d.id]
        if not remove:
            continue
        n_groups += 1
        if n_groups <= MAX_GROUPS_IN_REPLY:
            src = "модель" if picked_by_llm else "правило"
            if picked_by_llm:
                short = reason_llm[:220] + ("…" if len(reason_llm) > 220 else "")
                lines.append(
                    f"**{keep_d.filename}** — оставляю [{keep_d.id}] в «{keep_c.title}» ({keep_c.case_number}) "
                    f"— *{src}*: {short}"
                )
            else:
                lines.append(
                    f"**{keep_d.filename}** — оставляю [{keep_d.id}] в «{keep_c.title}» ({keep_c.case_number}) "
                    f"— *{src}*: {reason_llm}"
                )
            for d, c in items:
                if d.id == keep_d.id:
                    continue
                lines.append(f"  − удалить [{d.id}] из «{c.title}» ({c.case_number})")
            lines.append("")
        to_remove.extend(remove)

    if n_groups > MAX_GROUPS_IN_REPLY:
        lines.append(f"… и ещё групп: {n_groups - MAX_GROUPS_IN_REPLY} (в ответе сокращено).")
        lines.append("")

    lines.append(f"Итого: **{n_groups}** групп, будет удалено **{len(to_remove)}** лишних файлов.")
    if use_llm and fallback_groups:
        lines.append(
            f"Из **{n_total}** групп в **{fallback_groups}** сработало запасное правило (имя файла/папка)."
        )

    if dry_run or not to_remove:
        lines.append("")
        lines.append(
            "Чтобы **выполнить** удаление лишних копий: «Удали дубликаты между папками» "
            "или «Убери дубликаты, оставь по одному»."
        )
        return "\n".join(lines), unsorted_case

    mode = "semantic_llm" if use_llm else "heuristic"
    delete_documents_hard(db, to_remove)
    db.add(
        CaseEvent(
            case_id=unsorted_case.id,
            event_type="duplicate_cleanup",
            body=(
                f"Межпапочная очистка дубликатов ({mode}): удалено {len(to_remove)} копий в {n_groups} группах."
            ),
        )
    )
    db.commit()

    lines.append("")
    tail = f"Готово: удалено **{len(to_remove)}** дубликатов ({'по смыслу текста + папки' if use_llm else 'по эвристике'})."
    lines.append(tail)
    return "\n".join(lines), unsorted_case
