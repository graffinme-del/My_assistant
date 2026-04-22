from datetime import date, datetime

from sqlalchemy import Date, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db import Base


class Case(Base):
    __tablename__ = "cases"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    title: Mapped[str] = mapped_column(String(255))
    court_name: Mapped[str] = mapped_column(String(255))
    case_number: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    status: Mapped[str] = mapped_column(String(100), default="new")
    stage: Mapped[str] = mapped_column(String(100), default="analysis")
    summary: Mapped[str] = mapped_column(Text, default="")
    next_hearing_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    events: Mapped[list["CaseEvent"]] = relationship(back_populates="case")
    tasks: Mapped[list["Task"]] = relationship(back_populates="case")
    documents: Mapped[list["Document"]] = relationship(back_populates="case")
    tags: Mapped[list["CaseTag"]] = relationship(back_populates="case", cascade="all, delete-orphan")
    conversations: Mapped[list["Conversation"]] = relationship(back_populates="active_case")


class CaseEvent(Base):
    __tablename__ = "case_events"

    id: Mapped[int] = mapped_column(primary_key=True)
    case_id: Mapped[int] = mapped_column(ForeignKey("cases.id", ondelete="CASCADE"))
    event_type: Mapped[str] = mapped_column(String(100), default="note")
    body: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    case: Mapped[Case] = relationship(back_populates="events")


class Task(Base):
    __tablename__ = "tasks"

    id: Mapped[int] = mapped_column(primary_key=True)
    case_id: Mapped[int] = mapped_column(ForeignKey("cases.id", ondelete="CASCADE"))
    title: Mapped[str] = mapped_column(String(255))
    description: Mapped[str] = mapped_column(Text, default="")
    priority: Mapped[str] = mapped_column(String(30), default="medium")
    status: Mapped[str] = mapped_column(String(30), default="open")
    due_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    case: Mapped[Case] = relationship(back_populates="tasks")


class Document(Base):
    __tablename__ = "documents"

    id: Mapped[int] = mapped_column(primary_key=True)
    case_id: Mapped[int] = mapped_column(ForeignKey("cases.id", ondelete="CASCADE"))
    filename: Mapped[str] = mapped_column(String(255))
    category: Mapped[str] = mapped_column(String(100), default="other")
    s3_key: Mapped[str] = mapped_column(String(500))
    extracted_text: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    case: Mapped[Case] = relationship(back_populates="documents")
    chunks: Mapped[list["DocumentChunk"]] = relationship(back_populates="document", cascade="all, delete-orphan")


class Reminder(Base):
    __tablename__ = "reminders"

    id: Mapped[int] = mapped_column(primary_key=True)
    task_id: Mapped[int] = mapped_column(ForeignKey("tasks.id", ondelete="CASCADE"))
    remind_at: Mapped[datetime] = mapped_column(DateTime)
    channel: Mapped[str] = mapped_column(String(30), default="push")
    sent: Mapped[bool] = mapped_column(default=False)


class CaseTag(Base):
    __tablename__ = "case_tags"

    id: Mapped[int] = mapped_column(primary_key=True)
    case_id: Mapped[int] = mapped_column(ForeignKey("cases.id", ondelete="CASCADE"), index=True)
    value: Mapped[str] = mapped_column(String(255), index=True)
    kind: Mapped[str] = mapped_column(String(30), default="keyword")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    case: Mapped[Case] = relationship(back_populates="tags")


class PendingMovePlan(Base):
    __tablename__ = "pending_move_plans"

    id: Mapped[int] = mapped_column(primary_key=True)
    case_id: Mapped[int] = mapped_column(ForeignKey("cases.id", ondelete="CASCADE"), index=True)
    title: Mapped[str] = mapped_column(String(255))
    keywords_json: Mapped[str] = mapped_column(Text, default="[]")
    doc_ids_json: Mapped[str] = mapped_column(Text, default="[]")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class PendingSemanticPlan(Base):
    """План смысловой перестройки (кластеры дел и т.п.), ждёт подтверждения в чате."""

    __tablename__ = "pending_semantic_plans"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_key: Mapped[str] = mapped_column(String(80), index=True)
    plan_kind: Mapped[str] = mapped_column(String(40), default="case_clusters", index=True)
    payload_json: Mapped[str] = mapped_column(Text, default="{}")
    preview_text: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class Conversation(Base):
    __tablename__ = "conversations"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_key: Mapped[str] = mapped_column(String(50), unique=True, index=True)
    title: Mapped[str] = mapped_column(String(255), default="Основной чат")
    active_case_id: Mapped[int | None] = mapped_column(ForeignKey("cases.id", ondelete="SET NULL"), nullable=True)
    rolling_summary: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    active_case: Mapped[Case | None] = relationship(back_populates="conversations")
    messages: Mapped[list["ConversationMessage"]] = relationship(
        back_populates="conversation", cascade="all, delete-orphan"
    )


class ConversationMessage(Base):
    __tablename__ = "conversation_messages"

    id: Mapped[int] = mapped_column(primary_key=True)
    conversation_id: Mapped[int] = mapped_column(ForeignKey("conversations.id", ondelete="CASCADE"), index=True)
    role: Mapped[str] = mapped_column(String(20), index=True)
    case_id: Mapped[int | None] = mapped_column(ForeignKey("cases.id", ondelete="SET NULL"), nullable=True)
    content: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    conversation: Mapped[Conversation] = relationship(back_populates="messages")
    case: Mapped[Case | None] = relationship()


class DocumentChunk(Base):
    __tablename__ = "document_chunks"

    id: Mapped[int] = mapped_column(primary_key=True)
    document_id: Mapped[int] = mapped_column(ForeignKey("documents.id", ondelete="CASCADE"), index=True)
    case_id: Mapped[int] = mapped_column(ForeignKey("cases.id", ondelete="CASCADE"), index=True)
    chunk_index: Mapped[int] = mapped_column(index=True)
    page_hint: Mapped[str] = mapped_column(String(50), default="")
    chunk_text: Mapped[str] = mapped_column(Text)
    search_text: Mapped[str] = mapped_column(Text, default="")
    score: Mapped[float] = mapped_column(Float, default=0.0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    document: Mapped[Document] = relationship(back_populates="chunks")
    case: Mapped[Case] = relationship()


class CourtWatchProfile(Base):
    __tablename__ = "court_watch_profiles"

    id: Mapped[int] = mapped_column(primary_key=True)
    profile_type: Mapped[str] = mapped_column(String(30), index=True)
    query_value: Mapped[str] = mapped_column(String(255), index=True)
    title: Mapped[str] = mapped_column(String(255), default="")
    is_active: Mapped[bool] = mapped_column(default=True)
    auto_download: Mapped[bool] = mapped_column(default=True)
    check_interval_hours: Mapped[int] = mapped_column(default=24)
    last_checked_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class CourtSyncJob(Base):
    __tablename__ = "court_sync_jobs"

    id: Mapped[int] = mapped_column(primary_key=True)
    watch_profile_id: Mapped[int | None] = mapped_column(
        ForeignKey("court_watch_profiles.id", ondelete="SET NULL"), nullable=True, index=True
    )
    trigger_type: Mapped[str] = mapped_column(String(30), default="manual")
    requested_by: Mapped[str] = mapped_column(String(50), default="owner")
    query_type: Mapped[str] = mapped_column(String(30), index=True)
    query_value: Mapped[str] = mapped_column(String(255))
    run_mode: Mapped[str] = mapped_column(String(30), default="preview")
    status: Mapped[str] = mapped_column(String(30), default="pending", index=True)
    step: Mapped[str] = mapped_column(String(100), default="queued")
    report_text: Mapped[str] = mapped_column(Text, default="")
    manual_action_note: Mapped[str] = mapped_column(Text, default="")
    result_json: Mapped[str] = mapped_column(Text, default="{}")
    parser_year_min: Mapped[int | None] = mapped_column(Integer, nullable=True)
    parser_year_max: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    started_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class CourtSyncRun(Base):
    __tablename__ = "court_sync_runs"

    id: Mapped[int] = mapped_column(primary_key=True)
    job_id: Mapped[int] = mapped_column(ForeignKey("court_sync_jobs.id", ondelete="CASCADE"), index=True)
    status: Mapped[str] = mapped_column(String(30), default="running")
    step: Mapped[str] = mapped_column(String(100), default="started")
    message: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class CourtCaseSource(Base):
    __tablename__ = "court_case_sources"

    id: Mapped[int] = mapped_column(primary_key=True)
    watch_profile_id: Mapped[int | None] = mapped_column(
        ForeignKey("court_watch_profiles.id", ondelete="SET NULL"), nullable=True, index=True
    )
    case_id: Mapped[int | None] = mapped_column(ForeignKey("cases.id", ondelete="SET NULL"), nullable=True, index=True)
    source_system: Mapped[str] = mapped_column(String(30), default="kad")
    remote_case_id: Mapped[str] = mapped_column(String(255), index=True)
    card_url: Mapped[str] = mapped_column(String(1000), default="")
    case_number: Mapped[str] = mapped_column(String(255), default="", index=True)
    title: Mapped[str] = mapped_column(String(255), default="")
    court_name: Mapped[str] = mapped_column(String(255), default="")
    participants_json: Mapped[str] = mapped_column(Text, default="[]")
    is_tracked: Mapped[bool] = mapped_column(default=True)
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    last_synced_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class CourtDocumentSource(Base):
    __tablename__ = "court_document_sources"

    id: Mapped[int] = mapped_column(primary_key=True)
    case_source_id: Mapped[int | None] = mapped_column(
        ForeignKey("court_case_sources.id", ondelete="SET NULL"), nullable=True, index=True
    )
    local_document_id: Mapped[int | None] = mapped_column(
        ForeignKey("documents.id", ondelete="SET NULL"), nullable=True, index=True
    )
    remote_document_id: Mapped[str] = mapped_column(String(255), index=True)
    title: Mapped[str] = mapped_column(String(500), default="")
    filename: Mapped[str] = mapped_column(String(255), default="")
    file_url: Mapped[str] = mapped_column(String(1000), default="")
    published_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    status: Mapped[str] = mapped_column(String(30), default="discovered")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    last_downloaded_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class CaseEmbedding(Base):
    __tablename__ = "case_embeddings"

    id: Mapped[int] = mapped_column(primary_key=True)
    case_id: Mapped[int] = mapped_column(ForeignKey("cases.id", ondelete="CASCADE"))
    chunk_text: Mapped[str] = mapped_column(Text)
    score: Mapped[float] = mapped_column(Float, default=0.0)
