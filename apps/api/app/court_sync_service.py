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
    Document,
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
    dedupe: bool = True,
) -> tuple[CourtSyncJob, bool]:
    if dedupe:
        existing = (
            db.query(CourtSyncJob)
            .filter(
                CourtSyncJob.query_type == query_type,
                CourtSyncJob.query_value == query_value,
                CourtSyncJob.run_mode == run_mode,
                CourtSyncJob.status.in_(("pending", "running")),
            )
            .order_by(CourtSyncJob.id.desc())
            .first()
        )
        if existing:
            return existing, False
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
    return job, True


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
    if job.finished_at is not None:
        return job
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
    if job.finished_at is not None:
        return job
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


def cancel_active_court_sync_jobs(db: Session) -> dict[str, int]:
    """Снимает все задачи в очереди (pending) и останавливает помеченные как running (воркер прекращает между шагами)."""
    n = 0
    active = (
        db.query(CourtSyncJob)
        .filter(CourtSyncJob.status.in_(("pending", "running")))
        .order_by(CourtSyncJob.id.asc())
        .all()
    )
    for job in active:
        complete_sync_job(
            db,
            job.id,
            status="cancelled",
            result={"reason": "user_cancel_all"},
            report_text="Задача снята по запросу пользователя (очистка очереди / остановка старых загрузок).",
        )
        n += 1
    return {"cancelled": n}


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
        _, _ = create_sync_job(
            db,
            query_type=profile.profile_type,
            query_value=profile.query_value,
            run_mode="sync",
            requested_by="nightly",
            trigger_type="nightly",
            watch_profile_id=profile.id,
            dedupe=False,
        )
        count += 1
    return count


_STATUS_RU = {
    "pending": "в очереди",
    "running": "выполняется",
    "done": "завершена",
    "failed": "ошибка",
    "needs_manual_step": "нужна ручная проверка",
    "cancelled": "отменена",
}

_STEP_RU = {
    "queued": "ожидает запуска",
    "claimed": "запуск",
    "searching": "поиск в картотеке",
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
        if "participant_name=" in low or "query_type=" in low or "run_mode=" in low:
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


def _job_stats_narrative(result_json_raw: str | None) -> str | None:
    """Короткое предложение с цифрами — без сухого списка «ключ: значение»."""
    try:
        rj = json.loads(result_json_raw or "{}")
    except Exception:
        return None
    if not isinstance(rj, dict):
        return None
    parts: list[str] = []
    if rj.get("downloaded") is not None:
        parts.append(f"новых файлов сохранено — {rj['downloaded']}")
    if rj.get("documents_found") is not None:
        parts.append(f"в выдаче найдено документов — {rj['documents_found']}")
    if rj.get("cases_found") is not None:
        parts.append(f"дел в выдаче — {rj['cases_found']}")
    if rj.get("failures"):
        parts.append(f"не удалось скачать — {rj['failures']}")
    if rj.get("duplicates_skipped"):
        parts.append(f"пропущено как уже имеющиеся — {rj['duplicates_skipped']}")
    if not parts:
        return None
    return "По цифрам: " + "; ".join(parts) + "."


def format_kad_download_count_answer(db: Session) -> str:
    """Один ответ на «сколько скачали»: факт в базе + кратко по последней задаче."""
    n_saved = db.query(CourtDocumentSource).filter(CourtDocumentSource.local_document_id.isnot(None)).count()
    latest = (
        db.query(CourtSyncJob)
        .filter(CourtSyncJob.run_mode == "download")
        .order_by(CourtSyncJob.id.desc())
        .first()
    )
    head = (
        f"В приложении сейчас сохранено файлов, пришедших из картотеки: {n_saved} "
        "(это реально лежащие в хранилище документы, не просто строки в отчёте задачи)."
    )
    if not latest:
        return head
    try:
        rj = json.loads(latest.result_json or "{}")
    except Exception:
        rj = {}
    dl = rj.get("downloaded")
    if latest.status == "running":
        return (
            f"{head} Последняя загрузка (№{latest.id}) ещё выполняется — число выше будет расти по мере сохранения файлов."
        )
    if latest.status == "pending":
        return f"{head} Последняя поставленная загрузка (№{latest.id}) ещё в очереди."
    extra = ""
    if isinstance(dl, int):
        extra = f" По отчёту последней завершённой задачи №{latest.id} в выгрузке было новых файлов: {dl}."
    elif latest.status in ("failed", "needs_manual_step"):
        st_ru = _STATUS_RU.get(latest.status, latest.status)
        extra = f" Последняя задача №{latest.id} завершилась с пометкой «{st_ru}» — детали: «отчёт по задаче #{latest.id}»."
    return head + extra


def format_kad_downloaded_documents_list(db: Session, *, limit: int = 80) -> str:
    """Имена файлов, реально сохранённых из КАД (есть локальный Document)."""
    rows = (
        db.query(CourtDocumentSource)
        .filter(CourtDocumentSource.local_document_id.isnot(None))
        .order_by(CourtDocumentSource.last_downloaded_at.desc().nulls_last(), CourtDocumentSource.id.desc())
        .limit(limit)
        .all()
    )
    if not rows:
        return (
            "Пока нет сохранённых в приложении файлов из картотеки (или загрузка ещё не успела их записать). "
            "Когда фоновая загрузка завершится, список появится здесь; краткий ход процесса — по фразе «статус загрузки»."
        )
    doc_ids = [r.local_document_id for r in rows if r.local_document_id]
    docs = {d.id: d for d in db.query(Document).filter(Document.id.in_(doc_ids)).all()}
    case_ids = list({d.case_id for d in docs.values()})
    cases = {c.id: c for c in db.query(Case).filter(Case.id.in_(case_ids)).all()} if case_ids else {}
    cs_ids = [r.case_source_id for r in rows if r.case_source_id]
    case_sources = {
        cs.id: cs for cs in db.query(CourtCaseSource).filter(CourtCaseSource.id.in_(cs_ids)).all()
    } if cs_ids else {}
    lines = [
        f"Вот сохранённые из картотеки файлы (показано до {limit} шт., от новых к старым):",
        "",
    ]
    for ds in rows:
        doc = docs.get(ds.local_document_id) if ds.local_document_id else None
        fn = (doc.filename if doc else None) or ds.filename or ds.title or f"документ {ds.remote_document_id}"
        doc_id = ds.local_document_id
        folder = ""
        if doc and doc.case_id in cases:
            c = cases[doc.case_id]
            folder = f' — в папке «{c.title}»' if c.title else ""
        cs = case_sources.get(ds.case_source_id) if ds.case_source_id else None
        case_hint = ""
        if cs and (cs.case_number or cs.title):
            case_hint = f" (дело в КАД: {cs.case_number or cs.title})"
        lines.append(f"• [{doc_id}] {fn}{folder}{case_hint} — скачать: /api/documents/{doc_id}/download")
    if len(rows) >= limit:
        lines.append("")
        lines.append(f"Показан лимит {limit}; если файлов больше, уточните по делу или откройте папку в интерфейсе.")
    return "\n".join(lines)


def format_recent_download_jobs_status(db: Session, *, limit: int = 5) -> str:
    """Краткий статус последних загрузок из КАД — связный текст, без сырых URL и логов."""
    jobs = (
        db.query(CourtSyncJob)
        .filter(CourtSyncJob.run_mode == "download")
        .order_by(CourtSyncJob.id.desc())
        .limit(limit)
        .all()
    )
    if not jobs:
        return (
            "Пока не было фоновых загрузок из картотеки. Когда попросите скачать материалы "
            "(например, «скачай из КАД…»), здесь появится краткий итог."
        )

    intro = (
        "Ниже — кратко по последним фоновым загрузкам из картотеки арбитражных дел. "
        "Это не то же самое, что список документов в открытой у вас папке в чате: там только то, что уже привязано к делу."
    )
    blocks: list[str] = [intro, ""]
    now = datetime.utcnow()
    for j in jobs:
        stp = _STEP_RU.get(j.step, j.step)
        qline = _query_line_ru(j.query_type, j.query_value)
        if j.status == "running":
            head = f"Загрузка №{j.id} ещё идёт: сейчас — {stp}. {qline}"
        elif j.status == "pending":
            head = f"Загрузка №{j.id} стоит в очереди. {qline}"
        elif j.status == "done":
            head = f"Загрузка №{j.id} завершена. {qline}"
        elif j.status == "failed":
            head = f"Загрузка №{j.id} остановилась с ошибкой. {qline}"
        elif j.status == "needs_manual_step":
            head = f"Загрузка №{j.id} в основном обработана, но нужна ручная проверка. {qline}"
        elif j.status == "cancelled":
            head = f"Загрузка №{j.id} отменена. {qline}"
        else:
            st_ru = _STATUS_RU.get(j.status, j.status)
            head = f"Загрузка №{j.id}: статус «{st_ru}», этап — {stp}. {qline}"

        paras: list[str] = [head + "."]

        stats = _job_stats_narrative(j.result_json)
        if stats:
            paras.append(stats)

        if j.status == "running" and j.started_at:
            started = j.started_at.replace(tzinfo=None) if j.started_at.tzinfo else j.started_at
            age = now - started
            if age > timedelta(minutes=45):
                paras.append(
                    f"Процесс идёт уже около {int(age.total_seconds() // 60)} минут. "
                    "Если цифры не меняются, проверьте, что на сервере запущена фоновая служба загрузки документов."
                )

        snippet = _report_snippet_for_user(j.report_text or "")
        if snippet and not stats:
            paras.append(snippet)
        elif snippet and stats and j.status in ("failed", "needs_manual_step"):
            paras.append(snippet)

        blocks.append(" ".join(paras))
        blocks.append("")

    blocks.append(
        "Подробный текст по одной загрузке можно запросить фразой «отчёт по задаче #N» — подставьте номер из списка выше."
    )
    return "\n".join(blocks).strip()


def format_sync_status(db: Session, *, limit: int = 8) -> str:
    jobs = db.query(CourtSyncJob).order_by(CourtSyncJob.created_at.desc()).limit(limit).all()
    if not jobs:
        return "Задач судебной синхронизации пока не запускали."
    lines = [
        "Последние процессы синхронизации с картотекой (кратко, для справки):",
        "",
    ]
    for job in jobs:
        st = _STATUS_RU.get(job.status, job.status)
        stp = _STEP_RU.get(job.step, job.step)
        qv = (job.query_value or "").strip()
        if len(qv) > 80:
            qv = qv[:77] + "…"
        lines.append(f"• №{job.id} — {st}, этап: {stp}. Режим: {job.run_mode}. Запрос: «{qv}».")
        lines.append("")
    return "\n".join(lines).strip()


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
