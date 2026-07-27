"""Safe resolution of local:// document storage keys."""

from __future__ import annotations

from pathlib import Path


def resolve_local_s3_key(s3_key: str, storage_root: Path) -> Path | None:
    """Map a local:// s3_key to a path under storage_root, or None if unsafe/invalid.

    Rejects absolute paths and .. traversal so document download/delete cannot
    read or unlink files outside the storage root.
    """
    root = storage_root.resolve()
    if not isinstance(s3_key, str) or not s3_key.startswith("local://"):
        return None
    rel = s3_key.replace("local://", "", 1).strip()
    if not rel or rel.startswith(("/", "\\")):
        return None
    # Disallow empty / parent segments before resolve (defense in depth).
    parts = Path(rel).parts
    if not parts or any(p in ("", ".", "..") for p in parts):
        return None
    candidate = (root / rel).resolve()
    try:
        candidate.relative_to(root)
    except ValueError:
        return None
    return candidate
