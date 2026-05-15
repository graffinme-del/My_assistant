from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.court_sync_service import cancel_active_court_sync_jobs, get_court_sync_job_for_user
from app.db import Base
from app.models import CourtSyncJob


def _session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)()


def _job(db, *, requested_by: str, status: str = "pending", report_text: str = "") -> CourtSyncJob:
    job = CourtSyncJob(
        requested_by=requested_by,
        query_type="moy_arbitr_case_number",
        query_value=f"A40-{len(requested_by)}/2025",
        run_mode="download",
        status=status,
        step="queued",
        report_text=report_text,
    )
    db.add(job)
    db.commit()
    db.refresh(job)
    return job


def test_member_cannot_load_owner_court_sync_job_report():
    db = _session()
    owner_job = _job(db, requested_by="owner", status="done", report_text="owner secret report")
    member_job = _job(db, requested_by="member", status="done", report_text="member report")

    assert get_court_sync_job_for_user(db, owner_job.id, "member") is None
    assert get_court_sync_job_for_user(db, member_job.id, "member").id == member_job.id
    assert get_court_sync_job_for_user(db, member_job.id, "owner").id == member_job.id


def test_member_cancel_is_limited_to_member_jobs():
    db = _session()
    owner_job = _job(db, requested_by="owner")
    member_job = _job(db, requested_by="member")

    stats = cancel_active_court_sync_jobs(db, requested_by="member")
    db.refresh(owner_job)
    db.refresh(member_job)

    assert stats == {"cancelled": 1}
    assert owner_job.status == "pending"
    assert member_job.status == "cancelled"


def test_owner_cancel_remains_global():
    db = _session()
    owner_job = _job(db, requested_by="owner")
    member_job = _job(db, requested_by="member")

    stats = cancel_active_court_sync_jobs(db)
    db.refresh(owner_job)
    db.refresh(member_job)

    assert stats == {"cancelled": 2}
    assert owner_job.status == "cancelled"
    assert member_job.status == "cancelled"
