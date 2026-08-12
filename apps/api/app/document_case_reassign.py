"""Keep Document and DocumentChunk.case_id aligned after moves."""

from __future__ import annotations

from sqlalchemy.orm import Session

from .models import Document, DocumentChunk
from .retrieval import sync_document_chunks


def reassign_document_to_case(db: Session, document: Document, new_case_id: int) -> Document:
    """
    Move a document to another case and keep RAG/search chunks on that case.

    Callers that only set ``document.case_id`` leave ``DocumentChunk.case_id`` on the
    source case, so retrieval keeps citing the file under the old matter and the
    destination matter misses chunk hits until a full reindex.
    """
    document.case_id = int(new_case_id)
    updated = (
        db.query(DocumentChunk)
        .filter(DocumentChunk.document_id == document.id)
        .update({DocumentChunk.case_id: document.case_id}, synchronize_session="fetch")
    )
    if not updated and (document.extracted_text or "").strip():
        sync_document_chunks(db, document)
    return document
