from datetime import datetime, time, timedelta
import json
import mimetypes
from typing import Any
import re
import shutil
from pathlib import Path
from uuid import uuid4
import tempfile
import zipfile

from fastapi import Depends, FastAPI, File, Form, Header, HTTPException, Query, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from sqlalchemy import inspect, or_, text
from sqlalchemy.orm import Session

from .assistant_context import (
    add_conversation_message,
    build_grounded_prompt,
    get_or_create_conversation,
    refresh_conversation_summary,
    resolve_case_with_conversation,
)
from .ai_service import (
    build_case_summary,
    classify_document,
    extract_document_text,
    llm_assistant_chat_reply,
    llm_digest_incoming_case_note,
    llm_disambiguate_document_among_cases,
    llm_parse_case_tag_update,
    llm_parse_delete_case_folder_request,
    llm_document_routing,
    llm_participant_clarification_message,
    llm_summary,
    match_case,
    extract_case_number,
    find_case_by_hint,
    looks_like_hearing_note,
    looks_like_case_tag_update,
    parse_case_tag_update,
    parse_hearing_note,
)
from .case_number import arbitr_case_number_lookup_keys, normalize_arbitr_case_number
from .court_kad_search import (
    apply_active_case_number_to_kad_request,
    apply_folder_documents_case_numbers_to_kad_request,
    extract_kad_folder_title_hint,
    looks_like_cancel_court_sync_jobs,
    looks_like_court_download_count_question,
    looks_like_court_download_status_question,
    looks_like_court_search_command,
    looks_like_kad_downloaded_documents_list,
    looks_like_stored_arbitr_case_number,
    parse_court_search_request,
    try_resolve_kad_folder_title_to_case_number,
)
from .court_sync_service import (
    cancel_active_court_sync_jobs,
    claim_next_sync_job,
    complete_sync_job,
    create_sync_job,
    create_watch_profile,
    enqueue_nightly_jobs,
    format_kad_download_count_answer,
    format_kad_downloaded_documents_list,
    format_nightly_report,
    format_recent_download_jobs_status,
    format_sync_status,
    update_job_progress,
    upsert_case_source,
    upsert_document_source,
)
from .config import settings
from .document_batch_sort import format_auto_sort_reply, run_auto_sort_unsorted
from .participant_learning import (
    build_participant_context_for_llm,
    describe_cases_for_disambiguation_prompt,
    extract_participant_fio_candidates,
    find_cases_by_participant_hint,
    fio_matches_owner_participants_setting,
    handle_remember_participant_chat,
    learn_participant_tags_from_document,
    list_arbitr_cases_for_disambiguation,
    resolve_case_if_unique_participant_hint,
    template_participant_clarification_message,
)
from .ru_date_range import describe_calendar_period_ru, parse_calendar_period_ru
from .db import Base, engine, get_db
from .duplicate_cleanup import (
    handle_cross_folder_duplicate_cleanup_chat,
    looks_like_cross_folder_duplicate_cleanup_request,
)
from .materials_workflow import (
    handle_compare_documents_request,
    handle_extract_deadlines_request,
    handle_materials_draft_request,
    looks_like_compare_documents_request,
    looks_like_cross_case_duplicate_scan_request,
    looks_like_extract_deadlines_request,
    looks_like_materials_draft_request,
)
from .models import (
    Case,
    CaseEmbedding,
    CaseEvent,
    CaseTag,
    Conversation,
    ConversationMessage,
    CourtCaseSource,
    CourtSyncJob,
    Document,
    PendingMovePlan,
    Reminder,
    Task,
)
from .retrieval import sync_document_chunks
from .schemas import (
    CaseCreate,
    CaseOut,
    DocumentIngestOut,
    DocumentCreate,
    DocumentOut,
    ReminderOut,
    EventCreate,
    EventOut,
    HearingNoteIn,
    AssistantActiveCaseIn,
    AssistantIngestIn,
    AssistantIngestOut,
    SummaryOut,
    TaskCreate,
    TaskOut,
    BulkIngestOut,
    AutoSortUnsortedOut,
    CourtSyncCaseSourceIn,
    CourtSyncClaimOut,
    CourtSyncGetOut,
    CourtSyncCompleteIn,
    CourtSyncDocumentSourceIn,
    CourtSyncJobOut,
    CourtSyncProgressIn,
    AssistantSummaryIn,
    AssistantSummaryOut,
)

Base.metadata.create_all(bind=engine)


def _ensure_court_sync_job_parser_year_columns() -> None:
    """Добавляет колонки в существующую БД без Alembic (PostgreSQL)."""
    insp = inspect(engine)
    if "court_sync_jobs" not in insp.get_table_names():
        return
    cols = {c["name"] for c in insp.get_columns("court_sync_jobs")}
    with engine.begin() as conn:
        if "parser_year_min" not in cols:
            conn.execute(text("ALTER TABLE court_sync_jobs ADD COLUMN parser_year_min INTEGER"))
        if "parser_year_max" not in cols:
            conn.execute(text("ALTER TABLE court_sync_jobs ADD COLUMN parser_year_max INTEGER"))


_ensure_court_sync_job_parser_year_columns()

app = FastAPI(title="My Assistant API", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)
STORAGE_ROOT = Path("/app/storage")
STORAGE_ROOT.mkdir(parents=True, exist_ok=True)


def require_user(x_api_token: str | None = Header(default=None)) -> str:
    if x_api_token in (settings.owner_token, settings.member_token):
        return "owner" if x_api_token == settings.owner_token else "member"
    raise HTTPException(status_code=401, detail="Unauthorized. Provide X-API-Token header.")


def require_user_header_or_query(
    x_api_token: str | None = Header(default=None),
    token: str | None = Query(default=None),
) -> str:
    effective = x_api_token or token
    if effective in (settings.owner_token, settings.member_token):
        return "owner" if effective == settings.owner_token else "member"
    raise HTTPException(status_code=401, detail="Unauthorized. Provide X-API-Token header.")


def get_or_create_unsorted_case(db: Session) -> Case:
    case = db.query(Case).filter(Case.case_number == "UNSORTED").first()
    if case:
        return case
    case = Case(
        title="Входящие без номера дела",
        court_name="неизвестно",
        case_number="UNSORTED",
        status="analysis",
        stage="analysis",
    )
    db.add(case)
    db.commit()
    db.refresh(case)
    return case


def extract_case_hint_from_folder_phrase(text: str) -> str:
    """Название папки/дела из «в папке …», «по делу …» — кавычки не обязательны."""
    head = (text or "").split("\n", 1)[0].strip()
    if not head:
        return ""
    for pat in (
        r'(?:в|во)\s+папк[еиу]\s+(?:«([^»]+)»|"([^"]+)"|\'([^\']+)\')',
        r'по\s+делу\s+(?:«([^»]+)»|"([^"]+)"|\'([^\']+)\')',
    ):
        m = re.search(pat, head, flags=re.IGNORECASE)
        if m:
            hint = next((g for g in m.groups() if g and g.strip()), "")
            if hint:
                return hint.strip()
    for pat in (
        r'(?:в|во)\s+папк[еиу]\s+(.+?)(?:\s*[.!?]|$)',
        r'по\s+делу\s+(.+?)(?:\s*[.!?]|$)',
    ):
        m = re.search(pat, head, flags=re.IGNORECASE)
        if m:
            hint = m.group(1).strip().strip('"\'«»')
            if hint and len(hint) >= 2:
                return hint
    return ""


def resolve_case_for_chat(
    db: Session,
    text: str,
    *,
    preferred_case_number: str | None = None,
) -> Case:
    cases = db.query(Case).all()
    if preferred_case_number:
        normalized_case_number = normalize_arbitr_case_number(preferred_case_number)
        case = db.query(Case).filter(Case.case_number == normalized_case_number).first()
        if case:
            return case

    extracted_case_number = extract_case_number(text)
    if extracted_case_number:
        normalized_case_number = normalize_arbitr_case_number(extracted_case_number)
        case = db.query(Case).filter(Case.case_number == normalized_case_number).first()
        if case:
            return case

    folder_hint = extract_case_hint_from_folder_phrase(text)
    if folder_hint:
        hinted = find_case_by_hint(cases, folder_hint, db=db)
        if hinted:
            return hinted

    hinted = find_case_by_hint(cases, text, db=db)
    if hinted:
        return hinted

    with_docs = (
        db.query(Case)
        .join(Document, Document.case_id == Case.id)
        .order_by(Case.updated_at.desc())
        .first()
    )
    if with_docs:
        return with_docs
    return get_or_create_unsorted_case(db)


def extract_move_source_case_number(text: str) -> str | None:
    """Номер дела-источника до «в папку» / «перенеси», чтобы не перепутать с целевой папкой."""
    raw = (text or "").strip()
    if not raw:
        return None
    parts = re.split(r"\bв\s+папк[ау]\b", raw, maxsplit=1, flags=re.IGNORECASE)
    head = parts[0] if parts else raw
    n = extract_case_number(head)
    if n:
        return n
    parts = re.split(r"\b(?:перенеси|перемести)\b", raw, maxsplit=1, flags=re.IGNORECASE)
    head = parts[0] if parts else raw
    if len(head.strip()) > 2:
        n = extract_case_number(head)
        if n:
            return n
    return None


def resolve_move_source_case_from_text(db: Session, text: str) -> Case | None:
    num = extract_move_source_case_number(text)
    if not num:
        return None
    return db.query(Case).filter(Case.case_number == num).first()


def local_storage_path(doc: Document) -> Path | None:
    if not doc.s3_key.startswith("local://"):
        return None
    rel = doc.s3_key.replace("local://", "", 1)
    path = STORAGE_ROOT / rel
    return path if path.exists() else None


def conversation_user_key(user_role: str) -> str:
    return f"default:{user_role}"


def index_document_for_retrieval(db: Session, document: Document) -> None:
    sync_document_chunks(db, document)
    db.commit()


def resolve_case_for_conversation(
    db: Session,
    text: str,
    *,
    user_role: str,
    preferred_case_number: str | None = None,
) -> tuple[Conversation, Case]:
    conversation = get_or_create_conversation(db, conversation_user_key(user_role))
    resolved_case = resolve_case_for_chat(db, text, preferred_case_number=preferred_case_number)
    active_case = resolve_case_with_conversation(conversation=conversation, resolved_case=resolved_case)
    if active_case is None:
        active_case = get_or_create_unsorted_case(db)
    if conversation.active_case_id != active_case.id:
        conversation.active_case_id = active_case.id
        db.add(conversation)
        db.commit()
        db.refresh(conversation)
    return conversation, active_case


def normalize_document_signature(filename: str, extracted_text: str) -> tuple[str, str]:
    norm_name = re.sub(r"\s+", " ", filename.strip().lower())
    norm_text = re.sub(r"\s+", " ", (extracted_text or "").strip().lower())[:4000]
    return norm_name, norm_text


def find_duplicate_document(
    db: Session,
    *,
    case_id: int,
    filename: str,
    extracted_text: str,
) -> Document | None:
    norm_name, norm_text = normalize_document_signature(filename, extracted_text)
    docs = db.query(Document).filter(Document.case_id == case_id).all()
    for doc in docs:
        doc_name, doc_text = normalize_document_signature(doc.filename, doc.extracted_text or "")
        if doc_name == norm_name and doc_text == norm_text:
            return doc
    return None


def format_duplicate_documents_across_cases_report(db: Session, *, limit_groups: int = 50) -> str:
    """Список файлов с одинаковым нормализованным именем в разных папках."""
    from collections import defaultdict

    groups: dict[str, list[tuple[Document, Case]]] = defaultdict(list)
    for d in db.query(Document).all():
        c = db.query(Case).filter(Case.id == d.case_id).first()
        if not c:
            continue
        key = normalize_document_signature(d.filename, "")[0]
        if len(key) < 4:
            continue
        groups[key].append((d, c))

    lines: list[str] = [
        "Одинаковое имя файла (после нормализации) встречается в нескольких папках:",
        "",
    ]
    shown = 0
    for _key, items in sorted(groups.items(), key=lambda x: (-len(x[1]), x[0])):
        case_ids = {c.id for _, c in items}
        if len(case_ids) < 2:
            continue
        shown += 1
        if shown > limit_groups:
            lines.append(f"… и другие группы (показано не больше {limit_groups}).")
            break
        d0, c0 = items[0]
        lines.append(f"** {d0.filename} ** — копий: {len(items)}, папок: {len(case_ids)}")
        for d, c in items[:18]:
            lines.append(
                f"  • [{d.id}] папка: «{c.title}» ({c.case_number}) | скачать: /api/documents/{d.id}/download"
            )
        if len(items) > 18:
            lines.append(f"  … ещё {len(items) - 18} строк в этой группе.")
        lines.append("")

    if shown == 0:
        return (
            "Не найдено совпадений имён файлов между разными папками. "
            "(Если имена отличаются пробелами или регистром, они всё равно сгруппируются.)"
        )
    lines.append(
        "Чтобы сравнить два конкретных файла по тексту: «Сравни документы [id1] и [id2]». "
        "Чтобы объединить папки с такими дублями одной командой: "
        "«Объедини папки, где повторяются одинаковые файлы». "
        "Чтобы **автоматически удалить лишние копии** (оставить по одному файлу в каждой группе по правилам «нужная папка»): "
        "«Удали дубликаты между папками» или «Покажи план удаления дубликатов» (сначала превью без удаления)."
    )
    return "\n".join(lines)


def looks_like_documents_list_request(text: str) -> bool:
    t = text.lower()
    return any(noun in t for noun in ["документ", "файл", "архив", "перечень", "реестр"]) and any(
        k in t
        for k in [
            "покажи",
            "список",
            "какие",
            "дай",
            "собери",
            "собрать",
            "перечень",
            "реестр",
            "все файлы",
            "все документы",
        ]
    )


def looks_like_documents_analyze_request(text: str) -> bool:
    t = text.lower()
    return any(noun in t for noun in ["документ", "файл", "архив"]) and any(
        k in t for k in ["разбери", "проанализ", "разлож", "сгруппир"]
    )


def looks_like_group_by_cases_request(text: str) -> bool:
    t = text.lower()
    action_markers = [
        "разлож",
        "разложи",
        "разложил",
        "сгруппируй",
        "сгруппировал",
        "раскидай",
        "раскидал",
        "как разлож",
        "как раскид",
        "что разлож",
        "что раскид",
    ]
    target_markers = [
        "по делам",
        "по папкам",
        "по дел",
        "по папк",
        "документы по делам",
        "файлы по делам",
        "как разложены документы",
        "как разложены файлы",
    ]
    return any(k in t for k in action_markers) and any(k in t for k in target_markers)


def looks_like_unsorted_tag_suggestion_request(text: str) -> bool:
    t = text.lower()
    return any(k in t for k in ["предлож", "подскажи", "придумай", "выдели"]) and any(
        k in t for k in ["теги", "алиасы", "ключевые слова", "неразобран", "unsorted"]
    )


def looks_like_reclassify_unsorted_request(text: str) -> bool:
    t = text.lower()
    if "автосорт" in t and ("неразобран" in t or "unsorted" in t):
        return True
    return any(k in t for k in ["разбери", "переразбери", "перенеси", "привяжи", "разложи"]) and any(
        k in t for k in ["неразобран", "unsorted", "по тегам", "по делам", "по номеру", "по номерам"]
    )


def looks_like_manual_move_request(text: str) -> bool:
    t = text.lower()
    return any(k in t for k in ["перенеси", "перемести", "привяжи"]) and "дело" in t and any(
        k in t for k in ["документ", "файл", "["]
    )


def looks_like_bulk_folder_by_keywords_request(text: str) -> bool:
    t = text.lower()
    if (
        any(k in t for k in ("перенеси", "перемести", "отправь"))
        and ("все документ" in t or "все файлы" in t)
        and "содерж" in t
        and ("в папк" in t or "папку " in t or "в дел" in t)
    ):
        return True
    return any(k in t for k in ["создай папк", "создай дело", "создай папку", "новая папка", "новое дело"]) and any(
        k in t
        for k in [
            "отправь туда",
            "перенеси туда",
            "все документы",
            "содержат",
            "содерж",  # содержащие, содержит
            "ключевые слова",
            "собери",
        ]
    )


def looks_like_save_message_to_case_request(text: str) -> bool:
    """«Сохрани это сообщение в папке …» — текст заметки в дело, не массовый перенос файлов."""
    t = text.lower()
    if not any(k in t for k in ["сохрани", "сохранить", "запиши", "записать"]):
        return False
    if any(
        k in t
        for k in [
            "сохрани документ",
            "сохранить документ",
            "сохрани файл",
            "сохранить файл",
            "сохрани все док",
        ]
    ):
        return False
    if not any(k in t for k in ["сообщение", "переписк", "заметку", "этот текст", "заметка"]):
        return False
    return any(k in t for k in ["папк", "дело", "дела", "сделк", "кейс"])


def parse_save_message_case_hint(text: str) -> str:
    """Название дела из кавычек в начале запроса (не из длинного текста ниже)."""
    head = text.split("\n", 1)[0] if "\n" in text else text[:600]
    for pat in (r"«([^»]+)»", r'"([^"]+)"', r"'([^']+)'"):
        m = re.search(pat, head)
        if m:
            return m.group(1).strip()
    return ""


def extract_saved_message_body_for_case(text: str) -> str:
    """Текст заметки без строки-команды «Сохрани сообщение…»."""
    lines = text.split("\n")
    if len(lines) >= 2:
        fl = lines[0].lower()
        if ("сохрани" in fl or "запиши" in fl or "сохранить" in fl) and any(
            k in fl for k in ["сообщение", "переписк", "заметк", "текст"]
        ):
            return "\n".join(lines[1:]).strip()
    stripped = re.sub(
        r"^\s*(?:сохрани|сохранить|запиши|записать)\s+(?:это\s+)?(?:сообщение|текст)\s+(?:в\s+)?(?:папк[еиу]?\s+|дел[аеу]?\s+)?[«\"']([^»\"']+)[»\"']\s*",
        "",
        text,
        count=1,
        flags=re.IGNORECASE | re.DOTALL,
    )
    if stripped.strip() and stripped != text:
        return stripped.strip()
    return text.strip()


def looks_like_delete_documents_command(text: str) -> bool:
    """Удаление файлов из приложения (не путать с «удали задачи КАД»). Русский + English delete/remove."""
    t = (text or "").lower()
    has_del_ru = any(k in t for k in ("удали", "удалить", "стереть", "убери", "убрать"))
    has_del_en = bool(re.search(r"\b(delete|deletes|deleted|remove|removes|erase)\b", t, flags=re.IGNORECASE))
    if not has_del_ru and not has_del_en:
        return False
    if "задач" in t and "документ" not in t and "файл" not in t and "pdf" not in t and "document" not in t:
        return False
    if "папк" in t and "документ" not in t and "файл" not in t and "document" not in t and "file" not in t:
        return False
    return any(
        k in t
        for k in (
            "документ",
            "документа",
            "документы",
            "файл",
            "файлы",
            "pdf",
            "материал",
            "вложен",
        )
    ) or bool(
        re.search(
            r"\b(documents?|docs?|files?|pdf|attachments?)\b",
            t,
            flags=re.IGNORECASE,
        )
    )


def looks_like_show_documents_in_folder_only(text: str) -> bool:
    """Просмотр списка («покажи документы в папке …»), не перенос из активного дела."""
    t = (text or "").lower()
    if not any(n in t for n in ["документ", "файл", "архив", "материал"]):
        return False
    if any(k in t for k in ["собери", "соберите", "перенеси все", "создай папк", "создай дело", "назови", "назовите"]):
        return False
    if "перенеси" in t or "перенести" in t:
        return False
    if any(
        k in t
        for k in [
            "покажи",
            "покажите",
            "список",
            "какие документ",
            "какие файлы",
            "выведи",
            "перечисли",
            "перечень",
            "дай список",
        ]
    ):
        return True
    if ("все документы" in t or "все файлы" in t) and ("папк" in t or "по делу" in t):
        return True
    return False


def looks_like_move_all_from_active_case_to_folder(text: str) -> bool:
    """«Собери все документы в папку …», «в отдельную папку», без «Создай папку … содержащие:»."""
    if looks_like_save_message_to_case_request(text):
        return False
    if looks_like_show_documents_in_folder_only(text):
        return False
    t = text.lower()
    if "содерж" in t:
        return False
    if "создай папк" in t or "создай дело" in t:
        return False
    if ("папк" not in t and "дело" not in t) or not any(k in t for k in ["документ", "файл", "материал"]):
        return False
    return any(
        k in t
        for k in [
            "собери",
            "соберите",
            "в отдельную папку",
            "все эти",
            "эти документы",
            "в папку",
            "все документы",
            "перенеси все",
            "перенеси",
            "назови",
            "назовите",
        ]
    )


def looks_like_current_archive_reference(text: str) -> bool:
    t = text.lower()
    return any(
        k in t
        for k in [
            "этот архив",
            "текущий архив",
            "в текущем архиве",
            "из текущего архива",
            "из этого архива",
        ]
    )


def looks_like_bulk_folder_from_current_archive_request(text: str) -> bool:
    t = text.lower()
    return any(k in t for k in ["создай папк", "создай папку", "создай дело", "собери в одну папку"]) and any(
        k in t
        for k in [
            "весь архив",
            "весь текущий архив",
            "этот архив",
            "текущий архив",
            "в текущем архиве",
            "в одну папку",
            "все в одну папку",
            "собери все",
        ]
    )


def looks_like_followup_current_archive_confirmation(text: str) -> bool:
    t = text.lower()
    return looks_like_current_archive_reference(text) and any(
        k in t
        for k in [
            "они все",
            "они в",
            "все в",
            "все из",
            "да, все",
            "да все",
            "именно из",
        ]
    )


def looks_like_pending_move_confirmation(text: str) -> bool:
    t = text.lower()
    return any(k in t for k in ["да, перенеси", "перенеси все", "подтверждаю", "ок, перенеси", "да перенеси"])


def looks_like_pending_move_rejection(text: str) -> bool:
    t = text.lower()
    return any(k in t for k in ["не относится", "кроме", "исключи", "не переноси", "убери"])


def looks_like_semantic_workspace_clusters_request(text: str) -> bool:
    """Запрос на смысловой разбор всех папок и предложение объединений (не то же самое, что «объедини X и Y»)."""
    t = (text or "").lower()
    triggers = (
        "по смыслу",
        "смыслов",
        "смысловое объедин",
        "одно дело",
        "разные номер",
        "кластериз",
        "кластер ",
        "сгруппир",
        "проанализируй папк",
        "разбери папк",
        "все папки по сути",
        "объедини по сути",
        "одна суть",
        "интеллектуальн",
    )
    if not any(x in t for x in triggers):
        return False
    hints = parse_merge_case_hints(text)
    if len(hints) >= 2 and looks_like_merge_cases_request(text):
        return False
    return True


def looks_like_semantic_plan_confirm(text: str) -> bool:
    t = (text or "").lower()
    if not any(x in t for x in ("смысл", "по сути")):
        return False
    if any(k in t for k in ("объедин", "подтверж", "выполни", "соглас", "примени", "соглашаюсь")):
        return True
    return ("да" in t or "ок" in t) and "объедин" in t


def looks_like_semantic_plan_cancel(text: str) -> bool:
    t = (text or "").lower()
    return ("отмен" in t and "смысл" in t) or "отмени смыслов" in t or "сбрось смыслов" in t


def looks_like_chronology_request(text: str) -> bool:
    t = text.lower()
    return any(k in t for k in ["хронолог", "таймлайн", "по датам", "по времени"])


def extract_search_query(text: str) -> str:
    lowered = text.lower()
    # «поищи» раньше «ищи», иначе срабатывает подстрока «ищи» внутри «поищи» и запрос обрезается неверно.
    for marker in ["поищи", "найди", "поиск", "ищи", "покажи документы с", "документы с", "покажи"]:
        idx = lowered.find(marker)
        if idx >= 0:
            return text[idx + len(marker) :].strip(" :.-")
    return ""


def looks_like_documents_search_request(text: str) -> bool:
    t = text.lower()
    # Запросы в картотеку (КАД) — не поиск по локальным файлам текущей папки.
    if re.search(
        r"(?:поищи|найди|ищи|поиск)\s+(?:в|из)\s+кад|кад\.arbitr|картотек[аеи]?\s+арбитраж",
        t,
    ):
        return False
    if looks_like_global_documents_search(text):
        return False
    return any(k in t for k in ["найди", "поиск", "ищи", "поищи"]) and any(
        k in t
        for k in [
            "док",
            "файл",
            "асв",
            "банк",
            "определен",
            "договор",
            "жалоб",
            "акт",
            "имя",
            "фио",
            "содержа",
        ]
    )


def looks_like_cross_folder_matter_narrative_request(text: str) -> bool:
    """Сквозная история по теме/лицу через все папки (не просто список файлов)."""
    t = (text or "").lower()
    narrative = any(
        k in t
        for k in (
            "полный расклад",
            "полный разбор",
            "полную картину",
            "расклад по",
            "разбор по",
            "хронолог",
            "таймлайн",
            "от первого",
            "до последнего",
            "единая история",
            "связное повествование",
            "связн повеств",
            "печальн",
            "вся история",
            "расскажи историю",
            "опиши историю",
            "сквозной разбор",
            "сквозная история",
        )
    )
    matter = any(
        k in t
        for k in (
            "банкротств",
            "конкурсн",
            "несостоятельн",
            "финансовым оздоровлением",
            "арбитражн управля",
        )
    )
    cross = any(
        k in t
        for k in (
            "все папк",
            "всех папк",
            "по всем папк",
            "во всех папк",
            "по всем делам",
            "во всех делах",
            "весь архив",
            "везде в",
            "по всем документ",
            "во всех документ",
        )
    )
    if narrative and matter:
        return True
    if narrative and cross:
        return True
    return False


def looks_like_global_documents_search(text: str) -> bool:
    """Поиск по тексту/имени файла во всех папках (делах)."""
    t = (text or "").lower()
    if re.search(
        r"(?:поищи|найди|ищи|поиск)\s+(?:в|из)\s+кад|кад\.arbitr|картотек[аеи]?\s+арбитраж",
        t,
    ):
        return False
    scope = (
        "во всех папках",
        "по всем папкам",
        "по всем делам",
        "во всех делах",
        "везде по документ",
        "по всем документ",
        "сквозной поиск",
        "глобально",
        "по всем файлам",
        "во всех файлах",
    )
    if not any(s in t for s in scope):
        return False
    return any(k in t for k in ("найди", "поищи", "ищи", "поиск", "покажи"))


def normalize_global_search_query(raw: str) -> str:
    """Убирает служебные слова из извлечённого запроса глобального поиска."""
    s = (raw or "").strip()
    s = re.sub(
        r"^(?:во\s+всех\s+папках|по\s+всем\s+папкам|по\s+всем\s+делам|во\s+всех\s+делах|везде|глобально)\s*[,:.-]*\s*",
        "",
        s,
        flags=re.I,
    )
    s = re.sub(r"^документы?\s*", "", s, flags=re.I)
    # После «документы, содержащие…» часто остаётся запятая — иначе префикс «содержащие» не снимается.
    s = re.sub(r"^[\s,.:;—–-]+", "", s)
    s = re.sub(
        r"^(?:содержащ(?:ие|их)?|содержащие\s+имя|содержащие\s+текст|где\s+есть|с\s+текстом)\s+",
        "",
        s,
        flags=re.I,
    )
    s = re.sub(r"^(?:имя|фио|фамилию|текст)\s+", "", s, flags=re.I)
    s = re.sub(r"^[\s,.:;—–-]+", "", s)
    return s.strip(" ,.:-—")


def looks_like_single_doc_summary_request(text: str) -> bool:
    t = text.lower()
    return any(k in t for k in ["суть документа", "выжимка документа", "о чем документ", "резюме документа"])


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/ai/status")
async def ai_status(_: str = Depends(require_user)) -> dict[str, str | bool]:
    base = settings.openai_base_url.rstrip("/")
    provider = "openrouter" if "openrouter" in base.lower() else "openai"
    configured = bool(settings.openai_api_key.strip())
    if not configured:
        return {
            "provider": provider,
            "base_url": base,
            "configured": False,
            "status": "not_configured",
            "model": settings.openai_model,
            "message": (
                "В контейнере API нет ключа. На сервере в /opt/my_assistant в файле .env добавьте строку "
                "OPENAI_API_KEY=sk-… (без кавычек), при необходимости OPENAI_BASE_URL и OPENAI_MODEL, затем: "
                "docker compose --env-file .env -f infra/compose.prod.yml up -d --force-recreate api"
            ),
        }

    try:
        # Small probe call: proves API key/model/billing are operational.
        probe = await llm_summary("Проверка подключения. Ответь одним словом: OK")
        return {
            "provider": provider,
            "base_url": base,
            "configured": True,
            "status": "connected",
            "model": settings.openai_model,
            "message": (probe or "OK")[:120],
        }
    except Exception as exc:
        return {
            "provider": provider,
            "base_url": base,
            "configured": True,
            "status": "error",
            "model": settings.openai_model,
            "message": str(exc)[:200],
        }


@app.post("/cases", response_model=CaseOut)
def create_case(
    payload: CaseCreate, db: Session = Depends(get_db), _: str = Depends(require_user)
) -> Case:
    case = Case(**payload.model_dump())
    db.add(case)
    db.commit()
    db.refresh(case)
    return case


@app.get("/cases", response_model=list[CaseOut])
def list_cases(db: Session = Depends(get_db), _: str = Depends(require_user)) -> list[Case]:
    return db.query(Case).order_by(Case.updated_at.desc(), Case.id.desc()).all()


@app.get("/cases/{case_id}", response_model=CaseOut)
def get_case(case_id: int, db: Session = Depends(get_db), _: str = Depends(require_user)) -> Case:
    case = db.query(Case).filter(Case.id == case_id).first()
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")
    return case


@app.post("/cases/{case_id}/events", response_model=EventOut)
def add_event(
    case_id: int,
    payload: EventCreate,
    db: Session = Depends(get_db),
    _: str = Depends(require_user),
) -> CaseEvent:
    case = db.query(Case).filter(Case.id == case_id).first()
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")
    event = CaseEvent(case_id=case_id, **payload.model_dump())
    db.add(event)
    db.commit()
    db.refresh(event)
    return event


@app.get("/cases/{case_id}/events", response_model=list[EventOut])
def list_events(case_id: int, db: Session = Depends(get_db), _: str = Depends(require_user)) -> list[CaseEvent]:
    return (
        db.query(CaseEvent)
        .filter(CaseEvent.case_id == case_id)
        .order_by(CaseEvent.created_at.desc())
        .all()
    )


@app.post("/cases/{case_id}/tasks", response_model=TaskOut)
def add_task(
    case_id: int,
    payload: TaskCreate,
    db: Session = Depends(get_db),
    _: str = Depends(require_user),
) -> Task:
    case = db.query(Case).filter(Case.id == case_id).first()
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")
    task = Task(case_id=case_id, **payload.model_dump())
    db.add(task)
    db.commit()
    db.refresh(task)
    if task.due_date:
        reminder = Reminder(
            task_id=task.id,
            remind_at=datetime.combine(task.due_date, time(hour=9)),
            channel="push",
            sent=False,
        )
        db.add(reminder)
        db.commit()
    return task


@app.get("/cases/{case_id}/tasks", response_model=list[TaskOut])
def list_tasks(case_id: int, db: Session = Depends(get_db), _: str = Depends(require_user)) -> list[Task]:
    return (
        db.query(Task)
        .filter(Task.case_id == case_id)
        .order_by(Task.created_at.desc())
        .all()
    )


@app.get("/cases/{case_id}/reminders", response_model=list[ReminderOut])
def list_reminders(
    case_id: int, db: Session = Depends(get_db), _: str = Depends(require_user)
) -> list[Reminder]:
    return (
        db.query(Reminder)
        .join(Task, Reminder.task_id == Task.id)
        .filter(Task.case_id == case_id)
        .order_by(Reminder.remind_at.asc())
        .all()
    )


@app.post("/cases/{case_id}/documents", response_model=DocumentOut)
def add_document(
    case_id: int,
    payload: DocumentCreate,
    db: Session = Depends(get_db),
    _: str = Depends(require_user),
) -> Document:
    case = db.query(Case).filter(Case.id == case_id).first()
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")
    doc = Document(case_id=case_id, **payload.model_dump())
    db.add(doc)
    db.commit()
    db.refresh(doc)
    return doc


@app.get("/cases/{case_id}/documents", response_model=list[DocumentOut])
def list_documents(
    case_id: int, db: Session = Depends(get_db), _: str = Depends(require_user)
) -> list[Document]:
    return (
        db.query(Document)
        .filter(Document.case_id == case_id)
        .order_by(Document.created_at.desc())
        .all()
    )


@app.delete("/documents/{document_id}")
def delete_document(
    document_id: int,
    db: Session = Depends(get_db),
    _: str = Depends(require_user),
) -> dict[str, str | int]:
    doc = db.query(Document).filter(Document.id == document_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    fn = doc.filename
    cid = doc.case_id
    delete_documents_hard(db, [doc])
    return {"ok": True, "id": document_id, "filename": fn, "case_id": cid}


@app.get("/documents/{document_id}/download")
def download_document(
    document_id: int,
    inline: bool = Query(default=False),
    db: Session = Depends(get_db),
    _: str = Depends(require_user_header_or_query),
) -> FileResponse:
    doc = db.query(Document).filter(Document.id == document_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    path = local_storage_path(doc)
    if not path:
        raise HTTPException(status_code=404, detail="Document file not found on disk")
    media_type, _ = mimetypes.guess_type(doc.filename)
    if not media_type:
        media_type = "application/octet-stream"
    return FileResponse(
        path=str(path),
        filename=doc.filename,
        media_type=media_type,
        content_disposition_type="inline" if inline else "attachment",
    )


@app.get("/documents/{document_id}/summary")
async def document_summary(
    document_id: int, db: Session = Depends(get_db), _: str = Depends(require_user)
) -> dict[str, str | int]:
    doc = db.query(Document).filter(Document.id == document_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    case = db.query(Case).filter(Case.id == doc.case_id).first()
    text_sample = re.sub(r"\s+", " ", (doc.extracted_text or "").strip())[:6000]
    if not text_sample:
        text_sample = "Текст документа не извлечён. Есть только имя файла и категория."
    prompt = (
        "Сделай краткую выжимку по одному судебному документу.\n"
        "Ответ дай по-русски, коротко и по делу: что это за документ, по какому делу, "
        "главные участники, ключевые факты, даты и что важно проверить дальше. "
        "Не выдумывай то, чего нет в тексте.\n\n"
        f'Дело: {case.title if case else "неизвестно"} ({case.case_number if case else "-"})\n'
        f"Файл: {doc.filename}\n"
        f"Категория: {doc.category}\n"
        f"Текст:\n{text_sample}"
    )
    summary = await llm_summary(prompt)
    return {"document_id": doc.id, "filename": doc.filename, "summary": summary}


def find_case_by_arbitr_number(db: Session, extracted: str | None) -> Case | None:
    """Находит дело по номеру с учётом вариантов /25 и /2025."""
    if not (extracted or "").strip():
        return None
    for key in arbitr_case_number_lookup_keys(extracted):
        c = db.query(Case).filter(Case.case_number == key).first()
        if c:
            return c
    return None


def find_first_case_by_arbitr_numbers_in_text(db: Session, text: str) -> Case | None:
    for m in re.finditer(r"[АAаa]\d{1,4}-\d{1,7}/\d{2,4}", text or "", flags=re.IGNORECASE):
        c = find_case_by_arbitr_number(db, m.group(0))
        if c:
            return c
    return None


def _unlink_local_document_file(doc: Document) -> None:
    path = local_storage_path(doc)
    if path and path.is_file():
        try:
            path.unlink()
        except OSError:
            pass


def delete_documents_hard(db: Session, docs: list[Document]) -> list[str]:
    """Удаляет строки Document, чанки (CASCADE), файл на диске; пишет CaseEvent."""
    removed: list[str] = []
    for doc in docs:
        doc_id, case_id, fn = doc.id, doc.case_id, doc.filename
        _unlink_local_document_file(doc)
        db.add(
            CaseEvent(
                case_id=case_id,
                event_type="document_deleted",
                body=f"Удалён документ [{doc_id}]: {fn}",
            )
        )
        db.delete(doc)
        removed.append(f"[{doc_id}] {fn}")
    db.commit()
    return removed


# Токены, которые не должны участвовать в AND-поиске по PDF (часто попадают из формулировки запроса).
_HINT_SEARCH_SKIP_WORDS = frozenset(
    {
        "или",
        "либо",
        "содержащие",
        "содержащих",
        "документы",
        "документ",
        "найди",
        "поиск",
        "покажи",
        "всех",
        "папках",
        "делам",
        "делах",
    }
)


def _tokenize_delete_hint_words(h: str) -> list[str]:
    """Слова для поиска: кириллица и латиница, ё→е; без слишком коротких (кроме как часть фразы)."""
    s = (h or "").strip().lower()
    s = s.replace("ё", "е")
    words = re.findall(r"[a-zа-я]{3,}", s, flags=re.IGNORECASE)
    out: list[str] = []
    seen: set[str] = set()
    for w in words:
        wn = w.lower()
        if wn in _HINT_SEARCH_SKIP_WORDS or wn in seen:
            continue
        seen.add(wn)
        out.append(w)
    return out


def _collect_documents_matching_delete_hints(db: Session, hints: list[str]) -> list[Document]:
    """Имя файла или текст PDF. Если целая фраза не находится (разные пробелы в PDF), все значимые слова должны встречаться."""
    collected: dict[int, Document] = {}
    for h in hints:
        if re.search(r"[АAаa]\d{1,4}-\d{1,7}/\d{2,4}", h):
            continue
        h_safe = re.sub(r"[%_\x00]", "", h).strip()[:500]
        if len(h_safe) < 3:
            continue
        words = _tokenize_delete_hint_words(h_safe)
        q = db.query(Document)
        if len(words) >= 2:
            for w in words:
                w_esc = re.sub(r"[%_\x00]", "", w)[:80]
                if len(w_esc) < 3:
                    continue
                q = q.filter(
                    or_(
                        Document.filename.ilike(f"%{w_esc}%"),
                        Document.extracted_text.ilike(f"%{w_esc}%"),
                    )
                )
            q = q.order_by(Document.id.desc()).limit(300)
            for d in q:
                collected[d.id] = d
        else:
            w0 = words[0] if words else h_safe
            w0 = re.sub(r"[%_\x00]", "", w0)[:500]
            if len(w0) < 3:
                continue
            q = (
                q.filter(
                    or_(
                        Document.filename.ilike(f"%{w0}%"),
                        Document.extracted_text.ilike(f"%{w0}%"),
                    )
                )
                .order_by(Document.id.desc())
                .limit(250)
            )
            for d in q:
                collected[d.id] = d
    return list(collected.values())


def _extract_delete_target_phrases(text: str) -> list[str]:
    """Кавычки; для/for + ФИО; по Фамилия … (не по делу); English for Name."""
    out: list[str] = []
    seen: set[str] = set()

    def add(s: str) -> None:
        v = (s or "").strip().strip(".,;:")
        if len(v) >= 3 and v.lower() not in seen:
            seen.add(v.lower())
            out.append(v)

    for a, b in re.findall(r'"([^"]+)"|«([^»]+)»', text or ""):
        add((a or b).strip())
    for m in re.finditer(
        r"(?:для|по\s+фио)\s+([А-Яа-яЁёA-Za-z][А-Яа-яЁёA-Za-z'\-]*(?:\s+[А-Яа-яЁёA-Za-z][А-Яа-яЁёA-Za-z'\-]*){0,6})",
        text or "",
        flags=re.IGNORECASE,
    ):
        add(m.group(1).strip())
    m_en = re.search(
        r"\b(?:for|about)\s+([A-Za-zА-Яа-яЁё][A-Za-zА-Яа-яЁё'\-]*(?:\s+[A-Za-zА-Яа-яЁё][A-Za-zА-Яа-яЁё'\-]*){0,6})\s*[!?.…]*\s*$",
        (text or "").strip(),
        flags=re.IGNORECASE,
    )
    if m_en:
        add(m_en.group(1).strip())
    m_en2 = re.search(
        r"\b(?:for|about)\s+([A-Za-zА-Яа-яЁё][A-Za-zА-Яа-яЁё'\-]*(?:\s+[A-Za-zА-Яа-яЁё][A-Za-zА-Яа-яЁё'\-]*){1,6})(?=\s*[!?.]|$)",
        text or "",
        flags=re.IGNORECASE,
    )
    if m_en2:
        add(m_en2.group(1).strip())
    m2 = re.search(
        r"(?<![а-яё])по\s+(?!делу\b)([А-Яа-яЁё][А-Яа-яЁё'\-]*(?:\s+[А-Яа-яЁё][А-Яа-яЁё'\-]*){1,6})(?:\s*[!?.…]*)?(?:\s*$|\n)",
        text or "",
        flags=re.IGNORECASE,
    )
    if m2:
        add(m2.group(1).strip())
    return out


def parse_document_ids_for_delete_command(text: str) -> list[int]:
    raw = text or ""
    ids = [int(x) for x in re.findall(r"\[(\d+)\]", raw)]
    ids.extend(int(x) for x in re.findall(r"(?i)\bdoc[.:]?\s*(\d+)\b", raw))
    if ids:
        return sorted(set(ids))
    m = re.search(
        r"(?:документы?|файлы?)(?:\s+(?:с\s+)?id|\s+№|\s+#)?\s*[:.]?\s*([\d\s,;и]+)",
        text or "",
        flags=re.IGNORECASE,
    )
    if m:
        return sorted({int(x) for x in re.findall(r"\d+", m.group(1))})
    m2 = re.search(r"(?:документ|файл)\s*(?:№|#)?\s*(\d+)\b", text or "", flags=re.IGNORECASE)
    if m2:
        return [int(m2.group(1))]
    return []


def extract_document_ids_from_latest_assistant_message(db: Session, conversation: Conversation) -> list[int]:
    """Id вида [213] из последнего ответа ассистента (поиск, список файлов) — для «удали этот документ»."""
    m = (
        db.query(ConversationMessage)
        .filter(
            ConversationMessage.conversation_id == conversation.id,
            ConversationMessage.role == "assistant",
        )
        .order_by(ConversationMessage.created_at.desc())
        .first()
    )
    if not m or not (m.content or "").strip():
        return []
    return sorted({int(x) for x in re.findall(r"\[(\d+)\]", m.content)})


def _looks_like_this_document_anaphora(text: str) -> bool:
    t = (text or "").lower()
    return any(
        k in t
        for k in (
            "этот документ",
            "эту документ",
            "этот файл",
            "эту загрузку",
            "эти документы",
            "эти файлы",
            "тот документ",
            "тот файл",
            "найденн",
            "из результата",
            "из списка",
            "показанн",
            "выше ",
        )
    )


def _wants_delete_containing_folder(text: str) -> bool:
    """Составной запрос: убрать файл(ы) и папку/дело, где они лежат."""
    t = (text or "").lower()
    if "документ" not in t and "файл" not in t:
        return False
    if "папк" not in t and not re.search(r"\bдел[а-яё]*\b", t):
        return False
    return any(
        k in t
        for k in (
            "и папку",
            "и папк",
            "папку в которой",
            "папке в которой",
            "папку, в которой",
            "вместе с папк",
            "папку тоже",
            "и саму папку",
            "и само дело",
            "дело в котором",
        )
    )


def execute_delete_documents_and_optional_folder(
    db: Session,
    *,
    document_ids: list[int],
    also_delete_containing_folder: bool,
    user_message: str = "",
) -> tuple[str, Case | None]:
    """Удаляет документы; при флаге — затем удаляет дело целиком (остаток уходит в неразобранное)."""
    doc_ids = sorted({int(x) for x in document_ids if int(x) > 0})
    if not doc_ids:
        return "Не указаны номера документов.", None
    docs = db.query(Document).filter(Document.id.in_(doc_ids)).all()
    found_ids = {d.id for d in docs}
    missing = [i for i in doc_ids if i not in found_ids]
    if not docs:
        return (
            "Не нашёл документы с такими номерами. Пример: удали документы 214 287 или удали документ 214.",
            None,
        )
    case_for_reply = db.query(Case).filter(Case.id == docs[0].case_id).first()

    if also_delete_containing_folder:
        case_ids = {d.case_id for d in docs}
        if len(case_ids) != 1:
            return (
                "Указанные документы из разных папок. Уточните, какую папку удалить целиком, или удалите по шагам.",
                case_for_reply,
            )
        cid = next(iter(case_ids))
        folder_case = db.query(Case).filter(Case.id == cid).first()
        if not folder_case or (folder_case.case_number or "").upper() == "UNSORTED":
            removed = delete_documents_hard(db, docs)
            lines = ["Удалено из приложения (файл и поиск по тексту):"] + [f"• {r}" for r in removed]
            if missing:
                lines.append(f"Не найдены id: {', '.join(str(i) for i in missing)}.")
            return "\n".join(lines), get_or_create_unsorted_case(db)

        removed = delete_documents_hard(db, docs)
        doc_lines = ["Удалено из приложения (файл и поиск по тексту):"] + [f"• {r}" for r in removed]
        if missing:
            doc_lines.append(f"Не найдены id: {', '.join(str(i) for i in missing)}.")
        hint = folder_case.case_number or folder_case.title
        folder_reply, unsorted = handle_delete_case_folder_chat(
            db, user_message or "удали папку", hint_override=hint
        )
        return "\n\n".join(["\n".join(doc_lines), folder_reply]), unsorted

    removed = delete_documents_hard(db, docs)
    lines = ["Удалено из приложения (файл и поиск по тексту):"] + [f"• {r}" for r in removed]
    if missing:
        lines.append(f"Не найдены id: {', '.join(str(i) for i in missing)}.")
    return "\n".join(lines), case_for_reply


def handle_delete_documents_chat(
    db: Session, text: str, conversation: Conversation
) -> tuple[str, Case | None] | None:
    """Чат: удалить документы по id, по номеру дела или по фрагменту имени файла (в кавычках)."""
    if not looks_like_delete_documents_command(text):
        return None
    low = (text or "").lower()
    fallback_case = conversation.active_case or get_or_create_unsorted_case(db)

    doc_ids = parse_document_ids_for_delete_command(text)
    if not doc_ids and _looks_like_this_document_anaphora(text):
        doc_ids = extract_document_ids_from_latest_assistant_message(db, conversation)
    if doc_ids:
        if _wants_delete_containing_folder(text):
            return execute_delete_documents_and_optional_folder(
                db,
                document_ids=doc_ids,
                also_delete_containing_folder=True,
                user_message=text,
            )
        docs = db.query(Document).filter(Document.id.in_(doc_ids)).all()
        if not docs:
            return (
                "Не нашёл документы с такими номерами. Пример: удали документы 214 287 или удали документ 214.",
                fallback_case,
            )
        found_ids = {d.id for d in docs}
        missing = [i for i in doc_ids if i not in found_ids]
        removed = delete_documents_hard(db, docs)
        lines = ["Удалено из приложения (файл и поиск по тексту):"] + [f"• {r}" for r in removed]
        if missing:
            lines.append(f"Не найдены id: {', '.join(str(i) for i in missing)}.")
        case_reply = db.query(Case).filter(Case.id == docs[0].case_id).first() or fallback_case
        return "\n".join(lines), case_reply

    wants_all = any(
        w in low
        for w in (
            "все документ",
            "все файлы",
            "всех документ",
            "всех файлов",
            "каждый документ",
            "каждый файл",
        )
    )

    case: Case | None = find_first_case_by_arbitr_numbers_in_text(db, text)
    if not case and wants_all and any(
        p in low for p in ("этой папк", "текущ", "открыт", "в этой", "из этой", "это дело")
    ):
        case = conversation.active_case

    if wants_all and case:
        docs = db.query(Document).filter(Document.case_id == case.id).all()
        if not docs:
            return (
                f'В деле «{case.title}» ({case.case_number}) нет сохранённых документов.',
                case,
            )
        removed = delete_documents_hard(db, docs)
        return (
            f'Удалено файлов из дела «{case.title}» ({case.case_number}): {len(removed)}.\n'
            + "\n".join(f"• {r}" for r in removed),
            case,
        )

    hints = _extract_delete_target_phrases(text)
    if hints:
        docs = _collect_documents_matching_delete_hints(db, hints)
        if not docs:
            lat = hints[0] and all((not c.isalpha()) or ord(c) < 128 for c in hints[0])
            cyr_hint = (
                " В PDF обычно русское написание ФИО — попробуйте ту же фразу кириллицей "
                "(«Вартанов Эмиль Валерьевич»), либо «удали документ 214» / «удали все документы дела А53-13969/2026»."
                if lat
                else ""
            )
            return (
                f'Не нашёл документов, где в имени файла или в тексте PDF встречаются все значимые слова из «{hints[0]}». '
                "Проверьте написание или удалите по номеру дела."
                + cyr_hint,
                fallback_case,
            )
        removed = delete_documents_hard(db, docs)
        case_reply = db.query(Case).filter(Case.id == docs[0].case_id).first() or fallback_case
        return (
            f"Удалено по совпадению с фразой в имени файла или в тексте PDF ({len(removed)} шт.):\n"
            + "\n".join(f"• {r}" for r in removed)
            + "\n\nЗапросы в КАД лучше указывать с номером дела или ссылкой на карточку — "
            "по одному короткому имени поиск может подтянуть чужие дела.",
            case_reply,
        )

    if wants_all and not case:
        return (
            "Чтобы удалить всё лишнее, укажите номер дела, например: "
            "«удали все документы дела А53-13969/2026», "
            "или откройте папку слева и напишите «удали все документы в этой папке», "
            "или «удали все документы по Вартанов Эмиль Валерьевич» (поиск по имени файла и тексту PDF).",
            fallback_case,
        )
    return (
        "Напишите, что именно удалить:\n"
        "• по номерам: «удали документы 214 287»;\n"
        "• всё по делу: «удали все документы дела А53-13969/2026»;\n"
        "• всё в открытой папке: «удали все документы в этой папке»;\n"
        "• по ФИО/фразе в PDF: «удали все документы по Вартанов Эмиль Валерьевич» или «удали файлы «Вартанов»»;\n"
        "• после поиска: «удали этот документ и папку, где он лежит».",
        fallback_case,
    )


async def build_document_summary_by_id(db: Session, document_id: int) -> tuple[Document | None, str]:
    doc = db.query(Document).filter(Document.id == document_id).first()
    if not doc:
        return None, f"Документ {document_id} не найден."
    result = await document_summary(document_id=document_id, db=db, _="owner")
    return doc, str(result["summary"])


@app.post("/documents/ingest", response_model=DocumentIngestOut)
async def ingest_document(
    file: UploadFile = File(...),
    preferred_case_id: int | None = Form(default=None),
    db: Session = Depends(get_db),
    _: str = Depends(require_user),
) -> DocumentIngestOut:
    safe_name = file.filename or f"file-{uuid4().hex}.bin"
    storage_name = f"{uuid4().hex}-{safe_name}"
    dst = STORAGE_ROOT / storage_name
    with dst.open("wb") as out:
        shutil.copyfileobj(file.file, out)

    extracted_text = extract_document_text(dst, safe_name)
    category, class_confidence = classify_document(safe_name, extracted_text)

    matched_case = None
    case_confidence = 0.0
    llm_note = ""
    if preferred_case_id:
        matched_case = db.query(Case).filter(Case.id == preferred_case_id).first()
        if matched_case:
            case_confidence = 0.99

    if not matched_case:
        extracted_num = extract_case_number(safe_name) or extract_case_number(extracted_text)
        matched_case = find_case_by_arbitr_number(db, extracted_num)
        if matched_case:
            case_confidence = 0.97

    all_cases = db.query(Case).all()
    participant_ctx = build_participant_context_for_llm(db)
    llm_route = await llm_document_routing(
        filename=safe_name,
        text=extracted_text,
        available_case_numbers=[c.case_number for c in all_cases],
        participant_context=participant_ctx,
    )

    if llm_route:
        llm_case_number = str(llm_route.get("case_number", "")).strip()
        llm_category = str(llm_route.get("category", "")).strip()
        llm_confidence = float(llm_route.get("confidence", 0.0) or 0.0)
        llm_note = str(llm_route.get("short_note", "")).strip()
        if llm_category:
            category = llm_category
        if not matched_case and llm_case_number:
            ln = normalize_arbitr_case_number(llm_case_number)
            matched_case = db.query(Case).filter(Case.case_number == ln).first()
            if not matched_case:
                matched_case = db.query(Case).filter(Case.case_number == llm_case_number).first()
        if matched_case and case_confidence < 0.99:
            case_confidence = max(0.7, llm_confidence)
        class_confidence = max(class_confidence, llm_confidence)
    used_llm = llm_route is not None

    if not matched_case:
        matched_case, case_confidence = match_case(
            db,
            filename=safe_name,
            text=extracted_text,
            preferred_case_id=preferred_case_id,
        )
    if not matched_case:
        # Hands-off: если номер дела распознался, создадим дело автоматически.
        auto_case_number = extract_case_number(extracted_text) or extract_case_number(safe_name)
        if auto_case_number:
            normalized_auto = normalize_arbitr_case_number(auto_case_number.replace(" ", "").replace("\n", ""))
            case = find_case_by_arbitr_number(db, auto_case_number)
            if not case:
                case = Case(
                    title=f"Дело {normalized_auto}",
                    court_name="неизвестно",
                    case_number=normalized_auto,
                    status="analysis",
                    stage="analysis",
                )
                db.add(case)
                db.commit()
                db.refresh(case)
                db.add(
                    CaseEvent(
                        case_id=case.id,
                        event_type="case_auto_created",
                        body=f"Автосоздано дело из документа: {safe_name}",
                    )
                )
                db.commit()
            matched_case = case
            case_confidence = 0.4

    if not matched_case:
        matched_case = get_or_create_unsorted_case(db)
        case_confidence = 0.2

    participant_clarification: str | None = None
    needs_participant_clarification = False
    participant_clarification_cases: list[str] = []

    if matched_case.case_number == "UNSORTED" and not preferred_case_id:
        blob = f"{safe_name}\n{extracted_text}"
        fios = extract_participant_fio_candidates(blob)
        resolved_unique = False
        for fio in fios[:4]:
            one = resolve_case_if_unique_participant_hint(db, fio)
            if one:
                matched_case = one
                case_confidence = max(case_confidence, 0.78)
                resolved_unique = True
                break

        if not resolved_unique and fios:
            primary_fio = fios[0]
            multi = find_cases_by_participant_hint(db, primary_fio)
            if len(multi) >= 2:
                block = describe_cases_for_disambiguation_prompt(multi)
                if settings.openai_api_key.strip():
                    llm_pick = await llm_disambiguate_document_among_cases(
                        filename=safe_name,
                        text=extracted_text,
                        person_hint=primary_fio,
                        candidates_text=block,
                    )
                    if llm_pick:
                        cn_raw = str(llm_pick.get("case_number", "")).strip()
                        conf_llm = float(llm_pick.get("confidence", 0.0) or 0.0)
                        if cn_raw and conf_llm >= 0.68:
                            cn = normalize_arbitr_case_number(cn_raw.replace(" ", ""))
                            row = db.query(Case).filter(Case.case_number == cn).first()
                            if not row:
                                row = db.query(Case).filter(Case.case_number == cn_raw).first()
                            if row and row in multi:
                                matched_case = row
                                case_confidence = max(case_confidence, conf_llm)
                if matched_case.case_number == "UNSORTED":
                    participant_clarification_cases = [c.case_number for c in multi]
                    participant_clarification = await llm_participant_clarification_message(
                        filename=safe_name,
                        person_hint=primary_fio,
                        candidates_text=block,
                    )
                    if not participant_clarification:
                        participant_clarification = template_participant_clarification_message(
                            safe_name, primary_fio, block
                        )
                    needs_participant_clarification = True
            elif len(multi) == 0 and fio_matches_owner_participants_setting(
                primary_fio, settings.assistant_owner_participants
            ):
                wide = list_arbitr_cases_for_disambiguation(db, limit=24)
                if len(wide) >= 2:
                    wblock = describe_cases_for_disambiguation_prompt(wide)
                    if settings.openai_api_key.strip():
                        llm_w = await llm_disambiguate_document_among_cases(
                            filename=safe_name,
                            text=extracted_text,
                            person_hint=f"{primary_fio} (совпадает с ASSISTANT_OWNER_PARTICIPANTS)",
                            candidates_text=wblock,
                        )
                        if llm_w:
                            cn_raw = str(llm_w.get("case_number", "")).strip()
                            conf_llm = float(llm_w.get("confidence", 0.0) or 0.0)
                            if cn_raw and conf_llm >= 0.72:
                                cn = normalize_arbitr_case_number(cn_raw.replace(" ", ""))
                                row = db.query(Case).filter(Case.case_number == cn).first()
                                if not row:
                                    row = db.query(Case).filter(Case.case_number == cn_raw).first()
                                if row and row in wide:
                                    matched_case = row
                                    case_confidence = max(case_confidence, conf_llm)
                    if matched_case.case_number == "UNSORTED":
                        participant_clarification_cases = [c.case_number for c in wide]
                        participant_clarification = await llm_participant_clarification_message(
                            filename=safe_name,
                            person_hint=primary_fio,
                            candidates_text=wblock,
                        )
                        if not participant_clarification:
                            participant_clarification = template_participant_clarification_message(
                                safe_name, primary_fio, wblock
                            )
                        needs_participant_clarification = True

    duplicate = find_duplicate_document(
        db,
        case_id=matched_case.id,
        filename=safe_name,
        extracted_text=extracted_text,
    )
    if duplicate:
        return DocumentIngestOut(
            document=duplicate,
            matched_case_id=matched_case.id,
            matched_case_number=matched_case.case_number,
            category=duplicate.category,
            confidence=1.0,
            routing_mode="duplicate-skip",
            routing_model="дедупликация",
            note="Такой документ уже есть в этом деле. Повторная загрузка пропущена.",
            needs_participant_clarification=False,
            participant_clarification=None,
            participant_clarification_cases=[],
        )

    doc = Document(
        case_id=matched_case.id,
        filename=safe_name,
        category=category,
        s3_key=f"local://{storage_name}",
        extracted_text=extracted_text[:60000],
    )
    db.add(doc)
    db.add(
        CaseEvent(
            case_id=matched_case.id,
            event_type="document_ingested",
            body=(f"Добавлен документ: {safe_name} (категория: {category}). " f"{llm_note}".strip()),
        )
    )
    db.commit()
    db.refresh(doc)
    index_document_for_retrieval(db, doc)
    learn_participant_tags_from_document(
        db, case=matched_case, filename=safe_name, extracted_text=extracted_text
    )

    note_out = "Документ автоматически обработан и прикреплен к делу."
    if needs_participant_clarification and participant_clarification:
        note_out = participant_clarification

    return DocumentIngestOut(
        document=doc,
        matched_case_id=matched_case.id,
        matched_case_number=matched_case.case_number,
        category=category,
        confidence=round((class_confidence + case_confidence) / 2, 2),
        routing_mode="LLM" if used_llm else "fallback-правила",
        routing_model=settings.openai_model if used_llm else "эвристики",
        note=note_out,
        needs_participant_clarification=needs_participant_clarification,
        participant_clarification=participant_clarification if needs_participant_clarification else None,
        participant_clarification_cases=participant_clarification_cases,
    )


@app.post("/cases/{case_id}/hearing-note")
def process_hearing_note(
    case_id: int,
    payload: HearingNoteIn,
    db: Session = Depends(get_db),
    _: str = Depends(require_user),
) -> dict:
    case = db.query(Case).filter(Case.id == case_id).first()
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")

    event, tasks, extracted_date = parse_hearing_note(db, case, payload.text)
    db.refresh(case)
    return {
        "event_id": event.id,
        "created_tasks": [t.id for t in tasks],
        "next_hearing_date": extracted_date,
    }


@app.post("/documents/bulk-ingest", response_model=BulkIngestOut)
async def bulk_ingest(
    zip_file: UploadFile = File(...),
    preferred_case_number: str | None = Form(default=None),
    max_files: int = Form(default=0),
    db: Session = Depends(get_db),
    _: str = Depends(require_user),
) -> BulkIngestOut:
    # MVP: unzip -> for each supported file do the same auto routing as single ingest.
    # For now, indexing is synchronous (keep ZIP sizes moderate).
    if not zip_file.filename or not zip_file.filename.lower().endswith(".zip"):
        raise HTTPException(status_code=400, detail="Ожидается ZIP-архив (.zip)")

    preferred_case_id = None
    if preferred_case_number:
        normalized = normalize_arbitr_case_number(preferred_case_number)
        preferred_case_id = db.query(Case).filter(Case.case_number == normalized).first()
        preferred_case_id = preferred_case_id.id if preferred_case_id else None

    safe_name = f"{uuid4().hex}-{zip_file.filename}"
    dst = STORAGE_ROOT / safe_name
    with dst.open("wb") as out:
        shutil.copyfileobj(zip_file.file, out)

    total_files = 0
    ingested_files = 0
    skipped_files = 0
    errors: list[str] = []
    max_error_details = 15

    def add_skip_detail(message: str) -> None:
        if len(errors) < max_error_details:
            errors.append(message)

    try:
        with zipfile.ZipFile(dst) as zf, tempfile.TemporaryDirectory() as td:
            members = [m for m in zf.infolist() if not m.is_dir()]
            total_files = len(members)
            allowed_exts = {
                "pdf",
                "txt",
                "md",
                "csv",
                "log",
                "eml",
                "xlsx",
                "doc",
                "docx",
                "rtf",
                "jpg",
                "jpeg",
                "png",
                "webp",
                "mp3",
                "mp4",
            }
            if total_files == 0:
                return BulkIngestOut(
                    total_files=0, ingested_files=0, skipped_files=0, errors=["Архив пуст."]
                )

            for idx, m in enumerate(members):
                if max_files > 0 and idx >= max_files:
                    skipped_files += max(0, total_files - idx)
                    add_skip_detail(
                        f"Остановлено по лимиту max_files={max_files}. Не обработано файлов: {total_files - idx}."
                    )
                    break
                ext = (m.filename.rsplit(".", 1)[-1] if "." in m.filename else "").lower()
                if ext not in allowed_exts:
                    skipped_files += 1
                    add_skip_detail(f"{Path(m.filename).name}: неподдерживаемый формат .{ext or 'без_расширения'}")
                    continue

                # Extract one file
                extracted_path = Path(td) / Path(m.filename).name
                try:
                    with zf.open(m) as src, extracted_path.open("wb") as f_out:
                        shutil.copyfileobj(src, f_out)
                except Exception as e:
                    skipped_files += 1
                    add_skip_detail(f"{Path(m.filename).name}: не удалось распаковать ({str(e)[:120]})")
                    continue

                original_name = Path(m.filename).name
                try:
                    extracted_text = extract_document_text(extracted_path, original_name)
                except Exception as e:
                    skipped_files += 1
                    add_skip_detail(f"{original_name}: не удалось прочитать содержимое ({str(e)[:120]})")
                    continue
                category, class_confidence = classify_document(original_name, extracted_text)

                matched_case = None
                case_confidence = 0.0
                if preferred_case_id:
                    matched_case = db.query(Case).filter(Case.id == preferred_case_id).first()
                    if matched_case:
                        case_confidence = 0.99
                if not matched_case:
                    extracted_num = extract_case_number(original_name) or extract_case_number(extracted_text)
                    matched_case = find_case_by_arbitr_number(db, extracted_num)
                    if matched_case:
                        case_confidence = 0.97
                if not matched_case:
                    matched_case, case_confidence = match_case(
                        db,
                        filename=original_name,
                        text=extracted_text,
                        preferred_case_id=preferred_case_id,
                    )
                if not matched_case:
                    auto_case_number = extract_case_number(extracted_text) or extract_case_number(original_name)
                    if auto_case_number:
                        normalized_auto = normalize_arbitr_case_number(
                            auto_case_number.replace(" ", "").replace("\n", "")
                        )
                        case = find_case_by_arbitr_number(db, auto_case_number)
                        if not case:
                            case = Case(
                                title=f"Дело {normalized_auto}",
                                court_name="неизвестно",
                                case_number=normalized_auto,
                                status="analysis",
                                stage="analysis",
                            )
                            db.add(case)
                            db.commit()
                            db.refresh(case)
                            db.add(
                                CaseEvent(
                                    case_id=case.id,
                                    event_type="case_auto_created",
                                    body=f"Автосоздано дело из архива документов: {original_name}",
                                )
                            )
                            db.commit()
                        matched_case = case
                        case_confidence = 0.4
                    else:
                        skipped_files += 1
                        add_skip_detail(f"{original_name}: не удалось определить дело")
                        continue

                duplicate = find_duplicate_document(
                    db,
                    case_id=matched_case.id,
                    filename=original_name,
                    extracted_text=extracted_text,
                )
                if duplicate:
                    skipped_files += 1
                    add_skip_detail(f"{original_name}: уже есть в деле \"{matched_case.title}\"")
                    continue

                storage_name = f"{uuid4().hex}-{original_name}"
                final_path = STORAGE_ROOT / storage_name
                shutil.copyfile(str(extracted_path), final_path)

                doc = Document(
                    case_id=matched_case.id,
                    filename=original_name,
                    category=category,
                    s3_key=f"local://{storage_name}",
                    extracted_text=extracted_text[:60000],
                )
                db.add(doc)
                db.add(
                    CaseEvent(
                        case_id=matched_case.id,
                        event_type="document_ingested",
                        body=f"Bulk ingest: {original_name} (категория: {category})",
                    )
                )
                db.commit()
                db.refresh(doc)
                index_document_for_retrieval(db, doc)
                learn_participant_tags_from_document(
                    db, case=matched_case, filename=original_name, extracted_text=extracted_text
                )
                ingested_files += 1
    except zipfile.BadZipFile:
        raise HTTPException(status_code=400, detail="ZIP поврежден или не распаковывается.")
    except Exception as e:
        add_skip_detail(str(e))

    if skipped_files > len(errors):
        errors.append(f"И еще пропущено файлов без детализации: {skipped_files - len(errors)}")

    return BulkIngestOut(
        total_files=total_files,
        ingested_files=ingested_files,
        skipped_files=skipped_files,
        errors=errors,
    )


@app.post("/documents/auto-sort-unsorted", response_model=AutoSortUnsortedOut)
def auto_sort_unsorted_documents(
    max_documents: int = Query(default=10000, ge=1, le=50000),
    create_missing_cases: bool = Query(default=True),
    use_tag_match: bool = Query(default=True),
    db: Session = Depends(get_db),
    _: str = Depends(require_user),
) -> AutoSortUnsortedOut:
    """Разбор неразобранных: номер дела в имени/тексте (создание дела при необходимости), затем совпадение по тегам."""
    unsorted = db.query(Case).filter(Case.case_number == "UNSORTED").first()
    if not unsorted:
        raise HTTPException(status_code=404, detail="Неразобранное дело не найдено")
    result = run_auto_sort_unsorted(
        db,
        unsorted_case=unsorted,
        max_documents=max_documents,
        create_missing_cases=create_missing_cases,
        use_tag_match=use_tag_match,
    )
    return AutoSortUnsortedOut(
        moved=result.moved,
        remained=result.remained,
        created_cases=result.created_cases,
        moved_by_case_number=result.moved_by_case_number,
        moved_by_tag_match=result.moved_by_tag_match,
        details=result.details,
    )


@app.get("/cases/{case_id}/summary", response_model=SummaryOut)
async def case_summary(
    case_id: int, db: Session = Depends(get_db), _: str = Depends(require_user)
) -> SummaryOut:
    case = db.query(Case).filter(Case.id == case_id).first()
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")

    events = db.query(CaseEvent).filter(CaseEvent.case_id == case_id).all()
    tasks = db.query(Task).filter(Task.case_id == case_id).all()
    local_summary = build_case_summary(case, events, tasks)
    ai_text = await llm_summary(local_summary)
    return SummaryOut(case_id=case.id, summary=ai_text, next_hearing_date=case.next_hearing_date)


@app.get("/search")
def global_search(q: str, db: Session = Depends(get_db), _: str = Depends(require_user)) -> dict:
    cases = (
        db.query(Case)
        .filter(
            or_(
                Case.title.ilike(f"%{q}%"),
                Case.case_number.ilike(f"%{q}%"),
                Case.court_name.ilike(f"%{q}%"),
            )
        )
        .all()
    )
    docs = (
        db.query(Document)
        .filter(
            or_(
                Document.filename.ilike(f"%{q}%"),
                Document.extracted_text.ilike(f"%{q}%"),
                Document.category.ilike(f"%{q}%"),
            )
        )
        .limit(20)
        .all()
    )
    return {
        "query": q,
        "cases": [{"id": c.id, "title": c.title, "case_number": c.case_number} for c in cases],
        "documents": [{"id": d.id, "case_id": d.case_id, "filename": d.filename} for d in docs],
    }


@app.post("/internal/court-sync/claim", response_model=CourtSyncClaimOut)
def internal_claim_court_sync_job(
    db: Session = Depends(get_db), user_role: str = Depends(require_user)
) -> CourtSyncClaimOut:
    if user_role != "owner":
        raise HTTPException(status_code=403, detail="Owner token required")
    job = claim_next_sync_job(db)
    return CourtSyncClaimOut(job=job)


@app.get("/internal/court-sync/jobs/{job_id}", response_model=CourtSyncGetOut)
def internal_get_court_sync_job(
    job_id: int,
    db: Session = Depends(get_db),
    user_role: str = Depends(require_user),
) -> CourtSyncGetOut:
    if user_role != "owner":
        raise HTTPException(status_code=403, detail="Owner token required")
    job = db.query(CourtSyncJob).filter(CourtSyncJob.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return CourtSyncGetOut(job=job)


@app.post("/internal/court-sync/ensure-case")
def internal_ensure_case_for_number(
    case_number: str = Form(...),
    db: Session = Depends(get_db),
    user_role: str = Depends(require_user),
) -> dict[str, int]:
    if user_role != "owner":
        raise HTTPException(status_code=403, detail="Owner token required")
    normalized = normalize_arbitr_case_number(case_number)
    case = db.query(Case).filter(Case.case_number == normalized).first()
    if not case:
        case = Case(
            title=f"Дело {normalized}",
            court_name="неизвестно",
            case_number=normalized,
            status="analysis",
            stage="analysis",
        )
        db.add(case)
        db.commit()
        db.refresh(case)
    return {"case_id": case.id}


@app.post("/internal/court-sync/nightly-enqueue")
def internal_enqueue_nightly_sync(
    db: Session = Depends(get_db), user_role: str = Depends(require_user)
) -> dict[str, int]:
    if user_role != "owner":
        raise HTTPException(status_code=403, detail="Owner token required")
    return {"enqueued": enqueue_nightly_jobs(db)}


@app.post("/internal/court-sync/cancel-active")
def internal_cancel_active_court_sync_jobs(
    db: Session = Depends(get_db), user_role: str = Depends(require_user)
) -> dict[str, int]:
    if user_role != "owner":
        raise HTTPException(status_code=403, detail="Owner token required")
    return cancel_active_court_sync_jobs(db)


@app.post("/internal/court-sync/jobs/{job_id}/progress", response_model=CourtSyncJobOut)
def internal_update_court_sync_progress(
    job_id: int,
    payload: CourtSyncProgressIn,
    db: Session = Depends(get_db),
    user_role: str = Depends(require_user),
) -> CourtSyncJobOut:
    if user_role != "owner":
        raise HTTPException(status_code=403, detail="Owner token required")
    job = update_job_progress(db, job_id, step=payload.step, message=payload.message)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return job


@app.post("/internal/court-sync/jobs/{job_id}/complete", response_model=CourtSyncJobOut)
def internal_complete_court_sync_job(
    job_id: int,
    payload: CourtSyncCompleteIn,
    db: Session = Depends(get_db),
    user_role: str = Depends(require_user),
) -> CourtSyncJobOut:
    if user_role != "owner":
        raise HTTPException(status_code=403, detail="Owner token required")
    job = complete_sync_job(
        db,
        job_id,
        status=payload.status,
        result=payload.result_json,
        report_text=payload.report_text,
    )
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return job


@app.post("/internal/court-sync/jobs/{job_id}/case-source")
def internal_upsert_case_source(
    job_id: int,
    payload: CourtSyncCaseSourceIn,
    db: Session = Depends(get_db),
    user_role: str = Depends(require_user),
) -> dict[str, int]:
    if user_role != "owner":
        raise HTTPException(status_code=403, detail="Owner token required")
    job = db.query(CourtSyncJob).filter(CourtSyncJob.id == job_id).first()
    source = upsert_case_source(
        db,
        remote_case_id=payload.remote_case_id,
        case_number=payload.case_number,
        card_url=payload.card_url,
        title=payload.title,
        court_name=payload.court_name,
        participants=payload.participants,
        watch_profile_id=job.watch_profile_id if job else None,
        linked_case_id=payload.linked_case_id,
    )
    return {"case_source_id": source.id, "job_id": job_id}


@app.post("/internal/court-sync/jobs/{job_id}/document-source")
def internal_upsert_document_source(
    job_id: int,
    payload: CourtSyncDocumentSourceIn,
    db: Session = Depends(get_db),
    user_role: str = Depends(require_user),
) -> dict[str, int]:
    if user_role != "owner":
        raise HTTPException(status_code=403, detail="Owner token required")
    source = upsert_document_source(
        db,
        remote_document_id=payload.remote_document_id,
        case_source_id=payload.case_source_id,
        local_document_id=payload.local_document_id,
        title=payload.title,
        filename=payload.filename,
        file_url=payload.file_url,
        status=payload.status,
    )
    return {"document_source_id": source.id, "job_id": job_id}


@app.get("/internal/parser-api/test")
def internal_parser_api_test(
    case_number: str = Query(..., description="Номер дела, например А40-97353/2020"),
    try_first_pdf: bool = Query(default=False, description="Попробовать pdf_download по первому URL из ответа"),
    user_role: str = Depends(require_user),
) -> dict:
    """Проверка ключа Parser-API: детали по номеру дела и опционально скачивание первого PDF."""
    if user_role != "owner":
        raise HTTPException(status_code=403, detail="Owner token required")
    from .parser_api_client import (
        extract_kad_pdf_urls_from_details,
        parser_details_by_number,
        parser_pdf_download,
    )

    try:
        details = parser_details_by_number(case_number)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Parser-API: {e}") from e

    success = details.get("Success")
    pdf_urls = extract_kad_pdf_urls_from_details(details)
    out: dict = {
        "parser_success": success,
        "cases_in_response": len(details.get("Cases") or []),
        "kad_pdf_urls_found": len(pdf_urls),
        "first_pdf_url": pdf_urls[0] if pdf_urls else None,
    }
    if try_first_pdf and pdf_urls:
        try:
            raw = parser_pdf_download(pdf_urls[0])
            out["first_pdf_download_bytes"] = len(raw)
            out["first_pdf_starts_with_pdf"] = raw[:4] == b"%PDF"
        except Exception as e:
            out["first_pdf_error"] = str(e)[:500]
    return out


@app.get("/internal/parser-api/usage")
def internal_parser_api_usage(user_role: str = Depends(require_user)) -> dict[str, Any]:
    """Расход лимита Parser-API (как https://parser-api.com/stat/?key=...). Только owner."""
    if user_role != "owner":
        raise HTTPException(status_code=403, detail="Owner token required")
    from .parser_api_client import parser_usage_stat

    try:
        return parser_usage_stat()
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Parser-API stat: {e}") from e


@app.get("/internal/parser-api/service-status")
def internal_parser_api_service_status(user_role: str = Depends(require_user)) -> dict:
    """Статус сервисов Parser-API (публичный JSON). Только owner."""
    if user_role != "owner":
        raise HTTPException(status_code=403, detail="Owner token required")
    from .parser_api_client import parser_service_status_json

    try:
        return parser_service_status_json()
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Parser-API status: {e}") from e


@app.post("/assistant/summary-from-text", response_model=AssistantSummaryOut)
async def assistant_summary_from_text(
    payload: AssistantSummaryIn,
    db: Session = Depends(get_db),
    _: str = Depends(require_user),
) -> AssistantSummaryOut:
    extracted_case_number = payload.preferred_case_number or extract_case_number(payload.text)
    if extracted_case_number:
        normalized_case_number = extracted_case_number.replace(" ", "").replace("\n", "")
        case = db.query(Case).filter(Case.case_number == normalized_case_number).first()
    else:
        case = db.query(Case).order_by(Case.updated_at.desc()).first()
    if not case:
        case = get_or_create_unsorted_case(db)

    events = db.query(CaseEvent).filter(CaseEvent.case_id == case.id).all()
    tasks = db.query(Task).filter(Task.case_id == case.id).all()
    local_summary = build_case_summary(case, events, tasks)
    ai_text = await llm_summary(local_summary)
    return AssistantSummaryOut(
        case_id=case.id,
        case_number=case.case_number,
        summary=ai_text,
        next_hearing_date=case.next_hearing_date,
    )


def render_document_list(case: Case, docs: list[Document]) -> str:
    if not docs:
        note = ""
        if (case.case_number or "").startswith("TAG-"):
            note = (
                " Если документы должны быть здесь, попробуйте запрос по номеру дела "
                "(например: «покажи документы в папке по делу A40-19021/2025») — могла выбраться пустая служебная папка."
            )
        return f'В папке «{case.title}» пока нет загруженных документов.{note}'
    lines = [
        f'В папке «{case.title}» сейчас {len(docs)} документ(ов). Ниже первые 20; при необходимости сузим поиск.',
        "",
    ]
    for doc in docs[:20]:
        lines.append(
            f'- [{doc.id}] {doc.filename} ({doc.category}) — скачать: /api/documents/{doc.id}/download'
        )
    if len(docs) > 20:
        lines.append("")
        lines.append(f"… и ещё {len(docs) - 20}. Напишите, например: найди в этой папке …")
    return "\n".join(lines)


def render_documents_grouped_by_cases(db: Session) -> str:
    cases_with_docs = (
        db.query(Case)
        .join(Document, Document.case_id == Case.id)
        .order_by(Case.updated_at.desc())
        .all()
    )
    if not cases_with_docs:
        return "Пока нет загруженных документов, которые можно разложить по делам."

    seen_case_ids: set[int] = set()
    lines = ["Разложил документы по делам:"]
    unresolved_count = 0
    unresolved_examples: list[str] = []
    for case in cases_with_docs:
        if case.id in seen_case_ids:
            continue
        seen_case_ids.add(case.id)
        docs = (
            db.query(Document)
            .filter(Document.case_id == case.id)
            .order_by(Document.created_at.desc())
            .all()
        )
        if not docs:
            continue
        category_counts: dict[str, int] = {}
        for doc in docs:
            category_counts[doc.category] = category_counts.get(doc.category, 0) + 1
        top_categories = ", ".join(
            f"{name}: {count}" for name, count in sorted(category_counts.items(), key=lambda x: (-x[1], x[0]))[:4]
        )
        sample_docs = "; ".join(doc.filename for doc in docs[:3])
        if case.case_number == "UNSORTED":
            unresolved_count = len(docs)
            unresolved_examples = [doc.filename for doc in docs[:5]]
            continue
        lines.append(
            f'- "{case.title}" ({case.case_number}) -> документов: {len(docs)}; категории: {top_categories or "нет"}; '
            f'примеры: {sample_docs}'
        )

    if unresolved_count:
        lines.append(
            f'- Неразобранные / требуют ручной проверки: {unresolved_count}; примеры: {", ".join(unresolved_examples)}'
        )
    return "\n".join(lines)


async def suggest_tags_for_unsorted_case(db: Session) -> str:
    unsorted = db.query(Case).filter(Case.case_number == "UNSORTED").first()
    if not unsorted:
        return "Неразобранного дела нет."
    docs = (
        db.query(Document)
        .filter(Document.case_id == unsorted.id)
        .order_by(Document.created_at.desc())
        .all()
    )
    if not docs:
        return "В неразобранных документах пока ничего нет."

    snippets: list[str] = []
    for doc in docs[:20]:
        text_sample = re.sub(r"\s+", " ", (doc.extracted_text or "").strip())[:700]
        snippets.append(
            f"Файл: {doc.filename}\nКатегория: {doc.category}\nТекст: {text_sample or 'Текст не извлечён.'}"
        )

    prompt = (
        "Ты помогаешь разложить неразобранные судебные документы по делам.\n"
        "Нужно предложить возможные группы дел и для каждой дать:\n"
        "1. рабочее название дела,\n"
        "2. 3-8 тегов/ключевых слов,\n"
        "3. 1-3 алиаса/варианта названия,\n"
        "4. какие файлы к этой группе относятся.\n"
        "Если документы смешаны, раздели их на несколько групп. Не выдумывай номера дел, если их нет.\n\n"
        + "\n\n".join(snippets)
    )
    try:
        return await llm_summary(prompt)
    except Exception as exc:
        return f"Не удалось автоматически предложить теги для неразобранных документов: {exc}"


def reclassify_unsorted_documents(db: Session) -> str:
    unsorted = db.query(Case).filter(Case.case_number == "UNSORTED").first()
    if not unsorted:
        return "Неразобранного дела нет."

    docs = (
        db.query(Document)
        .filter(Document.case_id == unsorted.id)
        .order_by(Document.created_at.asc())
        .all()
    )
    if not docs:
        return "В неразобранных документах пока ничего нет."

    result = run_auto_sort_unsorted(db, unsorted_case=unsorted)
    return format_auto_sort_reply(result)


def move_documents_by_chat_command(db: Session, text: str) -> str:
    doc_ids = [int(x) for x in re.findall(r"\[(\d+)\]", text)]
    if not doc_ids:
        doc_ids = [int(x) for x in re.findall(r"(?:документ|файл)\s+(\d+)", text, flags=re.IGNORECASE)]
    if not doc_ids:
        return "Не вижу ID документов. Напишите, например: перенеси документ 4 в дело Банкротство АГМ"

    m = re.search(r"в\s+дел[оау]\s+(.+)$", text, flags=re.IGNORECASE)
    if not m:
        return "Не вижу, в какое дело переносить. Напишите: перенеси документ 4 в дело <название>"
    case_hint = m.group(1).strip(" .:-")
    target_case = find_case_by_hint(db.query(Case).all(), case_hint, db=db)
    if not target_case:
        return f'Не нашёл дело по фразе "{case_hint}". Сначала добавьте теги/алиасы или уточните название дела.'

    docs = db.query(Document).filter(Document.id.in_(doc_ids)).all()
    if not docs:
        return "Не нашёл документы с такими ID."

    moved: list[str] = []
    for doc in docs:
        old_case_id = doc.case_id
        doc.case_id = target_case.id
        db.add(
            CaseEvent(
                case_id=target_case.id,
                event_type="document_reclassified",
                body=f'Документ "{doc.filename}" вручную перенесён через чат.',
            )
        )
        db.add(
            CaseEvent(
                case_id=old_case_id,
                event_type="document_reclassified",
                body=f'Документ "{doc.filename}" вручную перенесён в дело "{target_case.title}".',
            )
        )
        moved.append(f'- [{doc.id}] {doc.filename}')
    db.commit()
    return (
        f'Перенёс документы в дело "{target_case.title}" ({target_case.case_number}).\n'
        + "\n".join(moved)
    )


def parse_bulk_folder_request(text: str) -> tuple[str, list[str]] | None:
    low = (text or "").lower()
    title = ""
    m = re.search(r'создай\s+(?:папк[ау]?|дело)\s*[:"«]?\s*([^"\n».]+)', text, flags=re.IGNORECASE)
    if m:
        title = m.group(1).strip(" .:-\"«»")
    if not title:
        m_dest = re.search(
            r"в\s+(?:папк[ау]?|дело)\s+(?:«([^»]+)»|\"([^\"]+)\")",
            text or "",
            flags=re.IGNORECASE,
        )
        if m_dest:
            title = (m_dest.group(1) or m_dest.group(2) or "").strip()
    quoted = [q.strip() for q in re.findall(r'"([^"]+)"|«([^»]+)»', text or "") for q in q if q.strip()]
    keywords: list[str] = []

    m_mid = re.search(
        r"содерж[а-я]*(?:\s+фамили[юи])?\s*(.+?)\s+в\s+(?:папк|дело)",
        text or "",
        flags=re.IGNORECASE | re.DOTALL,
    )
    if m_mid:
        raw_kw = (m_mid.group(1) or "").strip(" ,.:;\"'«»")
        raw_kw = re.sub(r"^фамили[юи]\s+", "", raw_kw, flags=re.IGNORECASE).strip()
        if raw_kw:
            keywords = [raw_kw]

    if "содерж" in low and not keywords:
        tail = re.split(r"содерж[а-я]*\s*[:]", text or "", flags=re.IGNORECASE)
        if len(tail) > 1:
            raw = tail[-1]
            raw = re.split(r"\s+в\s+(?:папк|дело)", raw, flags=re.IGNORECASE)[0]
            keywords = [p.strip(" .:-\"«»") for p in re.split(r"[,\n;]+", raw) if p.strip(" .:-\"«»")]
    if not title and quoted:
        title = quoted[-1]
    if not keywords:
        keywords = quoted[:-1] if len(quoted) > 1 and title and quoted[-1] == title else (quoted[1:] if len(quoted) > 1 else [])
    deduped: list[str] = []
    seen: set[str] = set()
    for value in keywords:
        key = value.lower()
        if value and key not in seen:
            seen.add(key)
            deduped.append(value)
    if not title or not deduped:
        return None
    return title, deduped


def parse_case_title_from_folder_request(text: str) -> str:
    m = re.search(r'создай\s+(?:папк[ау]?|дело)\s*[:"«]?\s*([^"\n».]+)', text, flags=re.IGNORECASE)
    if m:
        return m.group(1).strip(" .:-\"«»")
    quoted = [q.strip() for q in re.findall(r'"([^"]+)"|«([^»]+)»', text) for q in q if q.strip()]
    return quoted[0] if quoted else ""


def save_folder_request_context(db: Session, title: str) -> None:
    if not title:
        return
    unsorted_case = get_or_create_unsorted_case(db)
    db.add(CaseEvent(case_id=unsorted_case.id, event_type="folder_request_context", body=title[:255]))
    db.commit()


def get_recent_folder_request_context(db: Session, *, max_age_minutes: int = 60) -> str | None:
    unsorted_case = get_or_create_unsorted_case(db)
    event = (
        db.query(CaseEvent)
        .filter(
            CaseEvent.case_id == unsorted_case.id,
            CaseEvent.event_type == "folder_request_context",
        )
        .order_by(CaseEvent.created_at.desc())
        .first()
    )
    if not event:
        return None
    if event.created_at < datetime.utcnow() - timedelta(minutes=max_age_minutes):
        return None
    title = (event.body or "").strip()
    return title or None


def get_recent_document_batch(db: Session, *, max_gap_seconds: int = 180, max_age_minutes: int = 30) -> list[Document]:
    docs = db.query(Document).order_by(Document.created_at.desc()).limit(300).all()
    if not docs:
        return []
    latest_ts = docs[0].created_at
    min_ts = latest_ts - timedelta(minutes=max_age_minutes)
    batch: list[Document] = []
    previous_ts = latest_ts
    for doc in docs:
        if doc.created_at < min_ts:
            break
        if previous_ts and (previous_ts - doc.created_at).total_seconds() > max_gap_seconds and batch:
            break
        batch.append(doc)
        previous_ts = doc.created_at
    return list(reversed(batch))


def build_bulk_move_candidates(db: Session, keywords: list[str], *, docs_scope: list[Document] | None = None) -> list[Document]:
    docs = docs_scope if docs_scope is not None else db.query(Document).order_by(Document.created_at.asc()).all()
    result: list[Document] = []
    for doc in docs:
        haystack = f"{doc.filename}\n{doc.extracted_text or ''}".lower()
        if any(word.lower() in haystack for word in keywords):
            result.append(doc)
    return result


def ensure_chat_case(db: Session, title: str) -> tuple[Case, bool]:
    case = find_case_by_hint(db.query(Case).all(), title, db=db)
    created = False
    if not case:
        case = Case(
            title=title[:255],
            court_name="неизвестно",
            case_number=f"TAG-{uuid4().hex[:8].upper()}",
            status="analysis",
            stage="analysis",
        )
        db.add(case)
        db.commit()
        db.refresh(case)
        created = True
    return case, created


def preview_bulk_move_documents_to_case_by_keywords(
    db: Session, title: str, keywords: list[str], *, docs_scope: list[Document] | None = None, scope_label: str | None = None
) -> tuple[str, Case | None]:
    case, created = ensure_chat_case(db, title)

    existing_tags = {
        (tag.kind, tag.value.strip().lower())
        for tag in db.query(CaseTag).filter(CaseTag.case_id == case.id).all()
    }
    for word in keywords:
        key = ("keyword", word.strip().lower())
        if key not in existing_tags:
            db.add(CaseTag(case_id=case.id, value=word[:255], kind="keyword"))
    db.commit()

    docs = [doc for doc in build_bulk_move_candidates(db, keywords, docs_scope=docs_scope) if doc.case_id != case.id]
    db.query(PendingMovePlan).filter(PendingMovePlan.case_id == case.id).delete()
    db.add(
        PendingMovePlan(
            case_id=case.id,
            title=case.title,
            keywords_json=json.dumps(keywords, ensure_ascii=False),
            doc_ids_json=json.dumps([doc.id for doc in docs]),
        )
    )
    db.commit()
    summary = [
        f'{"Создал" if created else "Использовал"} дело "{case.title}" ({case.case_number}).',
        f"Ключевые слова: {', '.join(keywords)}.",
        f"Нашёл кандидатов на перенос{f' ({scope_label})' if scope_label else ''}: {len(docs)}.",
    ]
    if docs:
        summary.append("Проверь список ниже и ответь, например:")
        summary.append('`Да, перенеси все` или `Да, перенеси все, кроме 3, 7`')
        summary.append("Кандидаты:")
        for idx, doc in enumerate(docs[:50], start=1):
            summary.append(f"{idx}. [{doc.id}] {doc.filename}")
        if len(docs) > 50:
            summary.append(f"... и еще {len(docs) - 50}.")
    else:
        summary.append("Совпадений по документам не найдено.")
    return "\n".join(summary), case


def preview_collect_recent_archive_to_case(db: Session, title: str) -> tuple[str, Case | None]:
    recent_docs = get_recent_document_batch(db)
    if not recent_docs:
        return (
            "Не вижу недавней загрузки архива. Сначала загрузите ZIP или уточните документы по ключевым словам.",
            None,
        )
    case, created = ensure_chat_case(db, title)
    docs = [doc for doc in recent_docs if doc.case_id != case.id]
    db.query(PendingMovePlan).filter(PendingMovePlan.case_id == case.id).delete()
    db.add(
        PendingMovePlan(
            case_id=case.id,
            title=case.title,
            keywords_json=json.dumps(["__recent_archive__"], ensure_ascii=False),
            doc_ids_json=json.dumps([doc.id for doc in docs]),
        )
    )
    db.commit()
    summary = [
        f'{"Создал" if created else "Использовал"} дело "{case.title}" ({case.case_number}).',
        f"Взял документы из последнего загруженного архива: {len(recent_docs)} шт.",
        f"Кандидатов на перенос: {len(docs)}.",
    ]
    if docs:
        summary.append("Проверь список ниже и ответь, например:")
        summary.append('`Да, перенеси все` или `Да, перенеси все, кроме 3, 7`')
        summary.append("Кандидаты:")
        for idx, doc in enumerate(docs[:50], start=1):
            summary.append(f"{idx}. [{doc.id}] {doc.filename}")
        if len(docs) > 50:
            summary.append(f"... и еще {len(docs) - 50}.")
    else:
        summary.append("Все документы из последнего архива уже лежат в этом деле.")
    return "\n".join(summary), case


def parse_collect_folder_title(text: str) -> str:
    """Название новой папки из «…», \"…\", '…', «в папке …» или после «назови (её)»."""
    for pat in (r"«([^»]+)»", r'"([^"]+)"', r"'([^']+)'"):
        m = re.search(pat, text)
        if m:
            return m.group(1).strip()
    m = re.search(r"назови(?:те)?\s+(?:ее|её)?\s*[:\s,]*([^\n.!?]+?)(?:\s*$|[.!?])", text, flags=re.IGNORECASE)
    if m:
        return m.group(1).strip(" \t\"'«»")
    unquoted = extract_case_hint_from_folder_phrase(text)
    if unquoted:
        return unquoted
    return ""


def looks_like_rename_case_request(text: str) -> bool:
    """«Переименуй папку … в …», «смени название папки … на …»."""
    t = (text or "").lower()
    # «переименуйте» не совпадает с отдельным словом «переименуй» — нужно переименуй(?:те)?
    if re.search(r"\b(?:переименуй(?:те)?|переименовать)\b", t) and any(
        k in t for k in ("папк", "дело", "дела", "название")
    ):
        return True
    if re.search(r"(?:смени|измени)\s+название\s+(?:папк|дела)", t):
        return True
    if re.search(r"(?:поменяй|замени)\s+название\s+(?:папк[иы]|дела)", t):
        return True
    return False


def parse_rename_case_request(text: str) -> tuple[str, str] | None:
    """(подсказка старого названия или номера, новое название)."""
    t = (text or "").strip()
    if not t:
        return None
    m = re.search(
        r"(?:переименуй(?:те)?|переименовать)\s+(?:папк[ау]?|дело)\s+(?:«([^»]+)»|\"([^\"]+)\"|'([^']+)')\s+в\s+(?:«([^»]+)»|\"([^\"]+)\"|'([^']+)')",
        t,
        flags=re.IGNORECASE,
    )
    if m:
        old = next((g for g in m.groups()[:3] if g), "")
        new = next((g for g in m.groups()[3:] if g), "")
        if old.strip() and new.strip():
            return (old.strip(), new.strip())
    m = re.search(
        r"(?:переименуй(?:те)?|переименовать)\s+(?:папк[ау]?|дело)\s+(.+?)\s+в\s+(.+)$",
        t,
        flags=re.IGNORECASE | re.DOTALL,
    )
    if m:
        old = m.group(1).strip().strip('"\'«»')
        new = m.group(2).strip().strip('"\'«»')
        new = re.sub(r"[.!?…]+$", "", new).strip()
        if old and new:
            return (old, new)
    m = re.search(
        r"(?:смени|измени)\s+название\s+(?:папк[иы]|дела)\s+(.+?)\s+на\s+(.+)$",
        t,
        flags=re.IGNORECASE | re.DOTALL,
    )
    if m:
        old = m.group(1).strip().strip('"\'«»')
        new = m.group(2).strip().strip('"\'«»')
        new = re.sub(r"[.!?…]+$", "", new).strip()
        if old and new:
            return (old, new)
    m = re.search(
        r"(?:поменяй|замени)\s+название\s+(?:папк[иы]|дела)\s+(.+?)\s+на\s+(.+)$",
        t,
        flags=re.IGNORECASE | re.DOTALL,
    )
    if m:
        old = m.group(1).strip().strip('"\'«»')
        new = m.group(2).strip().strip('"\'«»')
        new = re.sub(r"[.!?…]+$", "", new).strip()
        if old and new:
            return (old, new)
    return None


def handle_rename_case_chat(db: Session, text: str) -> tuple[str, Case | None]:
    parsed = parse_rename_case_request(text)
    if not parsed:
        return (
            "Не разобрал переименование. Примеры:\n"
            "• переименуй папку «Старое» в «Новое»\n"
            "• переименуй папку Дело A40-19021/2025 в Банкротство Эмиль\n"
            "• смени название папки Старое на Новое",
            None,
        )
    old_hint, new_title = parsed
    if not new_title or len(new_title) > 255:
        return "Новое название пустое или слишком длинное (макс. 255 символов).", None
    cases = db.query(Case).all()
    case: Case | None = None
    extracted = extract_case_number(old_hint)
    if extracted:
        norm = normalize_arbitr_case_number(extracted)
        case = db.query(Case).filter(Case.case_number == norm).first()
    if not case:
        case = find_case_by_hint(cases, old_hint, db=db)
    if not case:
        return (
            f'Не нашёл папку по подсказке «{old_hint}». Уточните название как в списке дел или номер дела (например A40-19021/2025).',
            None,
        )
    prev = case.title
    case.title = new_title[:255]
    db.add(case)
    db.add(
        CaseEvent(
            case_id=case.id,
            event_type="case_renamed",
            body=f"Переименование папки: «{prev}» → «{case.title}»",
        )
    )
    db.commit()
    db.refresh(case)
    return (
        f'Готово: папка переименована «{prev}» → «{case.title}» (номер дела в системе: {case.case_number}).',
        case,
    )


def execute_move_all_documents_to_case_folder(db: Session, src: Case, target_title: str) -> tuple[str, Case | None]:
    """Перенос всех документов из дела src в папку target_title — сразу, без шага подтверждения."""
    tt = (target_title or "").strip()
    if not tt:
        return "Не вижу название папки назначения (куда переносить).", None
    docs = db.query(Document).filter(Document.case_id == src.id).order_by(Document.created_at.asc()).all()
    if not docs:
        return f'В деле «{src.title}» ({src.case_number}) нет документов для переноса.', None
    target_case, _created = ensure_chat_case(db, tt)
    if target_case.id == src.id:
        return "Источник и папка назначения совпадают — перенос не нужен.", None
    for doc in docs:
        old_case_id = doc.case_id
        doc.case_id = target_case.id
        db.add(
            CaseEvent(
                case_id=target_case.id,
                event_type="document_reclassified",
                body=f'Документ "{doc.filename}" перенесён из дела «{src.title}» ({src.case_number}).',
            )
        )
        db.add(
            CaseEvent(
                case_id=old_case_id,
                event_type="document_reclassified",
                body=f'Документ "{doc.filename}" перенесён в дело «{target_case.title}» ({target_case.case_number}).',
            )
        )
    db.commit()
    db.refresh(target_case)
    return (
        f"Готово: перенесено {len(docs)} документов из «{src.title}» ({src.case_number}) "
        f'в «{target_case.title}» ({target_case.case_number}).',
        target_case,
    )


def preview_move_all_documents_from_active_case_to_folder(
    db: Session, conversation: Conversation, title: str
) -> tuple[str, Case | None]:
    if not title:
        return (
            'Не вижу название папки в кавычках. Пример: Собери все документы в отдельную папку «Сделка по Гримме» '
            "или: Создай папку «Сделка по Гримме» и перенеси туда все документы, содержащие: A40-97353",
            None,
        )
    if not conversation.active_case_id:
        return (
            "Нет активного дела в чате. Сначала откройте дело (например «покажи документы по делу …»), "
            "затем повторите запрос.",
            None,
        )
    src = db.query(Case).filter(Case.id == conversation.active_case_id).first()
    if not src:
        return "Не удалось определить текущее дело.", None

    # Активное дело может быть «Неразобранное»: тогда «собери всё в папку …» означает
    # перенос всех документов из входящего ящика в новое дело — то же самое, что и для другого дела.
    docs = db.query(Document).filter(Document.case_id == src.id).order_by(Document.created_at.asc()).all()
    if not docs:
        return f'В деле «{src.title}» ({src.case_number}) пока нет документов для переноса.', None

    case, created = ensure_chat_case(db, title)
    if case.id == src.id:
        return "Новая папка совпадает с текущим делом — перенос не нужен.", None

    db.query(PendingMovePlan).filter(PendingMovePlan.case_id == case.id).delete()
    db.add(
        PendingMovePlan(
            case_id=case.id,
            title=case.title,
            keywords_json=json.dumps(["__from_active_case__"], ensure_ascii=False),
            doc_ids_json=json.dumps([doc.id for doc in docs]),
        )
    )
    db.commit()
    summary = [
        f'{"Создал" if created else "Использую"} дело «{case.title}» ({case.case_number}).',
        f"Документы из текущего дела «{src.title}» ({src.case_number}): {len(docs)} шт.",
        "Проверьте список и ответьте, например:",
        "`Да, перенеси все` или `Да, перенеси все, кроме 3, 7`",
        "Кандидаты:",
    ]
    for idx, doc in enumerate(docs[:50], start=1):
        summary.append(f"{idx}. [{doc.id}] {doc.filename}")
    if len(docs) > 50:
        summary.append(f"... и еще {len(docs) - 50}.")
    return "\n".join(summary), case


def apply_pending_move_plan(db: Session, text: str) -> tuple[str, Case | None]:
    plan = db.query(PendingMovePlan).order_by(PendingMovePlan.created_at.desc()).first()
    if not plan:
        return "Нет активного списка на перенос. Сначала попросите создать папку и подобрать документы.", None
    target_case = db.query(Case).filter(Case.id == plan.case_id).first()
    if not target_case:
        return "Не нашёл дело для активного списка переноса.", None
    planned_ids = json.loads(plan.doc_ids_json or "[]")
    all_cases = db.query(Case).all()
    alternate_moves: dict[int, Case] = {}
    for m in re.finditer(r"(\d+)\s*(?:и\s*(\d+))?\s*.*?перенеси\s+в\s+дел[оау]\s+([^.;\n]+)", text, flags=re.IGNORECASE):
        nums = [m.group(1), m.group(2)]
        case_hint = (m.group(3) or "").strip(" .:-")
        alt_case = find_case_by_hint(all_cases, case_hint, db=db)
        if not alt_case:
            continue
        for raw_num in nums:
            if raw_num:
                alternate_moves[int(raw_num)] = alt_case

    exclude_numbers = {
        int(x)
        for x in re.findall(r"\b(\d+)\b", text)
        if int(x) not in alternate_moves
    }
    docs = db.query(Document).filter(Document.id.in_(planned_ids)).order_by(Document.created_at.asc()).all()
    moved: list[str] = []
    moved_total = 0
    rerouted: list[str] = []
    excluded_docs: list[tuple[int, Document]] = []
    for idx, doc in enumerate(docs, start=1):
        if idx in alternate_moves:
            alt_case = alternate_moves[idx]
            old_case_id = doc.case_id
            doc.case_id = alt_case.id
            db.add(CaseEvent(case_id=alt_case.id, event_type="document_reclassified", body=f'Документ "{doc.filename}" перенесён по вашему уточнению.'))
            db.add(CaseEvent(case_id=old_case_id, event_type="document_reclassified", body=f'Документ "{doc.filename}" перенесён в дело "{alt_case.title}" по уточнению в чате.'))
            moved_total += 1
            if len(rerouted) < 20:
                rerouted.append(f"{idx}. [{doc.id}] {doc.filename} -> {alt_case.title}")
            continue
        if idx in exclude_numbers:
            excluded_docs.append((idx, doc))
            continue
        old_case_id = doc.case_id
        doc.case_id = target_case.id
        db.add(CaseEvent(case_id=target_case.id, event_type="document_reclassified", body=f'Документ "{doc.filename}" перенесён по подтверждённому списку.'))
        db.add(CaseEvent(case_id=old_case_id, event_type="document_reclassified", body=f'Документ "{doc.filename}" перенесён в дело "{target_case.title}" по подтверждённому списку.'))
        moved_total += 1
        if len(moved) < 20:
            moved.append(f"{idx}. [{doc.id}] {doc.filename}")
    db.delete(plan)
    db.commit()
    lines = [f'Перенёс документы в дело "{target_case.title}" ({target_case.case_number}). Перенесено: {moved_total}.']
    if exclude_numbers:
        lines.append("Исключены из переноса номера: " + ", ".join(str(x) for x in sorted(exclude_numbers)))
    if excluded_docs:
        lines.append("Что можно сделать с исключёнными документами:")
        all_cases = db.query(Case).all()
        for idx, doc in excluded_docs[:12]:
            suggestions: list[str] = []
            for case in all_cases:
                if case.id == target_case.id or case.case_number == "UNSORTED":
                    continue
                confidence = 0.0
                haystack = f"{doc.filename}\n{doc.extracted_text or ''}".lower()
                title_norm = case.title.lower()
                if title_norm and title_norm[:12] in haystack:
                    confidence += 0.35
                for tag in getattr(case, "tags", []):
                    token = tag.value.lower()
                    if token and token in haystack:
                        confidence += 0.7 if tag.kind == "alias" else 0.45
                if confidence >= 0.45:
                    suggestions.append(f'{case.title} ({confidence:.2f})')
            if suggestions:
                lines.append(f"{idx}. [{doc.id}] {doc.filename} -> возможно: " + "; ".join(suggestions[:3]))
            else:
                lines.append(f"{idx}. [{doc.id}] {doc.filename} -> явного дела не найдено, оставлен без переноса")
    if moved:
        lines.append("Что перенесено:")
        lines.extend(moved)
    if rerouted:
        lines.append("Что перенесено в другие дела по вашему уточнению:")
        lines.extend(rerouted)
    return "\n".join(lines), target_case


async def summarize_documents_for_case(case: Case, docs: list[Document], *, chronology: bool) -> str:
    if not docs:
        return f'По делу "{case.title}" пока нет документов для разбора.'
    snippets: list[str] = []
    for doc in docs[:15]:
        text_sample = (doc.extracted_text or "").strip()
        text_sample = re.sub(r"\s+", " ", text_sample)[:900]
        if not text_sample:
            text_sample = "Текст не извлечён."
        snippets.append(f"Файл: {doc.filename}\nКатегория: {doc.category}\nТекст: {text_sample}")
    prompt = (
        "Ты помощник по разбору судебных документов.\n"
        + (
            "Собери хронологию по документам: даты, события, участники, что произошло. "
            "Не выдумывай факты, пиши только то, что видно из материалов.\n\n"
            if chronology
            else "Кратко разложи документы по смыслу: что это за документы, какие важные факты, лица, сроки и что стоит посмотреть дальше.\n\n"
        )
        + f'Дело: {case.title} ({case.case_number})\n\n'
        + "\n\n".join(snippets)
    )
    try:
        return await llm_summary(prompt)
    except Exception as exc:
        return f"Не удалось разобрать документы автоматически: {exc}"


def search_documents(case: Case, docs: list[Document], query: str) -> str:
    if not docs:
        return f'По делу "{case.title}" пока нет документов.'
    norm_query = query.lower()
    matched = [
        doc
        for doc in docs
        if norm_query in doc.filename.lower()
        or norm_query in doc.category.lower()
        or norm_query in (doc.extracted_text or "").lower()
    ]
    if not matched:
        return f'По запросу "{query}" в деле "{case.title}" ничего не найдено.'
    lines = [f'Нашёл {len(matched)} документ(ов) по запросу "{query}" в деле "{case.title}":']
    for doc in matched[:20]:
        lines.append(f'- [{doc.id}] {doc.filename} | {doc.category} | скачать: /api/documents/{doc.id}/download')
    if len(matched) > 20:
        lines.append(f"... и еще {len(matched) - 20}.")
    return "\n".join(lines)


def search_documents_global_with_hints(db: Session, hints: list[str], *, limit: int = 40) -> str:
    """Поиск по всем делам по уже разобранным фразам (в т.ч. из NL-router)."""
    expanded: list[str] = []
    for h in hints:
        for part in re.split(r"\s+(?:или|либо)\s+", h or "", flags=re.IGNORECASE):
            p = part.strip().strip(" ,.:-—")
            if len(p) >= 2:
                expanded.append(p)
    hints = expanded if expanded else [x.strip() for x in hints if len((x or "").strip()) >= 2]
    if not hints:
        return (
            "Не понял, что искать во всех папках. Пример: «найди во всех папках документы с именем Эмилия» "
            "или «поиск по всем делам: Рочева»."
        )
    collected: dict[int, Document] = {}
    for h in hints:
        for d in _collect_documents_matching_delete_hints(db, [h]):
            collected[d.id] = d
    total = len(collected)
    matched = sorted(collected.values(), key=lambda d: d.id, reverse=True)[:limit]
    if not matched:
        return f'По запросу «{"; ".join(hints)}» в документах всех папок ничего не найдено.'
    case_ids = {d.case_id for d in matched}
    cases_map = {c.id: c for c in db.query(Case).filter(Case.id.in_(case_ids)).all()}
    lines = [
        f"Нашёл {total} документ(ов) во всех папках по запросу «{' / '.join(hints[:4])}»"
        + (f" (показываю {len(matched)}):" if total > len(matched) else ":")
    ]
    for doc in matched:
        c = cases_map.get(doc.case_id)
        cnum = c.case_number if c else "?"
        ctitle = c.title if c else "?"
        if ctitle and len(ctitle) > 52:
            ctitle = ctitle[:50] + "…"
        lines.append(
            f"- [{doc.id}] {doc.filename} | папка: {ctitle} ({cnum}) | скачать: /api/documents/{doc.id}/download"
        )
    if total > limit:
        lines.append(f"… всего совпадений: {total}. Сузьте фразу в кавычках для точного поиска.")
    return "\n".join(lines)


def search_documents_global(db: Session, user_text: str, *, limit: int = 40) -> str:
    """Поиск документов по всем делам (имя файла и извлечённый текст PDF)."""
    hints = _extract_delete_target_phrases(user_text)
    raw_q = extract_search_query(user_text)
    if not hints:
        nq = normalize_global_search_query(raw_q)
        if len(nq) >= 2:
            hints = [nq]
    if not hints:
        return (
            "Не понял, что искать во всех папках. Пример: «найди во всех папках документы с именем Эмилия» "
            "или «поиск по всем делам: Рочева»."
        )
    return search_documents_global_with_hints(db, hints, limit=limit)


def search_documents_union_queries(case: Case, docs: list[Document], queries: list[str]) -> str:
    """Поиск в одном деле: достаточно вхождения любой из фраз (как сформулировала модель)."""
    if not docs:
        return f'По делу «{case.title}» пока нет документов.'
    qn = [q.strip().lower() for q in queries if len(q.strip()) >= 2]
    if not qn:
        return "Уточните, что искать."
    matched: list[Document] = []
    seen: set[int] = set()
    for doc in docs:
        hay = f"{doc.filename}\n{doc.category}\n{doc.extracted_text or ''}".lower()
        if any(q in hay for q in qn):
            if doc.id not in seen:
                seen.add(doc.id)
                matched.append(doc)
    if not matched:
        show = ", ".join(repr(q) for q in queries[:5])
        return f"По фразам {show} в деле «{case.title}» ничего не найдено."
    lines = [
        f'Нашёл {len(matched)} документ(ов) в деле «{case.title}» (совпала любая из фраз):',
    ]
    for doc in matched[:25]:
        lines.append(f'- [{doc.id}] {doc.filename} | {doc.category} | скачать: /api/documents/{doc.id}/download')
    if len(matched) > 25:
        lines.append(f"... и ещё {len(matched) - 25}.")
    return "\n".join(lines)


def _move_all_case_content_to_target(db: Session, source: Case, target: Case) -> int:
    """Перенос документов (с чанками), задач, событий и тегов source → target. Возвращает число документов."""
    n = 0
    for doc in db.query(Document).filter(Document.case_id == source.id).all():
        doc.case_id = target.id
        db.add(doc)
        sync_document_chunks(db, doc)
        n += 1
    db.query(Task).filter(Task.case_id == source.id).update({Task.case_id: target.id}, synchronize_session=False)
    db.query(CaseEvent).filter(CaseEvent.case_id == source.id).update(
        {CaseEvent.case_id: target.id}, synchronize_session=False
    )
    existing = {
        (t.kind, t.value.strip().lower())
        for t in db.query(CaseTag).filter(CaseTag.case_id == target.id).all()
    }
    for tag in db.query(CaseTag).filter(CaseTag.case_id == source.id).all():
        key = (tag.kind, tag.value.strip().lower())
        if key not in existing:
            db.add(CaseTag(case_id=target.id, value=tag.value, kind=tag.kind))
            existing.add(key)
    db.query(CaseTag).filter(CaseTag.case_id == source.id).delete(synchronize_session=False)
    db.query(PendingMovePlan).filter(PendingMovePlan.case_id == source.id).update(
        {PendingMovePlan.case_id: target.id}, synchronize_session=False
    )
    db.query(Conversation).filter(Conversation.active_case_id == source.id).update(
        {Conversation.active_case_id: target.id}, synchronize_session=False
    )
    db.query(ConversationMessage).filter(ConversationMessage.case_id == source.id).update(
        {ConversationMessage.case_id: target.id}, synchronize_session=False
    )
    db.query(CaseEmbedding).filter(CaseEmbedding.case_id == source.id).update(
        {CaseEmbedding.case_id: target.id}, synchronize_session=False
    )
    db.query(CourtCaseSource).filter(CourtCaseSource.case_id == source.id).update(
        {CourtCaseSource.case_id: target.id}, synchronize_session=False
    )
    return n


def _pick_merge_target_case(db: Session, cases: list[Case]) -> Case:
    """Приоритет: «настоящий» номер арбитража, не TAG-*, больше документов."""
    scored: list[tuple[int, int, Case]] = []
    for c in cases:
        score = 0
        cn = c.case_number or ""
        if looks_like_stored_arbitr_case_number(cn):
            score += 200
        if cn.upper().startswith("TAG-"):
            score -= 50
        nd = db.query(Document).filter(Document.case_id == c.id).count()
        score += min(nd, 80)
        scored.append((score, c.id, c))
    scored.sort(key=lambda x: (-x[0], -x[1]))
    return scored[0][2]


def parse_merge_case_hints(text: str) -> list[str]:
    t = (text or "").strip()
    quoted = [a or b for a, b in re.findall(r'«([^»]+)»|"([^"]+)"', t)]
    if len(quoted) >= 2:
        return [q.strip() for q in quoted if len(q.strip()) >= 2][:15]
    m = re.search(
        r"(?:объедини|соедини|слей|смержи)\s+(?:эти\s+)?(?:папки|папку|дела|дело)\s+(.+)$",
        t,
        flags=re.IGNORECASE | re.DOTALL,
    )
    if not m:
        return []
    blob = re.sub(r"[.!?…]+$", "", m.group(1).strip())
    parts = re.split(r"\s+\bи\b\s+", blob, flags=re.IGNORECASE)
    out: list[str] = []
    for p in parts:
        p = re.sub(r"^(?:папк[ауеи]?\s+|дел[оа]\s+)", "", p, flags=re.I).strip().strip(' "\'«»')
        if len(p) >= 2:
            out.append(p)
    return out[:15]


def looks_like_merge_cases_request(text: str) -> bool:
    t = (text or "").lower()
    if not re.search(r"\b(?:объедини|соедини|слей|смержи)\b", t):
        return False
    return bool(re.search(r"\b(?:папк|дел)", t))


def handle_merge_cases_chat(db: Session, text: str) -> tuple[str, Case | None]:
    hints = parse_merge_case_hints(text)
    if len(hints) < 2:
        return (
            "Укажите минимум две папки. Примеры:\n"
            "• объедини папки «Банкротство Эмиль» и «Дело А40-19021/2025»\n"
            "• объедини папки TAG-26076AAD и A40-19021/2025",
            None,
        )
    all_cases = db.query(Case).all()
    resolved: list[Case] = []
    seen: set[int] = set()
    for h in hints:
        case: Case | None = None
        ext = extract_case_number(h)
        if ext:
            norm = normalize_arbitr_case_number(ext)
            case = db.query(Case).filter(Case.case_number == norm).first()
        if not case:
            case = find_case_by_hint(all_cases, h, db=db)
        if not case:
            return f'Не нашёл папку по подсказке «{h}». Уточните название или номер дела.', None
        if case.id not in seen:
            seen.add(case.id)
            resolved.append(case)
    if len(resolved) < 2:
        return "Нужны две разные папки (сейчас совпадают или найдена одна).", None
    if any((x.case_number or "").upper() == "UNSORTED" for x in resolved):
        return "Объединение с папкой «Неразобранное» (UNSORTED) не поддерживается.", None
    target = _pick_merge_target_case(db, resolved)
    sources = [c for c in resolved if c.id != target.id]
    lines_body: list[str] = []
    total_docs = 0
    for src in sources:
        n = _move_all_case_content_to_target(db, src, target)
        total_docs += n
        lines_body.append(f"— «{src.title}» ({src.case_number}): перенесено документов: {n}")
        db.add(
            CaseEvent(
                case_id=target.id,
                event_type="case_merge",
                body=f"Объединено из «{src.title}» ({src.case_number})",
            )
        )
        db.delete(src)
    db.commit()
    db.refresh(target)
    head = (
        f"Объединил папки в одну. Целевая папка: «{target.title}» ({target.case_number}). "
        f"Всего перенесено документов: {total_docs}.\n"
    )
    return head + "\n".join(lines_body), target


def looks_like_merge_duplicate_folders_request(text: str) -> bool:
    """Объединить папки автоматически, если в них дублируются одни и те же имена файлов."""
    t = (text or "").lower()
    if not re.search(r"\b(?:объедини|соедини|слей|смержи)\b", t):
        return False
    return any(
        k in t
        for k in (
            "дубл",
            "одинаков",
            "одно дело",
            "одно и то же",
            "повтор",
            "совпадающ",
            "совпадению файлов",
            "по файлам",
            "где те же файлы",
            "склей дубли",
        )
    )


def handle_merge_cases_linked_by_duplicate_filenames(db: Session) -> tuple[str, Case | None]:
    """Связные компоненты: дела A и B связаны, если есть одинаковое имя файла в обоих. UNSORTED не участвует."""
    from collections import defaultdict

    groups: dict[str, list[tuple[int, int]]] = defaultdict(list)  # norm_name -> [(doc_id, case_id)]
    for d in db.query(Document).all():
        c = db.query(Case).filter(Case.id == d.case_id).first()
        if not c or (c.case_number or "").upper() == "UNSORTED":
            continue
        key = normalize_document_signature(d.filename, "")[0]
        if len(key) < 4:
            continue
        groups[key].append((d.id, c.id))

    adj: dict[int, set[int]] = defaultdict(set)
    for _fname, rows in groups.items():
        cids = {cid for _, cid in rows}
        if len(cids) < 2:
            continue
        cl = list(cids)
        for i in range(len(cl)):
            for j in range(i + 1, len(cl)):
                adj[cl[i]].add(cl[j])
                adj[cl[j]].add(cl[i])

    if not adj:
        return (
            "Нет пар папок с одинаковыми именами файлов — объединять нечего. "
            "Сначала попросите отчёт: «найди одинаковые документы в разных папках».",
            None,
        )

    visited: set[int] = set()
    components: list[list[int]] = []
    for start in adj:
        if start in visited:
            continue
        stack = [start]
        visited.add(start)
        comp: list[int] = []
        while stack:
            x = stack.pop()
            comp.append(x)
            for y in adj[x]:
                if y not in visited:
                    visited.add(y)
                    stack.append(y)
        components.append(comp)

    merged_lines: list[str] = []
    last_target: Case | None = None
    total_merged_folders = 0
    for comp in components:
        if len(comp) < 2:
            continue
        cases = [db.query(Case).filter(Case.id == cid).first() for cid in comp]
        cases = [c for c in cases if c and (c.case_number or "").upper() != "UNSORTED"]
        if len(cases) < 2:
            continue
        target = _pick_merge_target_case(db, cases)
        sources = [c for c in cases if c.id != target.id]
        sub: list[str] = []
        for src in sources:
            n = _move_all_case_content_to_target(db, src, target)
            sub.append(f"«{src.title}» ({src.case_number}) → перенесено записей/документов: {n}")
            db.add(
                CaseEvent(
                    case_id=target.id,
                    event_type="case_merge",
                    body=f"Авто-объединение по дублям файлов из «{src.title}» ({src.case_number})",
                )
            )
            db.delete(src)
            total_merged_folders += 1
        merged_lines.append(
            f"В целевую папку «{target.title}» ({target.case_number}):\n"
            + "\n".join(f"  — {s}" for s in sub)
        )
        last_target = target

    if not merged_lines:
        return (
            "Связных групп папок по совпадению имён файлов не найдено (или все дела уже разделены).",
            None,
        )
    db.commit()
    if last_target:
        db.refresh(last_target)
    head = f"Объединил папки по совпадению имён файлов. Убрано лишних папок: {total_merged_folders}.\n\n"
    return head + "\n\n".join(merged_lines), last_target


def looks_like_delete_all_empty_folders(text: str) -> bool:
    """Удалить все дела/папки, в которых нет ни одного документа (пустые карточки)."""
    t = (text or "").lower()
    if not re.search(r"\b(?:удали|удалить|убери|убрать|очисти)\b", t):
        return False
    if "папк" not in t and not re.search(r"\bдел[а-яё]*\b", t):
        return False
    emptyish = (
        "пуст" in t
        or "без документ" in t
        or "нет документ" in t
        or "ни одного документ" in t
        or "ни одного файла" in t
        or "не содержат документ" in t
        or "не содержит документ" in t
        or "не содержащ" in t
        or "без файлов" in t
        or "без вложен" in t
    )
    if not emptyish:
        return False
    if "все" in t or "всё" in t or "кажд" in t:
        return True
    if "пуст" in t:
        return True
    if "без документ" in t or "без файлов" in t or "нет документ" in t:
        return True
    return False


def looks_like_delete_case_folder_request(text: str) -> bool:
    t = (text or "").lower()
    if looks_like_delete_all_empty_folders(text):
        return False
    if not re.search(r"\b(?:удали|убери|удалить)\b", t):
        return False
    # «папку», «папке» — не совпадут с \bпапк\b (после «к» буква «у»).
    if not re.search(r"\b(?:папк[а-яё]*|дел[а-яё]*)\b", t):
        return False
    if re.search(r"\b(?:документ|файл)\b", t):
        return False
    return True


def might_be_delete_case_folder_llm(text: str) -> bool:
    """Слабая эвристика: возможно, речь об удалении папки — тогда добираем смысл через LLM."""
    t = (text or "").lower()
    if looks_like_delete_all_empty_folders(text):
        return False
    if any(x in t for x in ("не удали", "не удаляй", "не убирай", "не удалить")):
        return False
    if not any(k in t for k in ("удали", "удалить", "убери", "убрать")):
        return False
    if any(k in t for k in ("документ", "файл", "pdf", "вложен", "attachment")):
        return False
    if "папк" in t:
        return True
    if re.search(r"\bдел[а-яё]*\b", t):
        return True
    if "folder" in t or re.search(r"\bcase\b", t, flags=re.IGNORECASE):
        return True
    return False


async def resolve_delete_folder_hint(
    text: str,
    cases: list[Case],
    *,
    active_case: Case | None,
) -> str | None:
    if looks_like_delete_case_folder_request(text):
        h = parse_delete_case_folder_hint(text)
        if h:
            return h
    if not might_be_delete_case_folder_llm(text):
        return None
    if not settings.openai_api_key.strip():
        return None
    try:
        return await llm_parse_delete_case_folder_request(text, cases, active_case=active_case)
    except Exception:
        return None


def parse_delete_case_folder_hint(text: str) -> str:
    t = (text or "").strip()
    # Между глаголом и «папку/дело» допускаются слова вроде «полностью», «навсегда».
    _cmd = r"(?:удали|убери|удалить)(?:\s+[а-яёa-z0-9-]{2,}){0,6}\s+(?:папк[а-яё]*|дел[а-яё]*)\s+"
    m = re.search(
        _cmd + r"(?:«([^»]+)»|\"([^\"]+)\"|'([^']+)')",
        t,
        flags=re.I,
    )
    if m:
        return next(g for g in m.groups() if g).strip()
    m = re.search(_cmd + r"(.+)$", t, flags=re.I | re.DOTALL)
    if m:
        raw = re.sub(r"[.!?…]+$", "", m.group(1).strip()).strip(' "\'«»')
        # Не принимать описательный хвост за имя папки («…папки не содержащие документов»).
        if re.match(r"^(?:не\s+содержа|содержащ(?:ие|их)?\s)", raw, flags=re.I):
            return ""
        return raw
    return ""


def handle_delete_case_folder_chat(
    db: Session,
    text: str,
    *,
    hint_override: str | None = None,
) -> tuple[str, Case | None]:
    hint = hint_override.strip() if hint_override else parse_delete_case_folder_hint(text)
    if not hint:
        return (
            "Не понял, какую папку удалить. Примеры:\n"
            "• удали папку «Банкротство Эмиль»\n"
            "• удали папку A40-97353/2020\n"
            "Документы будут перенесены в «Неразобранное», затем папка удалится.",
            None,
        )
    all_cases = db.query(Case).all()
    case: Case | None = None
    ext = extract_case_number(hint)
    if ext:
        norm = normalize_arbitr_case_number(ext)
        case = db.query(Case).filter(Case.case_number == norm).first()
    if not case:
        case = find_case_by_hint(all_cases, hint, db=db)
    if not case:
        return f'Не нашёл папку по подсказке «{hint}».', None
    if (case.case_number or "").upper() == "UNSORTED":
        return "Папку «Неразобранное» удалить нельзя.", None
    unsorted = get_or_create_unsorted_case(db)
    n = _move_all_case_content_to_target(db, case, unsorted)
    tit, num = case.title, case.case_number
    db.delete(case)
    db.commit()
    db.refresh(unsorted)
    return (
        f"Папка «{tit}» ({num}) удалена. Документов и связанных записей перенесено в неразобранное: {n}.",
        unsorted,
    )


def handle_delete_all_empty_case_folders_chat(
    db: Session, conversation: Conversation
) -> tuple[str, Case | None]:
    """Удаляет все Case без Document (кроме UNSORTED); задачи/события/теги — в неразобранное."""
    unsorted = get_or_create_unsorted_case(db)
    to_delete: list[Case] = []
    for c in db.query(Case).order_by(Case.id.asc()).all():
        if (c.case_number or "").upper() == "UNSORTED":
            continue
        n_docs = db.query(Document).filter(Document.case_id == c.id).count()
        if n_docs == 0:
            to_delete.append(c)
    if not to_delete:
        return (
            "Пустых папок не найдено: у каждого дела есть хотя бы один документ, либо осталась только «Неразобранное».",
            conversation.active_case or unsorted,
        )
    active_id = conversation.active_case_id
    removed_titles: list[str] = []
    for c in to_delete:
        _move_all_case_content_to_target(db, c, unsorted)
        tit, num = c.title, c.case_number
        db.delete(c)
        removed_titles.append(f"«{tit}» ({num})")
    db.commit()
    db.refresh(unsorted)
    if active_id and not db.query(Case).filter(Case.id == active_id).first():
        conversation.active_case_id = unsorted.id
        db.add(conversation)
        db.commit()
    lines = [
        f"Удалено пустых папок: {len(to_delete)}. Файлов в них не было; задачи, события и теги перенесены в «Неразобранное».",
        "",
        "Список:",
    ]
    lines.extend(f"• {x}" for x in removed_titles[:45])
    if len(removed_titles) > 45:
        lines.append(f"… и ещё {len(removed_titles) - 45}.")
    return "\n".join(lines), unsorted


_RECENT_UPLOAD_LOOKBACK_MINUTES = 45


def _extract_filename_hint_from_user_text(text: str) -> str:
    for pat in (r"«([^»]{2,})»", r'"([^"]{2,})"', r"'([^']{2,})'"):
        m = re.search(pat, text or "")
        if m:
            return m.group(1).strip()
    return ""


def looks_like_where_was_upload_saved_question(text: str) -> bool:
    """Куда ушёл только что загруженный файл (в продукте «папка» = дело / Case)."""
    if looks_like_show_documents_in_folder_only(text):
        return False
    low = (text or "").lower()
    where = (
        "в какую папку",
        "какую папку",
        "куда положил",
        "куда сохранил",
        "куда ты положил",
        "куда ты сохранил",
        "куда делся",
        "куда загрузил",
        "куда файл",
        "куда документ",
        "в какое дело",
        "к какому делу",
        "в какой папке",
        "где лежит",
        "где сейчас",
        "где этот файл",
        "где этот документ",
    )
    if not any(w in low for w in where):
        return False
    return any(
        k in low
        for k in (
            "документ",
            "файл",
            "загруз",
            "прикреп",
            "положил",
            "сохранил",
            "этот",
            "эту",
            "это ",
            "папк",
            "дело",
        )
    )


def answer_where_recent_upload_saved(
    db: Session, text: str, conversation: Conversation
) -> tuple[str, Case] | None:
    """Ответ по факту в БД: последние загрузки (окно времени), без LLM. Второй элемент — дело-папка файла."""
    if not looks_like_where_was_upload_saved_question(text):
        return None
    since = datetime.utcnow() - timedelta(minutes=_RECENT_UPLOAD_LOOKBACK_MINUTES)
    recent = (
        db.query(Document)
        .filter(Document.created_at >= since)
        .order_by(Document.created_at.desc())
        .limit(12)
        .all()
    )
    fallback_case = conversation.active_case or get_or_create_unsorted_case(db)
    if not recent:
        return (
            f"За последние ~{_RECENT_UPLOAD_LOOKBACK_MINUTES} мин. не вижу новых файлов в базе. "
            "Если загрузка прошла, повторите вопрос через несколько секунд или укажите имя файла в кавычках. "
            "Папка в приложении — это дело в списке слева; документ виден во вкладке документов этого дела.",
            fallback_case,
        )

    hint = _extract_filename_hint_from_user_text(text)
    chosen: Document | None = None
    if hint:
        hn = hint.lower()
        for d in recent:
            fn = (d.filename or "").lower()
            if hn in fn or fn in hn:
                chosen = d
                break
    if not chosen and conversation.active_case_id:
        for d in recent:
            if d.case_id == conversation.active_case_id:
                chosen = d
                break
    if not chosen:
        chosen = recent[0]

    case = db.query(Case).filter(Case.id == chosen.case_id).first()
    if not case:
        return None

    parts = [
        f'Файл «{chosen.filename}» сохранён в папке «{case.title}» (дело {case.case_number}). '
        f"Категория: {chosen.category}."
    ]
    if len(recent) >= 2 and chosen is recent[0] and not hint:
        parts.append(
            "Если речь о другом только что загруженном файле — напишите его имя в кавычках «…»."
        )
    ac = conversation.active_case
    if ac and ac.id != case.id:
        parts.append(
            f'Ранее в чате была открыта другая папка: «{ac.title}» ({ac.case_number}). '
            f"Сейчас подсказка относится к делу {case.case_number}."
        )
    return "\n".join(parts), case


def handle_court_sync_chat_command(
    db: Session,
    text: str,
    user_role: str,
    *,
    active_case_id: int | None = None,
    active_case_title: str | None = None,
    active_case_number: str | None = None,
) -> str | None:
    lowered = text.lower()
    _kad_date_range = parse_calendar_period_ru(text)
    _kad_period_label = describe_calendar_period_ru(text) if _kad_date_range else None
    if looks_like_cancel_court_sync_jobs(text):
        stats = cancel_active_court_sync_jobs(db)
        n = int(stats.get("cancelled", 0))
        return (
            f"Снято задач: {n}. Очередь и активные загрузки помечены как отменённые; воркер прекращает скачивание между файлами. "
            "Повторный запрос с тем же текстом не создаёт вторую параллельную задачу, пока первая не завершена — это ограничивает дубли."
        )
    if looks_like_kad_downloaded_documents_list(text):
        return format_kad_downloaded_documents_list(
            db, date_range=_kad_date_range, period_label=_kad_period_label
        )
    if looks_like_court_download_count_question(text):
        return format_kad_download_count_answer(
            db, date_range=_kad_date_range, period_label=_kad_period_label
        )
    if looks_like_court_download_status_question(text):
        return format_recent_download_jobs_status(
            db, date_range=_kad_date_range, period_label=_kad_period_label
        )
    if "статус синхронизации" in lowered:
        return format_sync_status(db)
    if "что нового скачано за ночь" in lowered:
        return format_nightly_report(db)
    # «№35», «#35», «номер 35» после «задаче»; только «#?» не ловит Unicode №.
    m_job = re.search(
        r"(?:(?:дай|покажи|пришли|нужен|нужно)\s+)?"
        r"(?:отчет|отчёт)\s+(?:по\s+)?задач[еаи]\s*(?:#|№)?\s*(?:номер\s*)?(\d+)",
        lowered,
    )
    if m_job:
        job_id = int(m_job.group(1))
        job = db.query(CourtSyncJob).filter(CourtSyncJob.id == job_id).first()
        if not job:
            return f"Задача #{job_id} не найдена."
        text = job.report_text.strip() or "(отчет пуст)"
        return f"Отчет по задаче #{job.id} ({job.status}, шаг: {job.step}):\n{text}"

    after_parse = parse_court_search_request(text)
    request = try_resolve_kad_folder_title_to_case_number(db, text, after_parse)
    parsed_before_override = request
    title_hint_kad = extract_kad_folder_title_hint(text)
    resolved_case_title_to_number = bool(
        title_hint_kad
        and after_parse
        and after_parse.query_type in ("participant_name", "organization_name")
        and request
        and request.query_type == "case_number"
    )
    extra_doc_case_numbers: list[str] = []
    replaced_from_documents = False
    if request and active_case_id:
        request, extra_doc_case_numbers, replaced_from_documents = apply_folder_documents_case_numbers_to_kad_request(
            db,
            text,
            request,
            active_case_id=active_case_id,
            active_case_title=active_case_title,
        )
    if request:
        request = apply_active_case_number_to_kad_request(
            text,
            request,
            active_case_title=active_case_title,
            active_case_number=active_case_number,
        )
    if not request:
        return None

    used_folder_case_number = bool(
        parsed_before_override
        and request
        and parsed_before_override.query_type in ("participant_name", "organization_name")
        and request.query_type == "case_number"
    )
    if replaced_from_documents:
        nums_shown = [request.query_value] + extra_doc_case_numbers
        folder_hint = (
            " Номера дел для КАД взяты из документов в этой папке (имена файлов и текст): "
            + ", ".join(f"«{n}»" for n in nums_shown)
            + "."
        )
    elif used_folder_case_number:
        folder_hint = (
            f" Номер дела взят из карточки папки ({active_case_title or active_case_number})."
        )
    elif resolved_case_title_to_number:
        folder_hint = f' Номер дела взят из вашего списка папок по названию «{title_hint_kad}» → {request.query_value}.'
    else:
        folder_hint = ""

    if "поставь на отслеживание" in lowered:
        profile, created = create_watch_profile(
            db,
            profile_type=request.query_type,
            query_value=request.query_value,
            title=request.query_value,
            auto_download=True,
        )
        job, job_new = create_sync_job(
            db,
            query_type=request.query_type,
            query_value=request.query_value,
            run_mode="sync",
            requested_by=user_role,
            trigger_type="manual",
            watch_profile_id=profile.id,
            parser_year_min=request.parser_year_min,
            parser_year_max=request.parser_year_max,
        )
        return (
            f'{"Добавил" if created else "Уже отслеживается"} профиль "{request.query_value}" '
            f'({request.query_type}). '
            f'{"Создана задача синхронизации" if job_new else "Уже есть активная задача синхронизации"} #{job.id}.'
            f"{folder_hint}"
        )

    def _wants_kad_download(qt: str, low: str) -> bool:
        if qt == "card_url":
            return True
        if any(p in low for p in ("не скачай", "не скачивай", "не надо скачивать")):
            return False
        if "скачай" in low or "скачайте" in low:
            return True
        if any(
            p in low
            for p in (
                "проверь кад на наличие новых",
                "проверь кад на новые",
                "новые документы по делу",
                "есть ли новые документы",
            )
        ):
            return True
        return False

    run_mode = "download" if _wants_kad_download(request.query_type, lowered) else "preview"
    job, job_new = create_sync_job(
        db,
        query_type=request.query_type,
        query_value=request.query_value,
        run_mode=run_mode,
        requested_by=user_role,
        parser_year_min=request.parser_year_min,
        parser_year_max=request.parser_year_max,
    )
    extra_job_ids: list[int] = []
    for extra_cn in extra_doc_case_numbers:
        ej, _ = create_sync_job(
            db,
            query_type="case_number",
            query_value=extra_cn,
            run_mode=run_mode,
            requested_by=user_role,
            parser_year_min=request.parser_year_min,
            parser_year_max=request.parser_year_max,
        )
        extra_job_ids.append(ej.id)
    job_ids_label = ", ".join(f"№{x}" for x in ([job.id] + extra_job_ids))

    period = ""
    if request.parser_year_min is not None:
        if request.parser_year_max is not None and request.parser_year_max != request.parser_year_min:
            period = f" (только документы за {request.parser_year_min}–{request.parser_year_max} г.)"
        else:
            period = f" (только документы за {request.parser_year_min} г.)"
    if not job_new:
        if run_mode == "download":
            return (
                f"Такая фоновая загрузка уже в работе или в очереди (процесс №{job.id}){period} по запросу «{request.query_value}». "
                "Дубликат не создавался. Спросите «как там скачивание» или «отмени все задачи КАД», если нужно снять очередь."
                f"{folder_hint}"
            )
        return (
            f"Такой поиск в КАД уже выполняется или стоит в очереди (процесс №{job.id}) по запросу «{request.query_value}». "
            "Дубликат не создавался."
            f"{folder_hint}"
        )
    if run_mode == "download":
        return (
            f"Запустил фоновую загрузку материалов из картотеки ({job_ids_label})"
            f'{period} по запросу «{request.query_value}». '
            "Обычно это занимает от нескольких минут. Спросите позже «как там скачивание» или «статус загрузки» — кратко опишу, что сделано."
            f"{folder_hint}"
        )
    return (
        f"Запустил фоновый поиск в КАД ({job_ids_label}) по запросу «{request.query_value}». "
        "Когда появятся результаты, можно спросить статус или попросить «отчёт по задаче» с номером."
        f"{folder_hint}"
    )


async def save_message_to_case_event(db: Session, text: str, cases: list[Case]) -> tuple[str, Case | None]:
    """Сохраняет текст сообщения как заметку по делу (CaseEvent assistant_message)."""
    hint = parse_save_message_case_hint(text)
    if not hint:
        return (
            "Укажите папку или дело в кавычках, например: Сохрани это сообщение в папке «Название»",
            None,
        )
    case = find_case_by_hint(cases, hint, db=db)
    if not case:
        case, _ = ensure_chat_case(db, hint)
    body = extract_saved_message_body_for_case(text)
    if not body.strip():
        body = text
    db.add(CaseEvent(case_id=case.id, event_type="assistant_message", body=body[:40000]))
    if (
        settings.case_note_digest_enabled
        and case.case_number != "UNSORTED"
        and len(body) >= settings.case_note_digest_min_chars
        and settings.openai_api_key.strip()
    ):
        try:
            digest = await llm_digest_incoming_case_note(body, case.title)
            if digest:
                db.add(CaseEvent(case_id=case.id, event_type="case_note_digest", body=digest[:4000]))
        except Exception:
            pass
    db.commit()
    reply = (
        f"Сохранил текст в деле «{case.title}» ({case.case_number}). "
        f"Символов: {len(body)}."
    )
    return reply, case


@app.post("/assistant/active-case")
def set_assistant_active_case(
    payload: AssistantActiveCaseIn,
    db: Session = Depends(get_db),
    _: str = Depends(require_user),
) -> dict:
    """Синхронизация выбранной в веб-панели папки с беседой (active_case)."""
    case = db.query(Case).filter(Case.id == payload.case_id).first()
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")
    conversation = get_or_create_conversation(db, conversation_user_key(_))
    conversation.active_case_id = case.id
    db.add(conversation)
    db.commit()
    return {"case_id": case.id, "case_number": case.case_number, "title": case.title}


@app.post("/assistant/ingest-text", response_model=AssistantIngestOut)
async def assistant_ingest_text(
    payload: AssistantIngestIn,
    db: Session = Depends(get_db),
    _: str = Depends(require_user),
) -> AssistantIngestOut:
    text = payload.text.strip()
    if not text:
        raise HTTPException(status_code=400, detail="Empty text")

    conversation = get_or_create_conversation(db, conversation_user_key(_))
    add_conversation_message(
        db,
        conversation=conversation,
        role="user",
        content=text,
        case=conversation.active_case,
    )
    db.commit()

    async def finalize_reply(
        *,
        case: Case,
        reply_text: str,
        mode: str,
        created_case: bool = False,
        created_tasks: int = 0,
        next_hearing_date=None,
        refresh_summary: bool = False,
    ) -> AssistantIngestOut:
        conversation.active_case_id = case.id
        db.add(conversation)
        db.add(CaseEvent(case_id=case.id, event_type="assistant_reply", body=reply_text))
        add_conversation_message(
            db,
            conversation=conversation,
            role="assistant",
            content=reply_text,
            case=case,
        )
        db.commit()
        if refresh_summary:
            await refresh_conversation_summary(db, conversation)
        return AssistantIngestOut(
            case_id=case.id,
            case_number=case.case_number,
            created_case=created_case,
            mode=mode,
            created_tasks=created_tasks,
            next_hearing_date=next_hearing_date if next_hearing_date is not None else case.next_hearing_date,
            reply=reply_text,
        )

    cases = db.query(Case).all()
    tag_update = parse_case_tag_update(text)
    if not tag_update and looks_like_case_tag_update(text):
        try:
            tag_update = await llm_parse_case_tag_update(text, cases)
        except Exception:
            tag_update = None
    if tag_update:
        case = find_case_by_hint(cases, tag_update["case_hint"], db=db)
        created_case = False
        if not case:
            case = Case(
                title=tag_update["title_candidate"][:255],
                court_name="неизвестно",
                case_number=f"TAG-{uuid4().hex[:8].upper()}",
                status="analysis",
                stage="analysis",
            )
            db.add(case)
            db.commit()
            db.refresh(case)
            created_case = True

        existing = {
            (tag.kind, tag.value.strip().lower()): tag
            for tag in db.query(CaseTag).filter(CaseTag.case_id == case.id).all()
        }
        added: list[str] = []
        alias_values = tag_update.get("aliases") or []
        tag_values = tag_update.get("tags") or []
        for value in alias_values:
            key = ("alias", value.strip().lower())
            if key not in existing:
                db.add(CaseTag(case_id=case.id, value=value[:255], kind="alias"))
                added.append(f'алиас "{value}"')
        for value in tag_values:
            key = ("keyword", value.strip().lower())
            if key not in existing:
                db.add(CaseTag(case_id=case.id, value=value[:255], kind="keyword"))
                added.append(f'тег "{value}"')
        db.add(
            CaseEvent(
                case_id=case.id,
                event_type="case_tags_updated",
                body=f"Сохранены теги из чата: {', '.join(tag_values[:20])}",
            )
        )
        db.commit()
        all_tags = [
            t.value
            for t in db.query(CaseTag).filter(CaseTag.case_id == case.id).order_by(CaseTag.kind, CaseTag.value).all()
        ]
        reply_text = (
            f'Сохранил привязку для дела "{case.title}". '
            f'Добавлено: {", ".join(added) if added else "новых тегов не было"}. '
            f'Всего тегов/алиасов у дела: {len(all_tags)}.'
        )
        return await finalize_reply(
            case=case,
            reply_text=reply_text,
            mode="case-tags",
            created_case=created_case,
            refresh_summary=True,
        )

    if looks_like_cross_folder_matter_narrative_request(text):
        from .matter_narrative import build_cross_folder_matter_narrative

        reply_text = await build_cross_folder_matter_narrative(db, text)
        return await finalize_reply(
            case=get_or_create_unsorted_case(db),
            reply_text=reply_text,
            mode="cross-folder-matter-narrative",
            refresh_summary=True,
        )

    if looks_like_cross_folder_duplicate_cleanup_request(text):
        reply_text, dup_case = handle_cross_folder_duplicate_cleanup_chat(db, text)
        return await finalize_reply(
            case=dup_case if dup_case is not None else get_or_create_unsorted_case(db),
            reply_text=reply_text,
            mode="documents-duplicates-cleanup",
            refresh_summary=True,
        )

    if settings.chat_tools_router_enabled and settings.openai_api_key.strip():
        try:
            from .chat_tools import run_chat_tools_router

            routed = await run_chat_tools_router(
                db,
                conversation,
                text,
                user_role=_,
                preferred_case_number=payload.preferred_case_number,
            )
            if routed is not None:
                reply_text, routed_case, mode = routed
                return await finalize_reply(case=routed_case, reply_text=reply_text, mode=mode)
        except Exception:
            pass

    if looks_like_save_message_to_case_request(text):
        reply_text, target_case = await save_message_to_case_event(db, text, cases)
        case_for_reply = target_case if target_case is not None else get_or_create_unsorted_case(db)
        return await finalize_reply(
            case=case_for_reply,
            reply_text=reply_text,
            mode="message-saved-to-case",
            refresh_summary=True,
        )

    if looks_like_rename_case_request(text):
        reply_text, target_case = handle_rename_case_chat(db, text)
        case_for_reply = target_case if target_case is not None else get_or_create_unsorted_case(db)
        return await finalize_reply(
            case=case_for_reply,
            reply_text=reply_text,
            mode="case-rename",
            refresh_summary=target_case is not None,
        )

    if looks_like_merge_cases_request(text):
        reply_text, target_case = handle_merge_cases_chat(db, text)
        case_for_reply = target_case if target_case is not None else get_or_create_unsorted_case(db)
        return await finalize_reply(
            case=case_for_reply,
            reply_text=reply_text,
            mode="cases-merge",
            refresh_summary=target_case is not None,
        )

    if looks_like_merge_duplicate_folders_request(text):
        reply_text, dup_merge_case = handle_merge_cases_linked_by_duplicate_filenames(db)
        case_for_reply = dup_merge_case if dup_merge_case is not None else get_or_create_unsorted_case(db)
        return await finalize_reply(
            case=case_for_reply,
            reply_text=reply_text,
            mode="cases-merge-duplicates",
            refresh_summary=dup_merge_case is not None,
        )

    if looks_like_semantic_workspace_clusters_request(text):
        from .matter_intelligence import preview_semantic_workspace_clusters

        reply_text, _semantic_case = await preview_semantic_workspace_clusters(
            db, conversation_user_key(_)
        )
        return await finalize_reply(
            case=get_or_create_unsorted_case(db),
            reply_text=reply_text,
            mode="semantic-workspace-preview",
        )

    if looks_like_delete_all_empty_folders(text):
        reply_text, empty_del_case = handle_delete_all_empty_case_folders_chat(db, conversation)
        case_for_reply = empty_del_case if empty_del_case is not None else get_or_create_unsorted_case(db)
        return await finalize_reply(
            case=case_for_reply,
            reply_text=reply_text,
            mode="case-empty-folders-delete",
            refresh_summary=True,
        )

    del_folder_hint = await resolve_delete_folder_hint(
        text,
        cases,
        active_case=conversation.active_case,
    )
    if del_folder_hint:
        reply_text, del_folder_case = handle_delete_case_folder_chat(
            db, text, hint_override=del_folder_hint
        )
        case_for_reply = del_folder_case if del_folder_case is not None else get_or_create_unsorted_case(db)
        return await finalize_reply(
            case=case_for_reply,
            reply_text=reply_text,
            mode="case-folder-delete",
            refresh_summary=True,
        )

    del_out = handle_delete_documents_chat(db, text, conversation)
    if del_out:
        del_reply, del_case = del_out
        case_for_reply = del_case or conversation.active_case or get_or_create_unsorted_case(db)
        return await finalize_reply(
            case=case_for_reply,
            reply_text=del_reply,
            mode="documents-delete",
        )

    upload_loc = answer_where_recent_upload_saved(db, text, conversation)
    if upload_loc:
        reply_ul, case_ul = upload_loc
        return await finalize_reply(
            case=case_ul,
            reply_text=reply_ul,
            mode="upload-location",
        )

    rp_participant = handle_remember_participant_chat(db, text)
    if rp_participant is not None:
        unsorted_case = get_or_create_unsorted_case(db)
        return await finalize_reply(
            case=unsorted_case,
            reply_text=rp_participant,
            mode="participant-link",
        )

    if looks_like_court_search_command(text):
        _ac = conversation.active_case
        reply_text = handle_court_sync_chat_command(
            db,
            text,
            _,
            active_case_id=_ac.id if _ac else None,
            active_case_title=_ac.title if _ac else None,
            active_case_number=_ac.case_number if _ac else None,
        )
        if reply_text:
            active_case = conversation.active_case or get_or_create_unsorted_case(db)
            return await finalize_reply(case=active_case, reply_text=reply_text, mode="court-sync-command")
        active_case = conversation.active_case or get_or_create_unsorted_case(db)
        return await finalize_reply(
            case=active_case,
            reply_text=(
                "Запрос похож на обращение к картотеке (КАД), но не удалось извлечь номер дела, ссылку на карточку "
                "kad.arbitr.ru, ИНН/ОГРН или название для поиска. Напишите, например: «Скачай из КАД все материалы "
                "дела А40-12345/2025» или вставьте полную ссылку на карточку дела. Фоновая загрузка идёт через Parser API."
            ),
            mode="court-sync-command",
        )

    if looks_like_show_documents_in_folder_only(text):
        _lc, command_case = resolve_case_for_conversation(
            db,
            text,
            user_role=_,
            preferred_case_number=payload.preferred_case_number,
        )
        command_docs = (
            db.query(Document)
            .filter(Document.case_id == command_case.id)
            .order_by(Document.created_at.desc())
            .all()
        )
        reply_text = render_document_list(command_case, command_docs)
        return await finalize_reply(case=command_case, reply_text=reply_text, mode="documents-list")

    if looks_like_group_by_cases_request(text):
        reply_text = render_documents_grouped_by_cases(db)
        unsorted_case = get_or_create_unsorted_case(db)
        return await finalize_reply(case=unsorted_case, reply_text=reply_text, mode="documents-grouped-by-case")

    if looks_like_single_doc_summary_request(text):
        ids = [int(x) for x in re.findall(r"\b(\d+)\b", text)]
        if not ids:
            reply_text = "Не вижу номер документа. Напишите, например: дай мне суть документа 72"
        else:
            doc, summary_text = await build_document_summary_by_id(db, ids[0])
            reply_text = (
                summary_text
                if doc is None
                else f'Суть документа [{doc.id}] "{doc.filename}":\n{summary_text}'
            )
        unsorted_case = get_or_create_unsorted_case(db)
        return await finalize_reply(case=unsorted_case, reply_text=reply_text, mode="document-summary-by-id")

    if looks_like_unsorted_tag_suggestion_request(text):
        unsorted_case = get_or_create_unsorted_case(db)
        reply_text = await suggest_tags_for_unsorted_case(db)
        return await finalize_reply(case=unsorted_case, reply_text=reply_text, mode="unsorted-tag-suggestions")

    if looks_like_reclassify_unsorted_request(text):
        unsorted_case = get_or_create_unsorted_case(db)
        reply_text = reclassify_unsorted_documents(db)
        return await finalize_reply(case=unsorted_case, reply_text=reply_text, mode="unsorted-reclassified")

    if looks_like_followup_current_archive_confirmation(text):
        title = get_recent_folder_request_context(db)
        target_case: Case | None = None
        if not title:
            reply_text = (
                "Не вижу, для какой папки продолжать. Напишите еще раз: "
                'Создай папку "Название дела" и собери туда весь текущий архив'
            )
        else:
            reply_text, target_case = preview_collect_recent_archive_to_case(db, title)
        case_for_reply = target_case if target_case is not None else get_or_create_unsorted_case(db)
        return await finalize_reply(
            case=case_for_reply,
            reply_text=reply_text,
            mode="documents-bulk-move-recent-archive-followup",
        )

    if looks_like_bulk_folder_from_current_archive_request(text):
        title = parse_case_title_from_folder_request(text)
        target_case = None
        if not title:
            reply_text = (
                'Не вижу название папки/дела. Напишите, например: Создай папку "Банкротство Эй Джи Мануфактуринг" '
                "и собери туда весь текущий архив"
            )
        else:
            save_folder_request_context(db, title)
            reply_text, target_case = preview_collect_recent_archive_to_case(db, title)
        case_for_reply = target_case if target_case is not None else get_or_create_unsorted_case(db)
        return await finalize_reply(case=case_for_reply, reply_text=reply_text, mode="documents-bulk-move-recent-archive")

    if looks_like_move_all_from_active_case_to_folder(text):
        title = parse_collect_folder_title(text)
        if not title:
            title = parse_case_title_from_folder_request(text)
        save_folder_request_context(db, title or "")
        src_explicit = resolve_move_source_case_from_text(db, text)
        if src_explicit and title:
            reply_text, target_case = execute_move_all_documents_to_case_folder(db, src_explicit, title)
            case_for_reply = target_case if target_case is not None else get_or_create_unsorted_case(db)
            return await finalize_reply(case=case_for_reply, reply_text=reply_text, mode="documents-bulk-move-direct")
        reply_text, target_case = preview_move_all_documents_from_active_case_to_folder(db, conversation, title)
        case_for_reply = target_case if target_case is not None else get_or_create_unsorted_case(db)
        return await finalize_reply(case=case_for_reply, reply_text=reply_text, mode="documents-bulk-move-active-case")

    if looks_like_bulk_folder_by_keywords_request(text):
        parsed = parse_bulk_folder_request(text)
        target_case = None
        if not parsed:
            reply_text = (
                'Не смог понять команду. Пример: Создай папку "Сделка Grimme". '
                'Перенеси туда все документы, которые содержат: "Grimme Landmaschinenfabrik GmbH & Co.", '
                '"Ex officio", "ООО Эй Джи Мануфактуринг"'
            )
        else:
            title, keywords = parsed
            save_folder_request_context(db, title)
            docs_scope = get_recent_document_batch(db) if looks_like_current_archive_reference(text) else None
            scope_label = "в последнем архиве" if docs_scope is not None else None
            reply_text, target_case = preview_bulk_move_documents_to_case_by_keywords(
                db,
                title,
                keywords,
                docs_scope=docs_scope,
                scope_label=scope_label,
            )
        case_for_reply = target_case if target_case is not None else get_or_create_unsorted_case(db)
        return await finalize_reply(case=case_for_reply, reply_text=reply_text, mode="documents-bulk-move-by-keywords")

    if looks_like_semantic_plan_cancel(text):
        from .matter_intelligence import cancel_pending_semantic_plan

        reply_text, _ok = cancel_pending_semantic_plan(db, conversation_user_key(_))
        return await finalize_reply(
            case=get_or_create_unsorted_case(db),
            reply_text=reply_text,
            mode="semantic-plan-cancel",
        )

    if looks_like_semantic_plan_confirm(text):
        from .matter_intelligence import apply_pending_semantic_plan

        reply_text, semantic_target = apply_pending_semantic_plan(db, conversation_user_key(_))
        case_for_reply = semantic_target if semantic_target is not None else get_or_create_unsorted_case(db)
        return await finalize_reply(
            case=case_for_reply,
            reply_text=reply_text,
            mode="semantic-plan-applied",
            refresh_summary=semantic_target is not None,
        )

    if looks_like_pending_move_confirmation(text) or looks_like_pending_move_rejection(text):
        reply_text, target_case = apply_pending_move_plan(db, text)
        case_for_reply = target_case if target_case is not None else get_or_create_unsorted_case(db)
        return await finalize_reply(case=case_for_reply, reply_text=reply_text, mode="documents-bulk-move-confirmed")

    if looks_like_manual_move_request(text):
        reply_text = move_documents_by_chat_command(db, text)
        unsorted_case = get_or_create_unsorted_case(db)
        return await finalize_reply(case=unsorted_case, reply_text=reply_text, mode="documents-manual-move")

    _command_conversation, command_case = resolve_case_for_conversation(
        db,
        text,
        user_role=_,
        preferred_case_number=payload.preferred_case_number,
    )
    command_docs = (
        db.query(Document)
        .filter(Document.case_id == command_case.id)
        .order_by(Document.created_at.desc())
        .all()
    )
    if looks_like_documents_list_request(text):
        reply_text = render_document_list(command_case, command_docs)
        return await finalize_reply(case=command_case, reply_text=reply_text, mode="documents-list")

    if looks_like_chronology_request(text):
        reply_text = await summarize_documents_for_case(command_case, command_docs, chronology=True)
        return await finalize_reply(case=command_case, reply_text=reply_text, mode="documents-chronology")

    if looks_like_documents_analyze_request(text):
        reply_text = await summarize_documents_for_case(command_case, command_docs, chronology=False)
        return await finalize_reply(case=command_case, reply_text=reply_text, mode="documents-analyze")

    if looks_like_global_documents_search(text):
        reply_text = search_documents_global(db, text, limit=45)
        unsorted_case = get_or_create_unsorted_case(db)
        return await finalize_reply(
            case=unsorted_case,
            reply_text=reply_text,
            mode="documents-search-global",
        )

    if looks_like_documents_search_request(text):
        query = extract_search_query(text)
        if query:
            reply_text = search_documents(command_case, command_docs, query)
            return await finalize_reply(case=command_case, reply_text=reply_text, mode="documents-search")

    if looks_like_materials_draft_request(text):
        reply_text = await handle_materials_draft_request(db, command_case, command_docs, text)
        return await finalize_reply(
            case=command_case,
            reply_text=reply_text,
            mode="materials-draft",
            refresh_summary=True,
        )

    if looks_like_cross_case_duplicate_scan_request(text):
        reply_text = format_duplicate_documents_across_cases_report(db)
        unsorted_case = get_or_create_unsorted_case(db)
        return await finalize_reply(
            case=unsorted_case,
            reply_text=reply_text,
            mode="documents-duplicates-across-folders",
        )

    if looks_like_compare_documents_request(text):
        reply_text = await handle_compare_documents_request(db, command_case, command_docs, text)
        return await finalize_reply(
            case=command_case,
            reply_text=reply_text,
            mode="materials-compare",
            refresh_summary=True,
        )

    if looks_like_extract_deadlines_request(text):
        reply_text = await handle_extract_deadlines_request(db, command_case, text)
        return await finalize_reply(
            case=command_case,
            reply_text=reply_text,
            mode="materials-deadlines",
            refresh_summary=True,
        )

    extracted_case_number = payload.preferred_case_number or extract_case_number(text)
    created_case = False
    if extracted_case_number:
        normalized_case_number = extracted_case_number.replace(" ", "").replace("\n", "")
        case = db.query(Case).filter(Case.case_number == normalized_case_number).first()
        if not case:
            if not payload.allow_case_create:
                raise HTTPException(status_code=404, detail="Дело с таким номером не найдено.")
            case = Case(
                title=f"Дело {normalized_case_number}",
                court_name="неизвестно",
                case_number=normalized_case_number,
                status="analysis",
                stage="analysis",
            )
            db.add(case)
            db.commit()
            db.refresh(case)
            created_case = True
    else:
        case = conversation.active_case or get_or_create_unsorted_case(db)

    created_tasks = 0
    next_hearing_date = None

    if looks_like_hearing_note(text):
        _, tasks, next_hearing_date = parse_hearing_note(db, case, text)
        created_tasks = len(tasks)
        reply_parts = [
            f"Записал заметки по заседанию. Создано задач: {created_tasks}.",
        ]
        if next_hearing_date:
            reply_parts.append(f"Дата следующего заседания (если из текста): {next_hearing_date}.")
        reply_hearing = " ".join(reply_parts)
        if settings.openai_api_key.strip():
            try:
                reply_hearing = await llm_assistant_chat_reply(
                    f"[Режим: протокол заседания]\n{text}", case
                )
            except Exception:
                reply_hearing = " ".join(reply_parts)
        return await finalize_reply(
            case=case,
            reply_text=reply_hearing,
            mode="hearing-parser",
            created_case=created_case,
            created_tasks=created_tasks,
            next_hearing_date=next_hearing_date,
            refresh_summary=True,
        )

    db.add(CaseEvent(case_id=case.id, event_type="assistant_message", body=text))
    if (
        settings.case_note_digest_enabled
        and case.case_number != "UNSORTED"
        and len(text) >= settings.case_note_digest_min_chars
        and settings.openai_api_key.strip()
    ):
        try:
            digest = await llm_digest_incoming_case_note(text, case.title)
            if digest:
                db.add(CaseEvent(case_id=case.id, event_type="case_note_digest", body=digest[:4000]))
        except Exception:
            pass
    db.commit()
    mode = "message" if case.case_number != "UNSORTED" else "message-unsorted"
    try:
        prompt, source_docs, citations = build_grounded_prompt(
            db,
            conversation=conversation,
            user_message=text,
            case=case,
        )
        reply_text = await llm_assistant_chat_reply(text, case, prompt_override=prompt)
        if citations:
            reply_text = reply_text.rstrip() + "\n\nИсточники:\n- " + "\n- ".join(dict.fromkeys(citations))
        elif source_docs:
            fallback_sources = [f"[doc:{doc.id}] {doc.filename}" for doc in source_docs[:5]]
            reply_text = reply_text.rstrip() + "\n\nСвязанные документы:\n- " + "\n- ".join(fallback_sources)
    except Exception as exc:
        reply_text = f"Сообщение сохранено, но ответ ИИ не получен: {exc}"
    return await finalize_reply(
        case=case,
        reply_text=reply_text,
        mode=mode,
        created_case=created_case,
        refresh_summary=True,
    )
