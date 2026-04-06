from __future__ import annotations

import json
import re
from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from .models import (
    Case,
    CaseEvent,
    Conversation,
    ConversationMessage,
    CourtCaseSource,
    CourtDocumentSource,
    CourtSyncJob,
    CourtSyncRun,
    CourtWatchProfile,
)


def create_watch_profile(
    db: Session,
    *,
    profile_type: str,
    query_value: str,
    title: str = "",
    auto_download: bool = True,
) -> tuple[CourtWatchProfile, bool]:
    existing = (
        db.query(CourtWatchProfile)
        .filter(CourtWatchProfile.profile_type == profile_type, CourtWatchProfile.query_value == query_value)
        .first()
    )
    if existing:
        if not existing.is_active:
            existing.is_active = True
            db.add(existing)
            db.commit()
            db.refresh(existing)
        return existing, False
    profile = CourtWatchProfile(
        profile_type=profile_type,
        query_value=query_value,
        title=title or query_value,
        auto_download=auto_download,
    )
    db.add(profile)
    db.commit()
    db.refresh(profile)
    return profile, True


def create_sync_job(
    db: Session,
    *,
    query_type: str,
    query_value: str,
    run_mode: str,
    requested_by: str,
    trigger_type: str = "manual",
    watch_profile_id: int | None = None,
    parser_year_min: int | None = None,
    parser_year_max: int | None = None,
) -> CourtSyncJob:
    job = CourtSyncJob(
        query_type=query_type,
        query_value=query_value,
        run_mode=run_mode,
        requested_by=requested_by,
        trigger_type=trigger_type,
        watch_profile_id=watch_profile_id,
        parser_year_min=parser_year_min,
        parser_year_max=parser_year_max,
        status="pending",
        step="queued",
    )
    db.add(job)
    db.commit()
    db.refresh(job)
    return job


def claim_next_sync_job(db: Session) -> CourtSyncJob | None:
    job = (
        db.query(CourtSyncJob)
        .filter(CourtSyncJob.status == "pending")
        .order_by(CourtSyncJob.created_at.asc())
        .first()
    )
    if not job:
        return None
    job.status = "running"
    job.step = "claimed"
    job.started_at = datetime.utcnow()
    db.add(job)
    db.add(CourtSyncRun(job_id=job.id, status="running", step="claimed", message="Job claimed by worker"))
    db.commit()
    db.refresh(job)
    return job


def update_job_progress(db: Session, job_id: int, *, step: str, message: str) -> CourtSyncJob | None:
    job = db.query(CourtSyncJob).filter(CourtSyncJob.id == job_id).first()
    if not job:
        return None
    job.step = step[:100]
    if message:
        job.report_text = (job.report_text + ("\n" if job.report_text else "") + message).strip()[:20000]
    db.add(job)
    db.add(CourtSyncRun(job_id=job.id, status=job.status, step=step[:100], message=message[:4000]))
    db.commit()
    db.refresh(job)
    return job


def complete_sync_job(db: Session, job_id: int, *, status: str, result: dict, report_text: str = "") -> CourtSyncJob | None:
    job = db.query(CourtSyncJob).filter(CourtSyncJob.id == job_id).first()
    if not job:
        return None
    job.status = status
    job.step = "completed" if status == "done" else status
    job.finished_at = datetime.utcnow()
    job.result_json = json.dumps(result, ensure_ascii=False)
    if report_text:
        job.report_text = (job.report_text + ("\n" if job.report_text else "") + report_text).strip()[:20000]
    db.add(job)
    db.add(
        CourtSyncRun(
            job_id=job.id,
            status=status,
            step=job.step,
            message=report_text[:4000],
            finished_at=datetime.utcnow(),
        )
    )
    if job.watch_profile_id:
        profile = db.query(CourtWatchProfile).filter(CourtWatchProfile.id == job.watch_profile_id).first()
        if profile:
            profile.last_checked_at = datetime.utcnow()
            db.add(profile)
    db.commit()
    db.refresh(job)
    return job


def upsert_case_source(
    db: Session,
    *,
    remote_case_id: str,
    case_number: str = "",
    card_url: str = "",
    title: str = "",
    court_name: str = "",
    participants: list[str] | None = None,
    watch_profile_id: int | None = None,
    linked_case_id: int | None = None,
) -> CourtCaseSource:
    source = db.query(CourtCaseSource).filter(CourtCaseSource.remote_case_id == remote_case_id).first()
    if not source:
        source = CourtCaseSource(remote_case_id=remote_case_id)
    source.watch_profile_id = watch_profile_id
    source.case_id = linked_case_id
    source.case_number = case_number[:255]
    source.card_url = card_url[:1000]
    source.title = title[:255]
    source.court_name = court_name[:255]
    source.participants_json = json.dumps(participants or [], ensure_ascii=False)
    source.last_seen_at = datetime.utcnow()
    db.add(source)
    db.commit()
    db.refresh(source)
    return source


def upsert_document_source(
    db: Session,
    *,
    remote_document_id: str,
    case_source_id: int | None = None,
    local_document_id: int | None = None,
    title: str = "",
    filename: str = "",
    file_url: str = "",
    status: str = "discovered",
) -> CourtDocumentSource:
    source = db.query(CourtDocumentSource).filter(CourtDocumentSource.remote_document_id == remote_document_id).first()
    if not source:
        source = CourtDocumentSource(remote_document_id=remote_document_id)
    source.case_source_id = case_source_id
    source.local_document_id = local_document_id
    source.title = title[:500]
    source.filename = filename[:255]
    source.file_url = file_url[:1000]
    source.status = status
    source.last_seen_at = datetime.utcnow()
    if local_document_id:
        source.last_downloaded_at = datetime.utcnow()
    db.add(source)
    db.commit()
    db.refresh(source)
    return source


def enqueue_nightly_jobs(db: Session) -> int:
    now = datetime.utcnow()
    count = 0
    profiles = db.query(CourtWatchProfile).filter(CourtWatchProfile.is_active == True).all()  # noqa: E712
    for profile in profiles:
        due = profile.last_checked_at is None or (
            profile.last_checked_at <= now - timedelta(hours=max(1, profile.check_interval_hours))
        )
        if not due:
            continue
        create_sync_job(
            db,
            query_type=profile.profile_type,
            query_value=profile.query_value,
            run_mode="sync",
            requested_by="nightly",
            trigger_type="nightly",
            watch_profile_id=profile.id,
        )
        count += 1
    return count


_STATUS_RU = {
    "pending": "в очереди",
    "running": "выполняется",
    "done": "завершена",
    "failed": "ошибка",
    "needs_manual_step": "нужна ручная проверка",
}

_STEP_RU = {
    "queued": "ожидает запуска",
    "searching": "поиск в КАД",
    "opening_case": "открытие карточки дела",
    "downloading": "скачивание файлов",
    "completed": "завершено",
    "needs_manual_step": "нужны действия",
    "failed": "ошибка",
}

_QUERY_TYPE_RU = {
    "participant_name": "участник",
    "case_number": "номер дела",
    "inn": "ИНН",
    "ogrn": "ОГРН",
    "organization_name": "организация",
    "card_url": "ссылка на карточку",
}


def _query_line_ru(query_type: str, query_value: str) -> str:
    label = _QUERY_TYPE_RU.get(query_type, query_type)
    qv = (query_value or "").strip()
    if len(qv) > 100:
        qv = qv[:97] + "…"
    return f"{label}: «{qv}»"


def _report_snippet_for_user(report: str, *, max_chars: int = 240) -> str:
    """Убирает URL и техно-логи; оставляет короткую человекочитаемую строку."""
    if not (report or "").strip():
        return ""
    fallback_note = ""
    clean_lines: list[str] = []
    for ln in report.splitlines():
        s = ln.strip()
        if not s:
            continue
        low = s.lower()
        if "parser-api pdf_download" in low:
            continue
        if "playwright fallback" in low and not fallback_note:
            fallback_note = "Часть файлов качалась запасным способом (браузер), когда API не смог скачать PDF."
            continue
        if re.search(r"https?://", s) and len(s) > 80:
            continue
        if any(
            k in s
            for k in (
                "Итог:",
                "Найдено дел",
                "По запросу",
                "Поставил задачу",
                "дела не найдены",
                "не найдены",
                "Ошибка поиска",
                "Не удалось",
                "Автоскачивание",
                "лимит",
            )
        ):
            s2 = re.sub(r"https?://\S+", "…", s)
            clean_lines.append(s2.strip())

    parts: list[str] = []
    if fallback_note:
        parts.append(fallback_note)
    if clean_lines:
        parts.append(" ".join(clean_lines[-2:])[:max_chars])
    text = " ".join(parts).strip()
    if not text:
        for ln in report.splitlines():
            s = ln.strip()
            if s and "http" not in s[:12] and len(s) < 200:
                return (s[:max_chars] + "…") if len(s) > max_chars else s
        return ""
    return (text[:max_chars] + "…") if len(text) > max_chars else text


def _job_stats_line(result_json_raw: str | None) -> str | None:
    try:
        rj = json.loads(result_json_raw or "{}")
    except Exception:
        return None
    if not isinstance(rj, dict):
        return None
    parts: list[str] = []
    if rj.get("downloaded") is not None:
        parts.append(f"скачано файлов: {rj['downloaded']}")
    if rj.get("documents_found") is not None:
        parts.append(f"найдено документов: {rj['documents_found']}")
    if rj.get("cases_found") is not None:
        parts.append(f"дел в выдаче: {rj['cases_found']}")
    if rj.get("failures"):
        parts.append(f"ошибок при загрузке: {rj['failures']}")
    if rj.get("duplicates_skipped"):
        parts.append(f"пропущено как дубликаты: {rj['duplicates_skipped']}")
    if not parts:
        return None
    return "Итог: " + ", ".join(parts) + "."


def format_recent_download_jobs_status(db: Session, *, limit: int = 5) -> str:
    """Краткий статус последних задач загрузки из КАД — без сырых URL и логов Parser-API."""
    jobs = (
        db.query(CourtSyncJob)
        .filter(CourtSyncJob.run_mode == "download")
        .order_by(CourtSyncJob.id.desc())
        .limit(limit)
        .all()
    )
    if not jobs:
        return "Фоновых загрузок из КАД пока не было. Когда поставите задачу («скачай из КАД…»), статус появится здесь."

    lines: list[str] = [
        "Кратко по последним загрузкам из КАД (это не список файлов в открытой папке в чате):",
        "",
    ]
    now = datetime.utcnow()
    for j in jobs:
        st = _STATUS_RU.get(j.status, j.status)
        stp = _STEP_RU.get(j.step, j.step)
        lines.append(f"• Задача #{j.id} — {st}. Сейчас: {stp}.")
        lines.append(f"  {_query_line_ru(j.query_type, j.query_value)}")

        stats = _job_stats_line(j.result_json)
        if stats:
            lines.append(f"  {stats}")

        if j.status == "running" and j.started_at:
            started = j.started_at.replace(tzinfo=None) if j.started_at.tzinfo else j.started_at
            age = now - started
            if age > timedelta(minutes=45):
                lines.append(
                    f"  Долго выполняется (~{int(age.total_seconds() // 60)} мин) — "
                    "проверьте, что контейнер worker запущен."
                )

        snippet = _report_snippet_for_user(j.report_text or "")
        if snippet and not stats:
            lines.append(f"  {snippet}")
        elif snippet and stats and j.status in ("failed", "needs_manual_step"):
            lines.append(f"  {snippet}")

        lines.append("")

    lines.append("Полный текст отчёта по одной задаче: напишите «отчёт по задаче #N» (подставьте номер).")
    return "\n".join(lines).strip()


def format_sync_status(db: Session, *, limit: int = 8) -> str:
    jobs = db.query(CourtSyncJob).order_by(CourtSyncJob.created_at.desc()).limit(limit).all()
    if not jobs:
        return "Задач судебной синхронизации пока нет."
    lines = ["Последние задачи судебной синхронизации:"]
    for job in jobs:
        lines.append(
            f'- #{job.id} | {job.status} | {job.run_mode} | {job.query_type}="{job.query_value}" | шаг: {job.step}'
        )
    return "\n".join(lines)


def format_nightly_report(db: Session, *, hours: int = 24) -> str:
    since = datetime.utcnow() - timedelta(hours=hours)
    jobs = (
        db.query(CourtSyncJob)
        .filter(CourtSyncJob.trigger_type == "nightly", CourtSyncJob.created_at >= since)
        .order_by(CourtSyncJob.created_at.desc())
        .all()
    )
    if not jobs:
        return "За последнюю ночь автоматических загрузок из суда не было."
    lines = ["Что нового скачано за ночь:"]
    for job in jobs[:12]:
        lines.append(f'- #{job.id} | {job.status} | {job.query_type}="{job.query_value}"')
        if job.report_text:
            lines.append(f"  {job.report_text[:220]}")
    return "\n".join(lines)


def save_sync_report_to_conversation(
    db: Session,
    *,
    conversation: Conversation | None,
    case: Case | None,
    text: str,
) -> None:
    if case is not None:
        db.add(CaseEvent(case_id=case.id, event_type="court_sync_report", body=text[:12000]))
    if conversation is not None:
        db.add(
            ConversationMessage(
                conversation_id=conversation.id,
                role="assistant",
                case_id=case.id if case else None,
                content=text[:12000],
            )
        )
    db.commit()
