from datetime import datetime, time
import shutil
from pathlib import Path
from uuid import uuid4
import tempfile
import zipfile

from fastapi import Depends, FastAPI, File, Form, Header, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import or_
from sqlalchemy.orm import Session

from .ai_service import (
    build_case_summary,
    classify_document,
    extract_document_text,
    llm_summary,
    llm_assistant_chat_reply,
    llm_document_routing,
    match_case,
    parse_hearing_note,
    extract_case_number,
    looks_like_hearing_note,
)
from .config import settings
from .db import Base, engine, get_db
from .models import Case, CaseEvent, Document, Reminder, Task
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
    max_files: int = Form(default=25),
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

    try:
        with zipfile.ZipFile(dst) as zf, tempfile.TemporaryDirectory() as td:
            members = [m for m in zf.infolist() if not m.is_dir()]
            total_files = len(members)
            if total_files == 0:
                return BulkIngestOut(
                    total_files=0, ingested_files=0, skipped_files=0, errors=["Архив пуст."]
                )

            for idx, m in enumerate(members):
                if idx >= max_files:
                    break
                ext = (m.filename.rsplit(".", 1)[-1] if "." in m.filename else "").lower()
                if ext not in {"pdf", "txt", "md"}:
                    # We still store metadata, but extracted text will be empty.
                    skipped_files += 1
                    continue

                # Extract one file
                extracted_path = Path(td) / Path(m.filename).name
                with zf.open(m) as src, extracted_path.open("wb") as f_out:
                    shutil.copyfileobj(src, f_out)

                original_name = Path(m.filename).name
                extracted_text = extract_document_text(extracted_path, original_name)
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
        errors.append(str(e))

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


@app.post("/assistant/ingest-text", response_model=AssistantIngestOut)
async def assistant_ingest_text(
    payload: AssistantIngestIn,
    db: Session = Depends(get_db),
    _: str = Depends(require_user),
) -> AssistantIngestOut:
    text = payload.text.strip()
    if not text:
        raise HTTPException(status_code=400, detail="Empty text")

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
