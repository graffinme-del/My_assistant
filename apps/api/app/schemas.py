from datetime import date, datetime

from pydantic import BaseModel, Field


class CaseCreate(BaseModel):
    title: str
    court_name: str
    case_number: str
    status: str = "new"
    stage: str = "analysis"


class CaseOut(BaseModel):
    id: int
    title: str
    court_name: str
    case_number: str
    status: str
    stage: str
    summary: str
    next_hearing_date: date | None
    created_at: datetime

    class Config:
        from_attributes = True


class EventCreate(BaseModel):
    event_type: str = "note"
    body: str = Field(min_length=2)


class EventOut(BaseModel):
    id: int
    case_id: int
    event_type: str
    body: str
    created_at: datetime

    class Config:
        from_attributes = True


class TaskCreate(BaseModel):
    title: str
    description: str = ""
    priority: str = "medium"
    status: str = "open"
    due_date: date | None = None


class TaskOut(BaseModel):
    id: int
    case_id: int
    title: str
    description: str
    priority: str
    status: str
    due_date: date | None
    created_at: datetime

    class Config:
        from_attributes = True


class ReminderOut(BaseModel):
    id: int
    task_id: int
    remind_at: datetime
    channel: str
    sent: bool

    class Config:
        from_attributes = True


class DocumentCreate(BaseModel):
    filename: str
    category: str = "other"
    s3_key: str
    extracted_text: str = ""


class DocumentOut(BaseModel):
    id: int
    case_id: int
    filename: str
    category: str
    s3_key: str
    extracted_text: str
    created_at: datetime

    class Config:
        from_attributes = True


class DocumentIngestOut(BaseModel):
    document: DocumentOut
    matched_case_id: int
    matched_case_number: str
    category: str
    confidence: float
    routing_mode: str
    routing_model: str
    note: str


class HearingNoteIn(BaseModel):
    text: str


class SummaryOut(BaseModel):
    case_id: int
    summary: str
    next_hearing_date: date | None


class AssistantIngestIn(BaseModel):
    text: str
    preferred_case_number: str | None = None
    allow_case_create: bool = True


class AssistantIngestOut(BaseModel):
    case_id: int
    case_number: str
    created_case: bool
    mode: str  # hearing-parser | message
    created_tasks: int = 0
    next_hearing_date: date | None = None
    reply: str = ""


class BulkIngestOut(BaseModel):
    total_files: int
    ingested_files: int
    skipped_files: int
    errors: list[str] = []


class AssistantSummaryIn(BaseModel):
    text: str
    preferred_case_number: str | None = None


class AssistantSummaryOut(BaseModel):
    case_id: int
    case_number: str
    summary: str
    next_hearing_date: date | None
