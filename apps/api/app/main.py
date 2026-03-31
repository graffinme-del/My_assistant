from datetime import datetime, time
import re
import shutil
from pathlib import Path
from uuid import uuid4
import tempfile
import zipfile

from fastapi import Depends, FastAPI, File, Form, Header, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from sqlalchemy import or_
from sqlalchemy.orm import Session

from .ai_service import (
    build_case_summary,
    classify_document,
    extract_document_text,
    llm_assistant_chat_reply,
    llm_parse_case_tag_update,
    llm_document_routing,
    llm_summary,
    match_case,
    extract_case_number,
    find_case_by_hint,
    looks_like_hearing_note,
    looks_like_case_tag_update,
    parse_case_tag_update,
    parse_hearing_note,
)
from .config import settings
from .db import Base, engine, get_db
from .models import Case, CaseEvent, CaseTag, Document, Reminder, Task
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
    AssistantIngestIn,
    AssistantIngestOut,
    SummaryOut,
    TaskCreate,
    TaskOut,
    BulkIngestOut,
    AssistantSummaryIn,
    AssistantSummaryOut,
)

Base.metadata.create_all(bind=engine)

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


def resolve_case_for_chat(
    db: Session,
    text: str,
    *,
    preferred_case_number: str | None = None,
) -> Case:
    cases = db.query(Case).all()
    if preferred_case_number:
        normalized_case_number = preferred_case_number.replace(" ", "").replace("\n", "")
        case = db.query(Case).filter(Case.case_number == normalized_case_number).first()
        if case:
            return case

    extracted_case_number = extract_case_number(text)
    if extracted_case_number:
        normalized_case_number = extracted_case_number.replace(" ", "").replace("\n", "")
        case = db.query(Case).filter(Case.case_number == normalized_case_number).first()
        if case:
            return case

    hinted = find_case_by_hint(cases, text)
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


def local_storage_path(doc: Document) -> Path | None:
    if not doc.s3_key.startswith("local://"):
        return None
    rel = doc.s3_key.replace("local://", "", 1)
    path = STORAGE_ROOT / rel
    return path if path.exists() else None


def looks_like_documents_list_request(text: str) -> bool:
    t = text.lower()
    return any(noun in t for noun in ["документ", "файл", "архив"]) and any(
        k in t for k in ["покажи", "список", "какие", "дай"]
    )


def looks_like_documents_analyze_request(text: str) -> bool:
    t = text.lower()
    return any(noun in t for noun in ["документ", "файл", "архив"]) and any(
        k in t for k in ["разбери", "проанализ", "разлож", "сгруппир"]
    )


def looks_like_group_by_cases_request(text: str) -> bool:
    t = text.lower()
    return any(k in t for k in ["разлож", "разложи", "сгруппируй", "раскидай"]) and any(
        k in t for k in ["по делам", "по папкам", "по дел", "по папк"]
    )


def looks_like_unsorted_tag_suggestion_request(text: str) -> bool:
    t = text.lower()
    return any(k in t for k in ["предлож", "подскажи", "придумай", "выдели"]) and any(
        k in t for k in ["теги", "алиасы", "ключевые слова", "неразобран", "unsorted"]
    )


def looks_like_chronology_request(text: str) -> bool:
    t = text.lower()
    return any(k in t for k in ["хронолог", "таймлайн", "по датам", "по времени"])


def extract_search_query(text: str) -> str:
    lowered = text.lower()
    for marker in ["найди", "поиск", "ищи", "покажи документы с", "документы с"]:
        idx = lowered.find(marker)
        if idx >= 0:
            return text[idx + len(marker) :].strip(" :.-")
    return ""


def looks_like_documents_search_request(text: str) -> bool:
    t = text.lower()
    return any(k in t for k in ["найди", "поиск", "ищи"]) and any(
        k in t for k in ["док", "файл", "асв", "банк", "определен", "договор", "жалоб", "акт"]
    )


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
                "В контейнере API нет ключа. На сервере в каталоге с runtime.compose.yml "
                "в файле .env добавьте строку OPENAI_API_KEY=sk-… (без кавычек), "
                "при необходимости OPENAI_BASE_URL и OPENAI_MODEL, затем: "
                "docker compose -f runtime.compose.yml up -d --force-recreate api"
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
    return db.query(Case).order_by(Case.created_at.desc()).all()


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


@app.get("/documents/{document_id}/download")
def download_document(
    document_id: int, db: Session = Depends(get_db), _: str = Depends(require_user)
) -> FileResponse:
    doc = db.query(Document).filter(Document.id == document_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    path = local_storage_path(doc)
    if not path:
        raise HTTPException(status_code=404, detail="Document file not found on disk")
    return FileResponse(path=str(path), filename=doc.filename, media_type="application/octet-stream")


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

    all_cases = db.query(Case).all()
    llm_route = await llm_document_routing(
        filename=safe_name,
        text=extracted_text,
        available_case_numbers=[c.case_number for c in all_cases],
    )

    matched_case = None
    case_confidence = 0.0
    llm_note = ""
    if llm_route:
        llm_case_number = str(llm_route.get("case_number", "")).strip()
        llm_category = str(llm_route.get("category", "")).strip()
        llm_confidence = float(llm_route.get("confidence", 0.0) or 0.0)
        llm_note = str(llm_route.get("short_note", "")).strip()
        if llm_category:
            category = llm_category
        if llm_case_number:
            matched_case = db.query(Case).filter(Case.case_number == llm_case_number).first()
        if matched_case:
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
            normalized_auto = auto_case_number.replace(" ", "").replace("\n", "")
            case = db.query(Case).filter(Case.case_number == normalized_auto).first()
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

    return DocumentIngestOut(
        document=doc,
        matched_case_id=matched_case.id,
        matched_case_number=matched_case.case_number,
        category=category,
        confidence=round((class_confidence + case_confidence) / 2, 2),
        routing_mode="LLM" if used_llm else "fallback-правила",
        routing_model=settings.openai_model if used_llm else "эвристики",
        note="Документ автоматически обработан и прикреплен к делу.",
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
        normalized = preferred_case_number.replace(" ", "").replace("\n", "")
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
                "doc",
                "docx",
                "rtf",
                "jpg",
                "jpeg",
                "png",
                "webp",
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

                matched_case, case_confidence = match_case(
                    db,
                    filename=original_name,
                    text=extracted_text,
                    preferred_case_id=preferred_case_id,
                )
                if not matched_case:
                    auto_case_number = extract_case_number(extracted_text) or extract_case_number(original_name)
                    if auto_case_number:
                        normalized_auto = auto_case_number.replace(" ", "").replace("\n", "")
                        case = db.query(Case).filter(Case.case_number == normalized_auto).first()
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
        return f'По делу "{case.title}" пока нет загруженных документов.'
    lines = [f'Документы по делу "{case.title}" ({len(docs)} шт.):']
    for doc in docs[:20]:
        lines.append(
            f'- [{doc.id}] {doc.filename} | {doc.category} | скачать: /api/documents/{doc.id}/download'
        )
    if len(docs) > 20:
        lines.append(f"... и еще {len(docs) - 20}. Уточните запрос, если нужен отбор.")
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


@app.post("/assistant/ingest-text", response_model=AssistantIngestOut)
async def assistant_ingest_text(
    payload: AssistantIngestIn,
    db: Session = Depends(get_db),
    _: str = Depends(require_user),
) -> AssistantIngestOut:
    text = payload.text.strip()
    if not text:
        raise HTTPException(status_code=400, detail="Empty text")

    cases = db.query(Case).all()
    tag_update = parse_case_tag_update(text)
    if not tag_update and looks_like_case_tag_update(text):
        try:
            tag_update = await llm_parse_case_tag_update(text, cases)
        except Exception:
            tag_update = None
    if tag_update:
        case = find_case_by_hint(cases, tag_update["case_hint"])
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
        db.add(CaseEvent(case_id=case.id, event_type="assistant_reply", body=reply_text))
        db.commit()
        return AssistantIngestOut(
            case_id=case.id,
            case_number=case.case_number,
            created_case=created_case,
            mode="case-tags",
            created_tasks=0,
            next_hearing_date=case.next_hearing_date,
            reply=reply_text,
        )

    if looks_like_group_by_cases_request(text):
        reply_text = render_documents_grouped_by_cases(db)
        unsorted_case = get_or_create_unsorted_case(db)
        db.add(CaseEvent(case_id=unsorted_case.id, event_type="assistant_reply", body=reply_text))
        db.commit()
        return AssistantIngestOut(
            case_id=unsorted_case.id,
            case_number=unsorted_case.case_number,
            created_case=False,
            mode="documents-grouped-by-case",
            created_tasks=0,
            next_hearing_date=unsorted_case.next_hearing_date,
            reply=reply_text,
        )

    if looks_like_unsorted_tag_suggestion_request(text):
        unsorted_case = get_or_create_unsorted_case(db)
        reply_text = await suggest_tags_for_unsorted_case(db)
        db.add(CaseEvent(case_id=unsorted_case.id, event_type="assistant_reply", body=reply_text))
        db.commit()
        return AssistantIngestOut(
            case_id=unsorted_case.id,
            case_number=unsorted_case.case_number,
            created_case=False,
            mode="unsorted-tag-suggestions",
            created_tasks=0,
            next_hearing_date=unsorted_case.next_hearing_date,
            reply=reply_text,
        )

    command_case = resolve_case_for_chat(db, text, preferred_case_number=payload.preferred_case_number)
    command_docs = (
        db.query(Document)
        .filter(Document.case_id == command_case.id)
        .order_by(Document.created_at.desc())
        .all()
    )
    if looks_like_documents_list_request(text):
        reply_text = render_document_list(command_case, command_docs)
        db.add(CaseEvent(case_id=command_case.id, event_type="assistant_reply", body=reply_text))
        db.commit()
        return AssistantIngestOut(
            case_id=command_case.id,
            case_number=command_case.case_number,
            created_case=False,
            mode="documents-list",
            created_tasks=0,
            next_hearing_date=command_case.next_hearing_date,
            reply=reply_text,
        )

    if looks_like_chronology_request(text):
        reply_text = await summarize_documents_for_case(command_case, command_docs, chronology=True)
        db.add(CaseEvent(case_id=command_case.id, event_type="assistant_reply", body=reply_text))
        db.commit()
        return AssistantIngestOut(
            case_id=command_case.id,
            case_number=command_case.case_number,
            created_case=False,
            mode="documents-chronology",
            created_tasks=0,
            next_hearing_date=command_case.next_hearing_date,
            reply=reply_text,
        )

    if looks_like_documents_analyze_request(text):
        reply_text = await summarize_documents_for_case(command_case, command_docs, chronology=False)
        db.add(CaseEvent(case_id=command_case.id, event_type="assistant_reply", body=reply_text))
        db.commit()
        return AssistantIngestOut(
            case_id=command_case.id,
            case_number=command_case.case_number,
            created_case=False,
            mode="documents-analyze",
            created_tasks=0,
            next_hearing_date=command_case.next_hearing_date,
            reply=reply_text,
        )

    if looks_like_documents_search_request(text):
        query = extract_search_query(text)
        if query:
            reply_text = search_documents(command_case, command_docs, query)
            db.add(CaseEvent(case_id=command_case.id, event_type="assistant_reply", body=reply_text))
            db.commit()
            return AssistantIngestOut(
                case_id=command_case.id,
                case_number=command_case.case_number,
                created_case=False,
                mode="documents-search",
                created_tasks=0,
                next_hearing_date=command_case.next_hearing_date,
                reply=reply_text,
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
        case = get_or_create_unsorted_case(db)

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
        db.add(CaseEvent(case_id=case.id, event_type="assistant_reply", body=reply_hearing))
        db.commit()
        return AssistantIngestOut(
            case_id=case.id,
            case_number=case.case_number,
            created_case=created_case,
            mode="hearing-parser",
            created_tasks=created_tasks,
            next_hearing_date=next_hearing_date,
            reply=reply_hearing,
        )

    db.add(CaseEvent(case_id=case.id, event_type="assistant_message", body=text))
    db.commit()
    mode = "message" if case.case_number != "UNSORTED" else "message-unsorted"
    try:
        reply_text = await llm_assistant_chat_reply(text, case)
    except Exception as exc:
        reply_text = f"Сообщение сохранено, но ответ ИИ не получен: {exc}"
    db.add(CaseEvent(case_id=case.id, event_type="assistant_reply", body=reply_text))
    db.commit()
    return AssistantIngestOut(
        case_id=case.id,
        case_number=case.case_number,
        created_case=created_case,
        mode=mode,
        created_tasks=0,
        next_hearing_date=case.next_hearing_date,
        reply=reply_text,
    )
