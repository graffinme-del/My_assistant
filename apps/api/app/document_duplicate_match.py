"""True-duplicate matching for cross-folder cleanup and auto-merge.

Filename-only matching is unsafe for court archives: generic names like
«Определение.pdf» / «Решение.pdf» appear in unrelated cases. Destructive
paths must require a stable content fingerprint from extracted text.
"""

from __future__ import annotations

import hashlib
import re
from collections import defaultdict
from typing import Iterable

# Short/empty OCR text is too weak to prove two PDFs are the same document.
MIN_CONTENT_FINGERPRINT_CHARS = 40
# A single shared generic filename (even with identical boilerplate text) must
# not collapse entire unrelated folders; require two distinct true duplicates.
MIN_SHARED_TRUE_DUPLICATES_FOR_MERGE = 2


def normalized_filename_key(filename: str) -> str:
    return re.sub(r"\s+", " ", (filename or "").strip().lower())


def content_fingerprint(
    extracted_text: str,
    *,
    min_chars: int = MIN_CONTENT_FINGERPRINT_CHARS,
) -> str | None:
    """Return a stable hash of normalized extracted text, or None if too weak."""
    norm = re.sub(r"\s+", " ", (extracted_text or "").strip().lower())
    if len(norm) < min_chars:
        return None
    digest = hashlib.sha256(norm[:8000].encode("utf-8")).hexdigest()
    return digest


def true_duplicate_group_key(
    filename: str,
    extracted_text: str,
    *,
    require_content_match: bool = True,
) -> str | None:
    """
    Group key for cross-folder duplicates.

    When require_content_match is True (default), both the normalized filename
    and a non-empty content fingerprint must be present. Filename-only keys are
    returned only when the caller explicitly opts out of content matching.
    """
    name_key = normalized_filename_key(filename)
    if len(name_key) < 4:
        return None
    if not require_content_match:
        return name_key
    fp = content_fingerprint(extracted_text)
    if not fp:
        return None
    return f"{name_key}::{fp}"


def pair_share_counts(
    case_docs: Iterable[tuple[int, str, str]],
    *,
    require_content_match: bool = True,
) -> dict[tuple[int, int], int]:
    """
    Count distinct true-duplicate keys shared by each unordered case pair.

    case_docs items are (case_id, filename, extracted_text).
    """
    groups: dict[str, set[int]] = defaultdict(set)
    for case_id, filename, extracted_text in case_docs:
        key = true_duplicate_group_key(
            filename,
            extracted_text,
            require_content_match=require_content_match,
        )
        if key is None:
            continue
        groups[key].add(case_id)

    shares: dict[tuple[int, int], int] = defaultdict(int)
    for case_ids in groups.values():
        if len(case_ids) < 2:
            continue
        ordered = sorted(case_ids)
        for i in range(len(ordered)):
            for j in range(i + 1, len(ordered)):
                shares[(ordered[i], ordered[j])] += 1
    return dict(shares)


def connected_case_components(
    case_docs: Iterable[tuple[int, str, str]],
    *,
    require_content_match: bool = True,
    min_shared_keys: int = MIN_SHARED_TRUE_DUPLICATES_FOR_MERGE,
) -> list[list[int]]:
    """
    Connected components of cases linked by enough true-duplicate file groups.

    An edge exists between A and B only when they share at least
    ``min_shared_keys`` distinct (filename + content) groups.
    """
    shares = pair_share_counts(case_docs, require_content_match=require_content_match)
    adj: dict[int, set[int]] = defaultdict(set)
    for (a, b), n in shares.items():
        if n < min_shared_keys:
            continue
        adj[a].add(b)
        adj[b].add(a)

    visited: set[int] = set()
    components: list[list[int]] = []
    for start in adj:
        if start in visited:
            continue
        stack = [start]
        visited.add(start)
        comp: list[int] = []
        while stack:
            x = stack.pop()
            comp.append(x)
            for y in adj[x]:
                if y not in visited:
                    visited.add(y)
                    stack.append(y)
        components.append(sorted(comp))
    return components
