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
