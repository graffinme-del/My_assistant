"""Hard-delete documents with commit-before-unlink ordering.

Filesystem unlinks must happen only after a successful DB commit. Otherwise a
failed/rolled-back transaction leaves Document rows pointing at missing files.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from sqlalchemy.orm import Session

from .models import CaseEvent, Document

ResolveLocalPath = Callable[[Document], Path | None]


def unlink_local_path(path: Path | None) -> None:
    if path is None or not path.is_file():
        return
    try:
        path.unlink()
    except OSError:
        pass


def delete_documents_hard(
    db: Session,
    docs: list[Document],
    *,
    resolve_local_path: ResolveLocalPath,
) -> list[str]:
    """Delete Document rows (chunks CASCADE), then unlink local files after commit."""
    removed: list[str] = []
    paths_to_unlink: list[Path] = []
    for doc in docs:
        doc_id, case_id, fn = doc.id, doc.case_id, doc.filename
        path = resolve_local_path(doc)
        if path is not None and path.is_file():
            paths_to_unlink.append(path)
        db.add(
            CaseEvent(
                case_id=case_id,
                event_type="document_deleted",
                body=f"Удалён документ [{doc_id}]: {fn}",
            )
        )
        db.delete(doc)
        removed.append(f"[{doc_id}] {fn}")
    db.commit()
    for path in paths_to_unlink:
        unlink_local_path(path)
    return removed
