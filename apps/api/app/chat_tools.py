"""
Единый слой tool-calling для чата: схемы операций + маршрутизация через LLM.

Регулярные ветки в main.py остаются запасным путём; при включённом роутере
модель может выбрать инструмент по смыслу формулировки.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from .ai_service import llm_chat_with_tool_choice
from .config import settings
from .court_sync_service import format_recent_download_jobs_status
from .models import Case, Conversation

# OpenAI-compatible tools (function calling)
CHAT_TOOLS: list[dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "collect_documents_into_folder",
            "description": (
                "Пользователь хочет собрать документы в новую «папку» (в продукте это отдельное дело/case). "
                "Типично: перенести все документы из текущего открытого дела в новое дело с заданным названием. "
                "Вызывай, если явно есть намерение перенести/собрать файлы в новую папку или новое дело. "
                "Если название новой папки не сказано — передай пустую строку в new_folder_title."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "new_folder_title": {
                        "type": "string",
                        "description": "Название новой папки/дела, как сформулировал пользователь. Пусто, если не названо.",
                    },
                    "scope": {
                        "type": "string",
                        "enum": ["from_active_case", "unspecified"],
                        "description": (
                            "from_active_case — перенести документы из текущего активного дела в чате; "
                            "unspecified — если неясно (сервер попытается извлечь название из текста)."
                        ),
                    },
                },
                "required": ["scope"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "kad_download_jobs_status",
            "description": (
                "Пользователь спрашивает статус фоновых задач скачивания документов с kad.arbitr.ru (КАД), "
                "воркер, «ты скачал», «статус скачивания». Не для списка файлов внутри дела."
            ),
            "parameters": {"type": "object", "properties": {}},
        },
    },
]


def _might_use_chat_tools(text: str) -> bool:
    """Эвристика: не дергать LLM на каждое сообщение."""
    if len(text) > 2500:
        return False
    t = text.lower()
    return any(
        k in t
        for k in (
            "папк",
            "собери",
            "соберите",
            "перенеси",
            "отдельную папку",
            "статус скачивания",
            "статус загрузки",
            "скачал",
            "загрузил",
            "воркер",
            "фонов",
            "kad.arbitr",
            "арбитражн",
        )
    )


def _system_prompt_with_context(db: Session, conversation: Conversation) -> str:
    if not conversation.active_case_id:
        ctx = "Активное дело в чате не выбрано."
    else:
        c = db.query(Case).filter(Case.id == conversation.active_case_id).first()
        if not c:
            ctx = "Активное дело в чате не выбрано."
        else:
            ctx = f"Активное дело: id={c.id}, название «{c.title}», номер {c.case_number}."
    return (
        "Ты классификатор намерений для юридического ассистента. "
        "Вызывай не более одного инструмента только если запрос явно соответствует его описанию. "
        "Если пользователь просит анализ, сводку, список файлов без переноса в новую папку, общий разговор — "
        "не вызывай инструменты.\n\n"
        f"Контекст: {ctx}"
    )


async def run_chat_tools_router(
    db: Session,
    conversation: Conversation,
    user_message: str,
    *,
    user_role: str,
) -> tuple[str, Case, str] | None:
    """
    Если модель выбрала инструмент — выполняет его и возвращает (reply, case, mode).
    Если модель не выбрала инструмент — возвращает None (дальше работают regex-ветки).
    """
    _ = user_role
    if not settings.chat_tools_router_enabled or not settings.openai_api_key.strip():
        return None
    if not _might_use_chat_tools(user_message):
        return None

    system = _system_prompt_with_context(db, conversation)
    _content, tool_calls = await llm_chat_with_tool_choice(
        system=system,
        user_message=user_message,
        tools=CHAT_TOOLS,
        timeout=50.0,
    )

    if not tool_calls:
        return None

    call = tool_calls[0]
    name = call.get("name") or ""
    args = call.get("arguments") or {}

    if name == "kad_download_jobs_status":
        reply = format_recent_download_jobs_status(db)
        from .main import get_or_create_unsorted_case

        return reply, get_or_create_unsorted_case(db), "chat-tools-kad-status"

    if name == "collect_documents_into_folder":
        from .main import (
            get_or_create_unsorted_case,
            parse_collect_folder_title,
            preview_move_all_documents_from_active_case_to_folder,
            save_folder_request_context,
        )

        title = (args.get("new_folder_title") or "").strip()
        if not title:
            title = parse_collect_folder_title(user_message)
        save_folder_request_context(db, title or "")
        reply = preview_move_all_documents_from_active_case_to_folder(db, conversation, title)
        return reply, get_or_create_unsorted_case(db), "chat-tools-collect-folder"

    return None
