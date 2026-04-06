from __future__ import annotations

import re

from sqlalchemy.orm import Session

from .ai_service import build_case_summary, llm_summary
from .models import Case, CaseEvent, Conversation, ConversationMessage, Document, Task
from .retrieval import (
    query_requests_strict_scope,
    retrieve_relevant_chunks,
    retrieve_relevant_documents,
    sync_document_chunks,
)


def get_or_create_conversation(db: Session, user_key: str) -> Conversation:
    conversation = db.query(Conversation).filter(Conversation.user_key == user_key).first()
    if conversation:
        return conversation
    conversation = Conversation(user_key=user_key, title="Основной чат")
    db.add(conversation)
    db.commit()
    db.refresh(conversation)
    return conversation


def _conversation_messages_for_prompt(
    db: Session, conversation: Conversation, case: Case | None
) -> list[ConversationMessage]:
    """История для промпта: по активному делу — до 40 сообщений с привязкой к делу; иначе последние 12 общих."""
    q = db.query(ConversationMessage).filter(ConversationMessage.conversation_id == conversation.id)
    if case is not None and case.case_number != "UNSORTED":
        rows = (
            q.filter(ConversationMessage.case_id == case.id)
            .order_by(ConversationMessage.created_at.desc())
            .limit(40)
            .all()
        )
    else:
        rows = q.order_by(ConversationMessage.created_at.desc()).limit(12).all()
    rows.reverse()
    return rows


def add_conversation_message(
    db: Session,
    *,
    conversation: Conversation,
    role: str,
    content: str,
    case: Case | None = None,
) -> ConversationMessage:
    message = ConversationMessage(
        conversation_id=conversation.id,
        role=role,
        case_id=case.id if case else None,
        content=content[:12000],
    )
    db.add(message)
    db.flush()
    return message


def resolve_case_with_conversation(
    *,
    conversation: Conversation,
    resolved_case: Case | None,
) -> Case | None:
    if resolved_case:
        return resolved_case
    return conversation.active_case


async def refresh_conversation_summary(db: Session, conversation: Conversation) -> None:
    recent = (
        db.query(ConversationMessage)
        .filter(ConversationMessage.conversation_id == conversation.id)
        .order_by(ConversationMessage.created_at.desc())
        .limit(10)
        .all()
    )
    if not recent:
        conversation.rolling_summary = ""
        db.add(conversation)
        db.commit()
        return
    recent.reverse()
    transcript = "\n".join(f"{msg.role}: {msg.content[:500]}" for msg in recent)
    try:
        summary = await llm_summary(
            "Сделай короткую рабочую память разговора. "
            "Верни 4-6 пунктов: активное дело, что пользователь хочет, важные ограничения, последние решения.\n\n"
            + transcript
        )
    except Exception:
        summary = "\n".join(f"- {msg.role}: {msg.content[:180]}" for msg in recent[-4:])
    conversation.rolling_summary = (summary or "")[:4000]
    db.add(conversation)
    db.commit()


def build_grounded_prompt(
    db: Session,
    *,
    conversation: Conversation,
    user_message: str,
    case: Case | None,
) -> tuple[str, list[Document], list[str]]:
    strict_scope = query_requests_strict_scope(user_message)
    if case is not None:
        chunk_exists = db.query(Document).join(Document.chunks).filter(Document.case_id == case.id).first()
        if not chunk_exists:
            docs_to_index = db.query(Document).filter(Document.case_id == case.id).order_by(Document.created_at.desc()).limit(25).all()
            for doc in docs_to_index:
                if (doc.extracted_text or "").strip():
                    sync_document_chunks(db, doc)
            db.commit()

    recent_messages = _conversation_messages_for_prompt(db, conversation, case)
    docs_with_scores = retrieve_relevant_documents(
        db,
        query=user_message,
        case=case,
        limit=6,
        min_score=2.0 if strict_scope else 0.9,
    )
    chunk_matches = retrieve_relevant_chunks(
        db,
        query=user_message,
        case=case,
        limit=6,
        min_score=2.4 if strict_scope else 1.0,
    )
    source_docs = [doc for doc, _ in docs_with_scores]

    history_block = "\n".join(f"{msg.role}: {msg.content}" for msg in recent_messages) or "история пуста"
    case_block = "дело не определено"
    if case is not None:
        events = db.query(CaseEvent).filter(CaseEvent.case_id == case.id).order_by(CaseEvent.created_at.desc()).limit(6).all()
        tasks = db.query(Task).filter(Task.case_id == case.id).order_by(Task.created_at.desc()).limit(6).all()
        case_block = build_case_summary(case, events, tasks)
        if case.case_number != "UNSORTED":
            digests = (
                db.query(CaseEvent)
                .filter(CaseEvent.case_id == case.id, CaseEvent.event_type == "case_note_digest")
                .order_by(CaseEvent.created_at.desc())
                .limit(12)
                .all()
            )
            if digests:
                digest_text = "\n---\n".join(reversed([d.body[:2000] for d in digests]))
                case_block += (
                    "\n\nСводки переписки и пересланных сообщений (по делу, последние записи):\n" + digest_text
                )

    chunk_lines: list[str] = []
    citations: list[str] = []
    for chunk, score in chunk_matches:
        doc = db.query(Document).filter(Document.id == chunk.document_id).first()
        if not doc:
            continue
        citation = f"[doc:{doc.id}] {doc.filename}"
        citations.append(citation)
        chunk_lines.append(
            f"{citation} | {chunk.page_hint} | score={score:.2f}\n{chunk.chunk_text[:900]}"
        )
    if not chunk_lines:
        chunk_lines.append(
            "Релевантных фрагментов документов не найдено. "
            "Если вопрос задан слишком широко или точных совпадений нет, нужно прямо сказать об этом."
        )

    rename_ops_hint = ""
    if re.search(
        r"переименов|название\s+папк|название\s+дела|смени\s+название|поменяй\s+название",
        user_message.lower(),
    ):
        rename_ops_hint = (
            "\n\n[Системная подсказка] Переименование папки/дела в этом приложении делается командой в чате, "
            "например: «переименуй папку «старое» в «новое»» или «переименуй папку Старое в Новое». "
            "Не утверждайте, что это возможно только вручную в интерфейсе — такая команда поддерживается."
        )

    prompt = (
        "Ты личный помощник по судебным делам. "
        "Отвечай по-русски, уверенно, по делу и только на основе найденного контекста. "
        "Если данных недостаточно, скажи это прямо. Не выдумывай факты. "
        "Если используешь сведения из документов, ссылайся на них в формате [doc:ID]. "
        "Если вопрос операционный, предложи конкретный следующий шаг. "
        "Не подтягивай соседний контекст, если связь слабая. "
        "Не повторяй одни и те же мысли разными словами. "
        "Если пользователь просит список, перечень, реестр или собрать все файлы по делу, не рассуждай общими фразами: "
        "верни именно список документов или прямо скажи, что список неполный. "
        "Если спрашивают «что по делу», «какой статус», «что с сделкой» — опирайся на сводки переписки, последние сообщения "
        "и документы; сведи в одну связную картину.\n\n"
        f"Режим отбора: {'строгий, только текущее дело и только сильные совпадения' if strict_scope else 'обычный, внутри активного дела'}.\n\n"
        f"Рабочая память беседы:\n{conversation.rolling_summary or 'нет'}\n\n"
        f"Активное дело:\n{case_block}\n\n"
        f"Последние сообщения:\n{history_block}\n\n"
        f"Релевантные фрагменты документов:\n" + "\n\n".join(chunk_lines) + "\n\n"
        f"Текущее сообщение пользователя:\n{user_message}"
        + rename_ops_hint
    )
    return prompt, source_docs, citations
