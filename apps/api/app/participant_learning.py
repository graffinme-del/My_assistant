"""Автопривязка ФИО участников к делам (теги kind=participant) и контекст для LLM-маршрутизации."""

from __future__ import annotations

import re

from sqlalchemy.orm import Session

from .court_kad_search import looks_like_stored_arbitr_case_number
from .models import Case, CaseEvent, CaseTag

PARTICIPANT_TAG_KIND = "participant"

_ROLE_PATTERN = re.compile(
    r"(?:должник|истец|ответчик|заявитель|взыскатель|лиц[оа]?\s*,?\s*привлекаем(?:ое|ого|ых)?|"
    r"участник[а]?\s+(?:судебного\s+)?производств|представитель\s+должника|"
    r"гражданин(?:ка)?|индивидуальный\s+предприниматель)\s*[:\s—-]*",
    re.IGNORECASE,
)

_FIO_3 = re.compile(
    r"([А-ЯЁ][а-яё]{1,35}\s+[А-ЯЁ][а-яё]{1,35}\s+[А-ЯЁ][а-яё]{1,35})",
    re.UNICODE,
)

_FIO_AFTER_LABEL = re.compile(
    r"(?:фио|ф\.?\s*и\.?\s*о\.?)\s*[:\s—-]*" + r"([А-ЯЁ][а-яё]{1,35}\s+[А-ЯЁ][а-яё]{1,35}\s+[А-ЯЁ][а-яё]{1,35})",
    re.IGNORECASE | re.UNICODE,
)

_STOP_PARTS = frozenset(
    x.lower()
    for x in (
        "общество",
        "ограниченной",
        "ответственностью",
        "акционерное",
        "публичное",
        "федеральная",
        "служба",
        "судебн",
        "арбитражн",
        "российской",
        "федерации",
        "банк",
        "отдел",
        "управлен",
    )
)


def _clean_fio_candidate(s: str) -> str:
    return re.sub(r"\s+", " ", (s or "").strip(" \t\n\r.,;:\"'«»"))


def expand_participant_label_variants(name: str) -> list[str]:
    """Полное ФИО, фамилия, «Фамилия Имя» — для поиска без запоминания номера дела."""
    name = _clean_fio_candidate(name)
    if len(name) < 5:
        return [name[:255]] if name else []
    parts = name.split()
    out: list[str] = []
    seen: set[str] = set()

    def add(x: str) -> None:
        v = x.strip()[:255]
        if len(v) < 3:
            return
        k = v.lower()
        if k not in seen:
            seen.add(k)
            out.append(v)

    add(name)
    if len(parts) >= 3:
        add(parts[0])
        add(f"{parts[0]} {parts[1]}")
    elif len(parts) == 2:
        add(parts[0])
    return out


def extract_participant_fio_candidates(text: str, *, max_candidates: int = 14) -> list[str]:
    """Эвристика по типовым судебным формулировкам (без LLM)."""
    raw = (text or "")[:42000]
    found: list[str] = []
    seen: set[str] = set()

    def push(s: str) -> None:
        c = _clean_fio_candidate(s)
        if len(c) < 8:
            return
        parts = c.split()
        if any(p.lower() in _STOP_PARTS for p in parts):
            return
        k = c.lower()
        if k not in seen:
            seen.add(k)
            found.append(c)

    for m in _FIO_AFTER_LABEL.finditer(raw):
        push(m.group(1))

    for m in _ROLE_PATTERN.finditer(raw):
        start = m.end()
        chunk = raw[start : start + 220]
        m2 = _FIO_3.search(chunk)
        if m2:
            push(m2.group(1))

    for m in _FIO_3.finditer(raw):
        push(m.group(1))

    return found[:max_candidates]


def ensure_participant_tags_for_case(
    db: Session,
    case: Case,
    names: list[str],
    *,
    source: str = "auto",
) -> list[str]:
    """Добавляет теги участника; не дублирует существующие (по kind+value)."""
    if not names:
        return []
    existing = {
        (t.kind, t.value.strip().lower())
        for t in db.query(CaseTag).filter(CaseTag.case_id == case.id).all()
    }
    added: list[str] = []
    for raw in names:
        for variant in expand_participant_label_variants(raw):
            v = variant.strip()[:255]
            key = (PARTICIPANT_TAG_KIND, v.lower())
            if key in existing or len(v) < 3:
                continue
            db.add(CaseTag(case_id=case.id, value=v, kind=PARTICIPANT_TAG_KIND))
            existing.add(key)
            added.append(v)
    if added:
        db.add(
            CaseEvent(
                case_id=case.id,
                event_type="participant_tags",
                body=f"{source}: {', '.join(added[:12])}",
            )
        )
        db.commit()
    return added


def learn_participant_tags_from_document(
    db: Session,
    *,
    case: Case,
    filename: str,
    extracted_text: str,
) -> list[str]:
    """После сохранения документа: извлечь ФИО и привязать к делу с «настоящим» номером."""
    if not looks_like_stored_arbitr_case_number(case.case_number or ""):
        return []
    blob = f"{filename}\n{extracted_text or ''}"
    candidates = extract_participant_fio_candidates(blob)
    if not candidates:
        return []
    return ensure_participant_tags_for_case(db, case, candidates, source="ingest")


def build_participant_context_for_llm(db: Session, *, limit_cases: int = 120) -> str:
    """Краткая сводка «номер дела — участники» для подсказки llm_document_routing."""
    lines: list[str] = []
    q = (
        db.query(Case)
        .order_by(Case.updated_at.desc(), Case.id.desc())
        .limit(limit_cases)
        .all()
    )
    for c in q:
        if not looks_like_stored_arbitr_case_number(c.case_number or ""):
            continue
        tags = [
            t.value
            for t in db.query(CaseTag)
            .filter(CaseTag.case_id == c.id, CaseTag.kind == PARTICIPANT_TAG_KIND)
            .order_by(CaseTag.id.asc())
            .limit(14)
            .all()
        ]
        if not tags:
            continue
        seen: set[str] = set()
        uniq: list[str] = []
        for v in tags:
            k = v.lower()
            if k not in seen:
                seen.add(k)
                uniq.append(v)
        lines.append(f"- {c.case_number}: {', '.join(uniq)}")
    return "\n".join(lines[:100])


def _norm_hint(value: str) -> str:
    return re.sub(r"[^a-zа-я0-9]", "", (value or "").lower())


def resolve_case_if_unique_participant_hint(db: Session, fio: str) -> Case | None:
    """Если по ФИО находится ровно одно «настоящее» дело с тегами участника — вернуть его."""
    cases = find_cases_by_participant_hint(db, fio)
    if len(cases) == 1:
        return cases[0]
    return None


def describe_cases_for_disambiguation_prompt(cases: list[Case]) -> str:
    """Нумерованный список для промпта LLM и для текста уточнения пользователю."""
    lines: list[str] = []
    for i, c in enumerate(cases[:16], start=1):
        t = (c.title or "").strip().replace("\n", " ")[:100]
        court = (c.court_name or "").strip().replace("\n", " ")[:80]
        lines.append(f"{i}. {c.case_number} — {t} ({court})".strip())
    return "\n".join(lines)


def fio_matches_owner_participants_setting(fio: str, owner_raw: str) -> bool:
    """Совпадение извлечённого ФИО с ASSISTANT_OWNER_PARTICIPANTS (фрагментарно)."""
    raw = (owner_raw or "").strip()
    if not raw or len((fio or "").strip()) < 5:
        return False
    fn = _norm_hint(fio)
    for part in raw.split(","):
        p = _norm_hint(part.strip())
        if len(p) < 6:
            continue
        if p in fn or fn in p:
            return True
    return False


def list_arbitr_cases_for_disambiguation(db: Session, limit: int = 24) -> list[Case]:
    """Последние дела с «настоящим» номером — для широкого выбора, если тегов участника ещё нет."""
    rows = (
        db.query(Case)
        .order_by(Case.updated_at.desc(), Case.id.desc())
        .limit(max(limit * 3, 40))
        .all()
    )
    out = [c for c in rows if looks_like_stored_arbitr_case_number(c.case_number or "")]
    return out[:limit]


def template_participant_clarification_message(filename: str, fio: str, candidates_block: str) -> str:
    return (
        f"Не удалось однозначно определить дело для файла «{filename}». "
        f"В тексте есть, в том числе, {fio} — эта фамилия/ФИО связаны с несколькими папками дел.\n"
        f"К какому делу отнести документ?\n{candidates_block}\n\n"
        "Ответьте в чате номером дела или фразой вида: "
        "«Привяжи к делу А40-12345/2025 участника …». "
        "Пока документ сохранён в «Неразобранное»."
    )


def find_cases_by_participant_hint(db: Session, hint: str) -> list[Case]:
    """Все дела, у которых в тегах участника есть пересечение с подсказкой."""
    norm_hint = _norm_hint(hint)
    if not norm_hint or len(norm_hint) < 3:
        return []
    cases = db.query(Case).all()
    scored: list[tuple[Case, float]] = []
    for case in cases:
        if not looks_like_stored_arbitr_case_number(case.case_number or ""):
            continue
        score = 0.0
        tags = db.query(CaseTag).filter(CaseTag.case_id == case.id, CaseTag.kind == PARTICIPANT_TAG_KIND).all()
        for t in tags:
            tn = _norm_hint(t.value)
            if not tn:
                continue
            if norm_hint in tn or tn in norm_hint:
                score += 1.0
            elif len(norm_hint) >= 5 and any(
                len(tok) >= 4 and tok in tn for tok in re.findall(r"[а-яё]{4,}", norm_hint)
            ):
                score += 0.45
        if score >= 0.45:
            scored.append((case, score))
    scored.sort(key=lambda x: (-x[1], x[0].id))
    return [c for c, _ in scored]


def looks_like_remember_participant_command(text: str) -> bool:
    t = (text or "").lower()
    if "участник" in t and "запомни" in t:
        return True
    if "привяжи" in t and ("фио" in t or "участник" in t):
        return True
    if "запомни" in t and "фио" in t and re.search(r"[АA]\d{1,4}-\d{1,7}/\d{2,4}", text or "", re.I):
        return True
    return False


def parse_remember_participant_command(text: str) -> tuple[str, str] | None:
    """(сырой_номер_из_текста, фио) или None."""
    raw = text or ""
    num_m = re.search(r"([АA]\d{1,4}-\d{1,7}/\d{2,4})", raw, re.I)
    if not num_m:
        return None
    cn_raw = num_m.group(1)
    fio_m = re.search(
        r"(?:фио|участник[а]?)\s*[:\s—-]*([А-ЯЁ][а-яё]+(?:\s+[А-ЯЁ][а-яё]+){1,3})",
        raw,
        re.I,
    )
    if fio_m:
        return cn_raw, fio_m.group(1).strip()
    after = raw[num_m.end() :]
    fio2 = _FIO_3.search(after)
    if fio2:
        return cn_raw, fio2.group(1).strip()
    before = raw[: num_m.start()]
    fio3 = _FIO_3.search(before)
    if fio3:
        return cn_raw, fio3.group(1).strip()
    return None


def handle_remember_participant_chat(db: Session, text: str) -> str | None:
    if not looks_like_remember_participant_command(text):
        return None
    parsed = parse_remember_participant_command(text)
    if not parsed:
        return (
            "Не хватает данных. Пример: «Привяжи к делу А53-13969/2026 участника Вартанов Эмиль Валерьевич» "
            "или «Запомни участника Вартанов Эмиль Валерьевич для дела А53-13969/2026»."
        )
    cn_raw, fio = parsed
    from .case_number import normalize_arbitr_case_number

    cn = normalize_arbitr_case_number(cn_raw.replace(" ", ""))
    case = db.query(Case).filter(Case.case_number == cn).first() or db.query(Case).filter(
        Case.case_number == cn_raw
    ).first()
    if not case:
        return (
            f"Дело с номером {cn} не найдено. Создайте папку дела или подтяните карточку из КАД, затем повторите команду."
        )
    if not looks_like_stored_arbitr_case_number(case.case_number or ""):
        return (
            "Эта папка не по номеру арбитражного дела (например А40-12345/2025). "
            "Привязку ФИО лучше делать для реальной папки дела."
        )
    added = ensure_participant_tags_for_case(db, case, [fio], source="chat")
    if not added:
        return f"Такие подписи участника уже есть у дела {case.case_number}."
    return f"Запомнил участника: {', '.join(added[:8])} — дело {case.case_number}."
