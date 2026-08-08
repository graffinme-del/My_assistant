"""Helpers for choosing which local case receives ingested court documents."""

from __future__ import annotations


def pick_case_number_for_filing(case_data_number: str | None, page_hint: str | None) -> str | None:
    """Prefer the search-result case number over the first HTML regex match.

    KAD card HTML often cites related/joined matters before the primary number;
    filing from that first match mis-archives documents into the wrong folder.
    """
    num = (case_data_number or "").strip()
    if num:
        return num
    hint = (page_hint or "").strip()
    return hint or None
