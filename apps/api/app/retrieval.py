from __future__ import annotations

import re
from collections import Counter

from sqlalchemy.orm import Session

from .models import Case, Document, DocumentChunk


def normalize_search_text(value: str) -> str:
    return re.sub(r"\s+", " ", (value or "").strip().lower())


def tokenize_query(value: str) -> list[str]:
    return [
        token
        for token in re.findall(r"[a-zа-я0-9]{3,}", normalize_search_text(value))
        if len(token) >= 3
    ]


def chunk_document_text(text: str, *, chunk_size: int = 1400, overlap: int = 220) -> list[str]:
    normalized = re.sub(r"\s+", " ", (text or "").strip())
    if not normalized:
        return []
    if len(normalized) <= chunk_size:
        return [normalized]
    chunks: list[str] = []
    start = 0
    while start < len(normalized):
        end = min(len(normalized), start + chunk_size)
        chunk = normalized[start:end].strip()
        if chunk:
            chunks.append(chunk)
        if end >= len(normalized):
            break
        start = max(end - overlap, start + 1)
    return chunks


def sync_document_chunks(db: Session, document: Document) -> list[DocumentChunk]:
    db.query(DocumentChunk).filter(DocumentChunk.document_id == document.id).delete()
    chunks: list[DocumentChunk] = []
    text_chunks = chunk_document_text(document.extracted_text or "")
    for idx, chunk_text in enumerate(text_chunks):
        chunk = DocumentChunk(
            document_id=document.id,
            case_id=document.case_id,
            chunk_index=idx,
            page_hint=f"chunk-{idx + 1}",
            chunk_text=chunk_text,
            search_text=normalize_search_text(f"{document.filename}\n{chunk_text}"),
            score=0.0,
        )
        db.add(chunk)
        chunks.append(chunk)
    db.flush()
    return chunks


def _score_text(query_tokens: list[str], haystack: str) -> float:
    if not query_tokens or not haystack:
        return 0.0
    counts = Counter(tokenize_query(haystack))
    score = 0.0
    for token in query_tokens:
        if token in counts:
            score += 1.0 + min(counts[token], 4) * 0.35
    return score


def retrieve_relevant_chunks(
    db: Session,
    *,
    query: str,
    case: Case | None = None,
    limit: int = 6,
) -> list[tuple[DocumentChunk, float]]:
    query_tokens = tokenize_query(query)
    if not query_tokens:
        return []
    q = db.query(DocumentChunk)
    if case is not None:
        q = q.filter(DocumentChunk.case_id == case.id)
    chunks = q.order_by(DocumentChunk.created_at.desc()).limit(800).all()
    ranked: list[tuple[DocumentChunk, float]] = []
    for chunk in chunks:
        score = _score_text(query_tokens, chunk.search_text)
        if score <= 0:
            continue
        ranked.append((chunk, score))
    ranked.sort(key=lambda item: item[1], reverse=True)
    return ranked[:limit]


def retrieve_relevant_documents(
    db: Session,
    *,
    query: str,
    case: Case | None = None,
    limit: int = 8,
) -> list[tuple[Document, float]]:
    query_tokens = tokenize_query(query)
    if not query_tokens:
        return []
    q = db.query(Document)
    if case is not None:
        q = q.filter(Document.case_id == case.id)
    docs = q.order_by(Document.created_at.desc()).limit(300).all()
    ranked: list[tuple[Document, float]] = []
    for doc in docs:
        haystack = f"{doc.filename}\n{doc.category}\n{doc.extracted_text[:6000]}"
        score = _score_text(query_tokens, haystack)
        if score <= 0:
            continue
        ranked.append((doc, score))
    ranked.sort(key=lambda item: item[1], reverse=True)
    return ranked[:limit]
