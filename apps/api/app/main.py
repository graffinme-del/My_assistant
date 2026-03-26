from datetime import datetime, time

from fastapi import Depends, FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import or_
from sqlalchemy.orm import Session

from .ai_service import build_case_summary, llm_summary, parse_hearing_note
from .config import settings
from .db import Base, engine, get_db
from .models import Case, CaseEvent, Document, Reminder, Task
from .schemas import (
    CaseCreate,
    CaseOut,
    DocumentCreate,
    DocumentOut,
    ReminderOut,
    EventCreate,
    EventOut,
    HearingNoteIn,
    SummaryOut,
    TaskCreate,
    TaskOut,
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


def require_user(x_api_token: str | None = Header(default=None)) -> str:
    if x_api_token in (settings.owner_token, settings.member_token):
        return "owner" if x_api_token == settings.owner_token else "member"
    raise HTTPException(status_code=401, detail="Unauthorized. Provide X-API-Token header.")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


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
