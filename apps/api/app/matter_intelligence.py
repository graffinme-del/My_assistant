"""Смысловой анализ набора папок (дел): кластеризация по сути спора, не только по номеру."""

from __future__ import annotations

import json
import re
from typing import Any

from sqlalchemy.orm import Session

from .ai_service import llm_system_user
from .config import settings
from .models import Case, CaseEvent, CaseTag, Document, PendingSemanticPlan


def _strip_json_fence(raw: str) -> str:
    s = (raw or "").strip()
    m = re.search(r"```(?:json)?\s*([\s\S]*?)```", s, re.IGNORECASE)
    if m:
        return m.group(1).strip()
    return s


def build_workspace_digest(db: Session, *, max_cases: int = 70, snippets_per_case: int = 2) -> str:
    rows = db.query(Case).order_by(Case.updated_at.desc()).limit(max_cases * 2).all()
    cases = [c for c in rows if (c.case_number or "").upper() != "UNSORTED"][:max_cases]
    blocks: list[str] = []
    for c in cases:
        tags = db.query(CaseTag).filter(CaseTag.case_id == c.id).limit(16).all()
        tag_str = ", ".join(f"{t.kind}:{t.value}" for t in tags)
        nd = db.query(Document).filter(Document.case_id == c.id).count()
        docs = (
            db.query(Document)
            .filter(Document.case_id == c.id)
            .order_by(Document.created_at.desc())
            .limit(snippets_per_case)
            .all()
        )
        snips: list[str] = []
        for d in docs:
            txt = (d.extracted_text or "").strip()
            txt = re.sub(r"\s+", " ", txt)[:450]
            snips.append(f"{d.filename}: {txt or '(текст не извлечён)'}")
        blocks.append(
            f"CASE_ID={c.id}; number={c.case_number}; title={c.title}; doc_count={nd}; "
            f"tags=[{tag_str}]\n" + "\n".join(f"  • {s}" for s in snips)
        )
    return "\n\n".join(blocks) if blocks else "(нет папок кроме неразобранного)"


def _valid_case_ids(db: Session) -> set[int]:
    rows = db.query(Case.id, Case.case_number).all()
    return {r[0] for r in rows if (r[1] or "").upper() != "UNSORTED"}


def _normalize_clusters(parsed: dict[str, Any], allowed: set[int]) -> list[dict[str, Any]]:
    raw_clusters = parsed.get("clusters") or []
    out: list[dict[str, Any]] = []
    assigned: set[int] = set()
    for item in raw_clusters:
        if not isinstance(item, dict):
            continue
        ids = [int(x) for x in (item.get("case_ids") or []) if str(x).isdigit()]
        ids = [i for i in ids if i in allowed and i not in assigned]
        if len(ids) < 2:
            continue
        rec_raw = item.get("recommended_target_case_id")
        try:
            rec = int(rec_raw) if rec_raw is not None else ids[0]
        except (TypeError, ValueError):
            rec = ids[0]
        if rec not in ids:
            rec = ids[0]
        conf = item.get("confidence")
        try:
            cf = float(conf) if conf is not None else 0.5
        except (TypeError, ValueError):
            cf = 0.5
        cf = max(0.0, min(1.0, cf))
        out.append(
            {
                "label": str(item.get("label") or "Группа").strip()[:200],
                "case_ids": ids,
                "confidence": cf,
                "rationale": str(item.get("rationale") or "").strip()[:1200],
                "recommended_target_case_id": rec,
            }
        )
        assigned.update(ids)
    return out


def _format_preview(clusters: list[dict[str, Any]], db: Session) -> str:
    lines: list[str] = [
        "Смысловой разбор папок (предложение модели). Одна строка — группа, которую имеет смысл считать **одним делом по сути** "
        "(разные номера процессов, банкротство и споры вокруг него и т.п.).",
        "",
        "Проверьте группы. Чтобы **выполнить слияние** папок внутри каждой группы в одну, ответьте:",
        "«да, объединить по смыслу» или «подтверждаю смысловое объединение».",
        "Отмена: «отмени смысловой план».",
        "",
    ]
    for i, cl in enumerate(clusters, start=1):
        ids = cl["case_ids"]
        parts: list[str] = []
        for cid in ids:
            c = db.query(Case).filter(Case.id == cid).first()
            if c:
                parts.append(f"id {c.id} «{c.title}» ({c.case_number})")
        lines.append(
            f"{i}. **{cl['label']}** (уверенность ~{int(cl['confidence'] * 100)}%)\n"
            f"   Папки: {', '.join(parts)}\n"
            f"   Почему: {cl['rationale'] or '—'}\n"
            f"   Предлагаемая основная папка (куда сольём остальные): id {cl['recommended_target_case_id']}"
        )
        lines.append("")
    if not clusters:
        lines.append("Подходящих групп из двух и более папок модель не нашла (или данных мало).")
    return "\n".join(lines).rstrip()


async def preview_semantic_workspace_clusters(db: Session, user_key: str) -> tuple[str, Case | None]:
    if not settings.openai_api_key.strip():
        return "Нужен API-ключ LLM (OPENAI_API_KEY), иначе смысловой разбор недоступен.", None
    digest = build_workspace_digest(db)
    allowed = _valid_case_ids(db)
    if len(allowed) < 2:
        return "Для смыслового объединения нужно минимум две папки (кроме «Неразобранное»).", None

    system = (
        "Ты аналитик судебных материалов. По кратким карточкам папок (дел) определи, какие из них относятся к **одной "
        "смысловой истории**: например банкротство одного лица и множество отдельных исков с разными номерами; "
        "или цепочка связанных споров с одними и теми же сторонами/предметом.\n"
        "Не объединяй папки только из-за общих слов без связи по делу.\n"
        "Верни **только JSON** без пояснений вне JSON, объект вида:\n"
        '{"clusters":[{"label":"краткое название сути","case_ids":[числа],"confidence":0.0-1.0,'
        '"rationale":"1-3 предложения по-русски","recommended_target_case_id":число}],'
        '"unclustered_case_ids":[числа],"notes":""}\n'
        "Правила: каждый case_id из входа не более чем в одном cluster; в cluster минимум 2 case_id; "
        "recommended_target_case_id обязан быть одним из case_ids этого cluster (лучше папка с «настоящим» "
        "номером арбитража или с большим doc_count, если видно из данных); confidence — насколько уверенно "
        "это одна история."
    )
    raw = await llm_system_user(system, f"Данные папок:\n\n{digest}", timeout=120.0)
    if not raw.strip():
        return "Модель не вернула ответ. Повторите запрос позже.", None
    try:
        parsed = json.loads(_strip_json_fence(raw))
    except json.JSONDecodeError:
        return (
            "Не удалось разобрать ответ модели как JSON. Попробуйте ещё раз или смените модель.\n"
            f"Фрагмент ответа: {raw[:800]}",
            None,
        )
    clusters = _normalize_clusters(parsed, allowed)
    payload = {"clusters": clusters, "unclustered_case_ids": parsed.get("unclustered_case_ids") or []}
    preview = _format_preview(clusters, db)

    db.query(PendingSemanticPlan).filter(
        PendingSemanticPlan.user_key == user_key,
        PendingSemanticPlan.plan_kind == "case_clusters",
    ).delete(synchronize_session=False)
    db.add(
        PendingSemanticPlan(
            user_key=user_key,
            plan_kind="case_clusters",
            payload_json=json.dumps(payload, ensure_ascii=False),
            preview_text=preview,
        )
    )
    db.commit()
    return preview, None


def cancel_pending_semantic_plan(db: Session, user_key: str) -> tuple[str, bool]:
    n = (
        db.query(PendingSemanticPlan)
        .filter(
            PendingSemanticPlan.user_key == user_key,
            PendingSemanticPlan.plan_kind == "case_clusters",
        )
        .delete(synchronize_session=False)
    )
    db.commit()
    if n:
        return "Черновик смыслового объединения сброшен.", True
    return "Нет активного смыслового плана для отмены.", False


def apply_pending_semantic_plan(db: Session, user_key: str) -> tuple[str, Case | None]:
    plan = (
        db.query(PendingSemanticPlan)
        .filter(
            PendingSemanticPlan.user_key == user_key,
            PendingSemanticPlan.plan_kind == "case_clusters",
        )
        .order_by(PendingSemanticPlan.created_at.desc())
        .first()
    )
    if not plan:
        return (
            "Нет сохранённого плана смыслового объединения. Сначала попросите проанализировать папки по смыслу.",
            None,
        )
    try:
        payload = json.loads(plan.payload_json or "{}")
    except json.JSONDecodeError:
        db.delete(plan)
        db.commit()
        return "План повреждён, запросите анализ заново.", None

    clusters = payload.get("clusters") or []
    if not clusters:
        db.delete(plan)
        db.commit()
        return "В плане нет групп для объединения.", None

    from .main import _move_all_case_content_to_target, _pick_merge_target_case

    last_target: Case | None = None
    merge_lines: list[str] = []
    total_merged_folders = 0
    total_docs = 0

    for cl in clusters:
        ids = [int(x) for x in cl.get("case_ids") or []]
        ids = sorted(set(ids))
        if len(ids) < 2:
            continue
        cases = db.query(Case).filter(Case.id.in_(ids)).all()
        if len(cases) < 2:
            continue
        if any((c.case_number or "").upper() == "UNSORTED" for c in cases):
            continue
        rec = cl.get("recommended_target_case_id")
        try:
            rec_id = int(rec) if rec is not None else None
        except (TypeError, ValueError):
            rec_id = None
        target = next((c for c in cases if c.id == rec_id), None)
        if not target:
            target = _pick_merge_target_case(db, cases)
        sources = [c for c in cases if c.id != target.id]
        sub_docs = 0
        for src in sources:
            n = _move_all_case_content_to_target(db, src, target)
            sub_docs += n
            db.add(
                CaseEvent(
                    case_id=target.id,
                    event_type="case_merge",
                    body=f"Смысловое объединение из «{src.title}» ({src.case_number}) — группа «{cl.get('label', '')}»",
                )
            )
            db.delete(src)
            total_merged_folders += 1
        total_docs += sub_docs
        db.commit()
        db.refresh(target)
        last_target = target
        merge_lines.append(
            f"— «{cl.get('label', 'группа')}»: в «{target.title}» ({target.case_number}), "
            f"слито папок: {len(sources)}, документов перенесено: {sub_docs}"
        )

    db.delete(plan)
    db.commit()

    if not merge_lines:
        return "Не удалось применить план (проверьте, что папки на месте).", last_target

    head = (
        f"Выполнено смысловое объединение. Целевая папка последнего слияния: "
        f"«{last_target.title}» ({last_target.case_number}).\n"
        f"Всего слито карточек дел: {total_merged_folders}, перенесено документов: {total_docs}.\n"
    )
    return head + "\n".join(merge_lines), last_target
