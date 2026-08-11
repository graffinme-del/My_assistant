"""Helpers for CourtSyncJob run_mode classification."""

# Modes that download/ingest court documents (not preview-only search).
DOCUMENT_INGEST_RUN_MODES = ("download", "sync")


def is_document_ingest_run_mode(run_mode: str | None) -> bool:
    """True for modes that download/ingest court documents (not preview-only)."""
    return (run_mode or "").strip().lower() in DOCUMENT_INGEST_RUN_MODES
