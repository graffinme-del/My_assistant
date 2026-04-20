"""Пакетная автосортировка документов из UNSORTED: номер дела → при необходимости создание дела → совпадение по тегам/алиасам."""

from __future__ import annotations

from dataclasses import dataclass, field

from sqlalchemy.orm import Session

from .ai_service import extract_case_number, match_case
from .case_number import arbitr_case_number_lookup_keys, normalize_arbitr_case_number
from .models import Case, CaseEvent, Document
from .retrieval import sync_document_chunks


def find_case_by_arbitr_number(db: Session, extracted: str | None) -> Case | None:
    if not (extracted or "").strip():
        return None
    for key in arbitr_case_number_lookup_keys(extracted):
        c = db.query(Case).filter(Case.case_number == key).first()
        if c:
            return c
    return None


@dataclass
class AutoSortUnsortedResult:
    moved: int = 0
    remained: int = 0
    created_cases: int = 0
    moved_by_case_number: int = 0
    moved_by_tag_match: int = 0
    details: list[str] = field(default_factory=list)


def _ensure_case_for_number(db: Session, raw_number: str, *, source_filename: str) -> tuple[Case, bool]:
    """Возвращает дело с нормализованным номером; создаёт при отсутствии."""
    normalized = normalize_arbitr_case_number(raw_number.replace(" ", "").replace("\n", ""))
    case = find_case_by_arbitr_number(db, raw_number)
    if case:
        return case, False
    case = Case(
        title=f"Дело {normalized}",
        court_name="неизвестно",
        case_number=normalized,
        status="analysis",
        stage="analysis",
    )
    db.add(case)
    db.flush()
    db.add(
        CaseEvent(
            case_id=case.id,
            event_type="case_auto_created",
            body=f"Автосоздано при разборе неразобранного: {source_filename}",
        )
    )
    return case, True


def run_auto_sort_unsorted(
    db: Session,
    *,
    unsorted_case: Case,
    max_documents: int = 10000,
    create_missing_cases: bool = True,
    use_tag_match: bool = True,
    min_tag_confidence: float = 0.6,
    max_detail_lines: int = 24,
) -> AutoSortUnsortedResult:
    """
    Обрабатывает документы в UNSORTED: сначала извлечённый номер дела, затем match_case по тегам/тексту.
    После переноса обновляет чанки поиска (case_id в DocumentChunk).
    """
    out = AutoSortUnsortedResult()
    docs = (
        db.query(Document)
        .filter(Document.case_id == unsorted_case.id)
        .order_by(Document.created_at.asc())
        .limit(max_documents)
        .all()
    )
    if not docs:
        return out

    detail_budget = max_detail_lines

    for doc in docs:
        matched_case: Case | None = None
        confidence = 0.0
        reason = ""

        extracted_num = extract_case_number(doc.filename) or extract_case_number(doc.extracted_text or "")
        if extracted_num:
            found = find_case_by_arbitr_number(db, extracted_num)
            if found and found.id != unsorted_case.id:
                matched_case = found
                confidence = 0.97
                reason = "case_number"
            elif found is None and create_missing_cases:
                matched_case, created = _ensure_case_for_number(
                    db, extracted_num, source_filename=doc.filename
                )
                if created:
                    out.created_cases += 1
                confidence = 0.92
                reason = "case_number_new_case"

        if not matched_case and use_tag_match:
            mc, conf = match_case(db, filename=doc.filename, text=doc.extracted_text or "")
            if mc and mc.id != unsorted_case.id and conf >= min_tag_confidence:
                matched_case = mc
                confidence = conf
                reason = "tag_match"

        if not matched_case or matched_case.id == unsorted_case.id:
            out.remained += 1
            continue

        old_case_id = doc.case_id
        doc.case_id = matched_case.id
        db.add(
            CaseEvent(
                case_id=matched_case.id,
                event_type="document_reclassified",
                body=(
                    f'Документ "{doc.filename}" автоматически перенесён из UNSORTED '
                    f"({reason}, confidence={confidence:.2f})."
                ),
            )
        )
        db.add(
            CaseEvent(
                case_id=old_case_id,
                event_type="document_reclassified",
                body=f'Документ "{doc.filename}" перенесён в дело "{matched_case.title}" ({matched_case.case_number}).',
            )
        )
        sync_document_chunks(db, doc)
        out.moved += 1
        if reason.startswith("case_number"):
            out.moved_by_case_number += 1
        elif reason == "tag_match":
            out.moved_by_tag_match += 1

        if detail_budget > 0:
            out.details.append(
                f'- {doc.filename} -> "{matched_case.title}" ({matched_case.case_number}), '
                f"{reason}, confidence={confidence:.2f}"
            )
            detail_budget -= 1

    db.commit()
    return out


def format_auto_sort_reply(result: AutoSortUnsortedResult) -> str:
    lines = [
        "Автосортировка неразобранных:",
        f"- Перенесено: {result.moved} (по номеру дела: {result.moved_by_case_number}, по тегам/тексту: {result.moved_by_tag_match}).",
        f"- Осталось в UNSORTED: {result.remained}.",
    ]
    if result.created_cases:
        lines.append(f"- Создано новых дел по номеру: {result.created_cases}.")
    if result.details:
        lines.append("Детали:")
        lines.extend(result.details)
    return "\n".join(lines)
