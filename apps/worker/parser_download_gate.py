"""Decide when court-sync jobs should ingest PDFs via Parser-API."""


def should_download_via_parser(*, use_parser_api: bool, run_mode: str) -> bool:
    """Return True when Parser-API should replace Playwright for PDF download.

    Preview never downloads. Manual ``download`` and watch/nightly ``sync`` both
    ingest documents; gating only on ``download`` left automated syncs on the
    fragile browser path while search already used Parser-API.
    """
    if not use_parser_api:
        return False
    mode = (run_mode or "").strip().lower()
    return mode in ("download", "sync")
