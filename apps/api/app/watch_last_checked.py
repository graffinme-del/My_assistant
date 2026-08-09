"""Pure helpers for CourtWatchProfile.last_checked_at scheduling."""

from __future__ import annotations


def should_update_watch_last_checked(status: str) -> bool:
    """
    Bump CourtWatchProfile.last_checked_at only after a successful sync.

    Failed / cancelled / needs_manual_step completions must NOT advance the
    timestamp — otherwise enqueue_nightly_jobs skips the profile for a full
    check_interval_hours window and new court filings are silently missed.
    """
    return (status or "").strip() == "done"
