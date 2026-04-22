from datetime import date, datetime

from pydantic import BaseModel, Field


class CaseCreate(BaseModel):
    title: str
    court_name: str
    case_number: str
    status: str = "new"
    stage: str = "analysis"


class CaseTagOut(BaseModel):
    id: int
    value: str
    kind: str

    class Config:
        from_attributes = True


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
    updated_at: datetime
    tags: list[CaseTagOut] = []

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
    # Если несколько дел подходят по ФИО и LLM не выбрал — просим пользователя уточнить (документ в UNSORTED).
    needs_participant_clarification: bool = False
    participant_clarification: str | None = None
    participant_clarification_cases: list[str] = []


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


class AssistantActiveCaseIn(BaseModel):
    """Выбранное в UI дело — активная папка для чата (удаление «в этой папке», контекст ответов)."""

    case_id: int


class ConversationMessageOut(BaseModel):
    id: int
    role: str
    case_id: int | None
    content: str
    created_at: datetime

    class Config:
        from_attributes = True


class AssistantIngestOut(BaseModel):
    case_id: int
    case_number: str
    created_case: bool
    mode: str  # hearing-parser | message
    created_tasks: int = 0
    next_hearing_date: date | None = None
    reply: str = ""
    user_message_id: int | None = None
    assistant_message_id: int | None = None


class BulkIngestOut(BaseModel):
    total_files: int
    ingested_files: int
    skipped_files: int
    errors: list[str] = []


class AutoSortUnsortedOut(BaseModel):
    moved: int
    remained: int
    created_cases: int
    moved_by_case_number: int
    moved_by_tag_match: int
    details: list[str] = []


class AssistantSummaryIn(BaseModel):
    text: str
    preferred_case_number: str | None = None


class AssistantSummaryOut(BaseModel):
    case_id: int
    case_number: str
    summary: str
    next_hearing_date: date | None


class CourtSyncJobOut(BaseModel):
    id: int
    watch_profile_id: int | None = None
    status: str
    step: str
    query_type: str
    query_value: str
    run_mode: str
    report_text: str
    parser_year_min: int | None = None
    parser_year_max: int | None = None

    class Config:
        from_attributes = True


class CourtSyncClaimOut(BaseModel):
    job: CourtSyncJobOut | None = None


class CourtSyncGetOut(BaseModel):
    job: CourtSyncJobOut


class CourtSyncProgressIn(BaseModel):
    step: str
    message: str = ""


class CourtSyncCompleteIn(BaseModel):
    status: str
    report_text: str = ""
    result_json: dict = {}


class CourtSyncCaseSourceIn(BaseModel):
    remote_case_id: str
    case_number: str = ""
    card_url: str = ""
    title: str = ""
    court_name: str = ""
    participants: list[str] = []
    linked_case_id: int | None = None


class CourtSyncDocumentSourceIn(BaseModel):
    remote_document_id: str
    case_source_id: int | None = None
    local_document_id: int | None = None
    title: str = ""
    filename: str = ""
    file_url: str = ""
    status: str = "discovered"
