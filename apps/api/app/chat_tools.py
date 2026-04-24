"""
Единый слой tool-calling для чата: модель выбирает действие по смыслу формулировки.

При включённом CHAT_TOOLS_ROUTER сообщение (до ~8k символов) может пройти один вызов LLM
с набором инструментов; regex-ветки в main.py остаются запасным путём, если инструмент не выбран.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from .ai_service import llm_chat_with_tool_choice
from .config import settings
from .court_kad_search import looks_like_court_download_count_question, looks_like_kad_downloaded_documents_list
from .court_sync_service import format_kad_downloaded_documents_list, format_recent_download_jobs_status
from .ru_date_range import describe_calendar_period_ru, parse_calendar_period_ru
from .models import Case, Conversation, ConversationMessage, Document

# OpenAI-compatible tools (function calling)
CHAT_TOOLS: list[dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "search_documents",
            "description": (
                "Пользователь ищет уже загруженные в приложение файлы (PDF и др.) по смыслу: ФИО, название, "
                "фрагмент текста, организация и т.д. Поиск идёт по имени файла и распознанному тексту документов. "
                "Вызывай при любой формулировке вроде «найди», «где документ», «покажи файлы с», "
                "«есть ли что-то про …», в том числе без явных слов «во всех папках» — scope выбери сам по контексту. "
                "Не вызывай для запросов к сайту kad.arbitr.ru / картотеке судов. "
                "Не вызывай, если пользователь просит сохранить текст самого сообщения в папку как заметку. "
                "В queries передай 1–10 коротких фраз без служебных слов («найди», «документы», «содержащие»): "
                "разные формы ФИО или написания — отдельными элементами (логика ИЛИ между элементами)."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "scope": {
                        "type": "string",
                        "enum": ["all_folders", "active_case"],
                        "description": (
                            "all_folders — искать во всех папках; active_case — только в текущей открытой папке чата."
                        ),
                    },
                    "queries": {
                        "type": "array",
                        "items": {"type": "string"},
                        "minItems": 1,
                        "maxItems": 10,
                        "description": "Поисковые фразы; достаточно совпадения любой фразы с файлом или текстом PDF.",
                    },
                },
                "required": ["scope", "queries"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "delete_documents_and_folder",
            "description": (
                "Удалить конкретные загруженные документы по id (в чате они помечены как [123]) и при необходимости "
                "сразу удалить папку/дело, в котором они лежали (остальные файлы этого дела уйдут в неразобранное). "
                "Используй, когда пользователь говорит «удали этот документ и папку», «убери файл и само дело» "
                "или ссылается на последний найденный документ. "
                "document_ids возьми из последних сообщений ассистента в контексте (строки с [id]). "
                "Не вызывай, если нужно удалить только папку без привязки к конкретным id — тогда delete_case_folder."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "document_ids": {
                        "type": "array",
                        "items": {"type": "integer"},
                        "minItems": 1,
                        "maxItems": 40,
                        "description": "Id документов из ответов ассистента, например 213 из «[213] имя.pdf».",
                    },
                    "also_delete_containing_folder": {
                        "type": "boolean",
                        "description": "True, если нужно удалить дело/папку целиком после удаления перечисленных файлов.",
                    },
                },
                "required": ["document_ids", "also_delete_containing_folder"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "delete_all_empty_folders",
            "description": (
                "Удалить все «пустые» папки (дела), в которых нет ни одного загруженного документа/файла. "
                "Папку «Неразобранное» не трогать. Типичные формулировки: «удали пустые папки», «убери дела без документов», "
                "«очисти папки где нет файлов». Не вызывай, если нужно удалить одну конкретную папку по названию."
            ),
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "delete_case_folder",
            "description": (
                "Пользователь хочет удалить из приложения целиком папку/дело (карточку дела). "
                "Содержимое уходит в «Неразобранное». Не вызывай для удаления отдельных файлов («удали документ …»)."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "case_hint": {
                        "type": "string",
                        "description": (
                            "Номер дела или название папки из сообщения; если «эта папка» — используй активную из контекста."
                        ),
                    },
                },
                "required": ["case_hint"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_duplicate_files_across_folders",
            "description": (
                "Показать файлы с одинаковым именем, которые лежат в разных папках (делах). "
                "Формулировки: «есть ли дубликаты», «одинаковые документы в папках», «проверь повторы файлов»."
            ),
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "cleanup_duplicate_files_keep_best_copy",
            "description": (
                "Удалить лишние копии одного и того же **имени файла** в разных папках: остаётся одна копия. "
                "По умолчанию модель смотрит **распознанный текст** PDF и контекст папки (смысл документа); "
                "иначе — эвристика по номеру дела в имени файла. Можно указать предпочтительную папку. "
                "Формулировки: «удали дубликаты», «убери повторы», «оставь по одному». "
                "Не вызывай для сравнения двух файлов с разными именами."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "dry_run_only": {
                        "type": "boolean",
                        "description": "True — только план, без удаления. False — выполнить удаление лишних копий.",
                    },
                    "preferred_folder_title": {
                        "type": "string",
                        "description": "Если пользователь назвал папку, где оставить копии — подстрока названия (необязательно).",
                    },
                },
                "required": ["dry_run_only"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "merge_folders_sharing_duplicate_filenames",
            "description": (
                "Объединить папки автоматически: если два дела содержат файл с одним и тем же именем, "
                "слить такие группы в одну папку (целевую выбирает сервер: приоритет делу с «настоящим» номером арбитража). "
                "Не вызывай, если пользователь явно назвал две конкретные папки через «и» — тогда достаточно обычного объединения вручную."
            ),
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "cross_folder_matter_narrative",
            "description": (
                "Пользователь просит связную хронологическую историю по теме или лицу **через все папки/дела**: "
                "например полный расклад банкротства с разными номерами процессов, «печальная история», "
                "от первого документа до последнего, таймлайн по всему архиву. "
                "НЕ для простого списка «найди файлы с фамилией» без запроса повествования."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "user_request": {
                        "type": "string",
                        "description": "Дословно или кратко переформулированный запрос пользователя для поиска и тона ответа.",
                    },
                },
                "required": ["user_request"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "propose_semantic_case_clusters",
            "description": (
                "Смысловой анализ всех папок: найти группы дел, относящихся к одной реальной истории "
                "(например банкротство и множество исков с разными номерами; связанные споры). "
                "Даёт черновик групп и ждёт подтверждения пользователя перед объединением. "
                "Формулировки: «проанализируй папки по смыслу», «что объединить по сути», «одно дело разные номера», "
                "«кластеризация дел». Не вызывай для простого «объедини папку А и папку Б» без запроса анализа всего набора."
            ),
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "semantic_consolidate_into_case",
            "description": (
                "Отсортировать и собрать документы **из всех других папок** в одну целевую **по смыслу текста PDF и номерам дел**: "
                "например «отсортируй документы», «оставь только относящиеся к делу …», «по контексту в папку …». "
                "По умолчанию перенос выполняется сразу; если пользователь просит «только список» или «без переноса» — только предпросмотр и подтверждение. "
                "Не вызывай для простого переноса всех файлов из текущей папки без анализа смысла."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "instruction": {
                        "type": "string",
                        "description": "Запрос пользователя целиком: куда собрать (в папку … / по делу …), кавычки не обязательны; контекст сортировки.",
                    },
                },
                "required": ["instruction"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "collect_documents_into_folder",
            "description": (
                "Пользователь хочет собрать документы в новую «папку» (в продукте это отдельное дело/case). "
                "Типично: перенести все документы из текущего открытого дела в новое дело с заданным названием. "
                "Не вызывай для сохранения текста сообщения как заметки в папке. "
                "Если название новой папки не сказано — передай пустую строку в new_folder_title."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "new_folder_title": {
                        "type": "string",
                        "description": "Название новой папки/дела (можно без кавычек). Пусто, если не названо — сервер возьмёт из текста.",
                    },
                    "scope": {
                        "type": "string",
                        "enum": ["from_active_case", "unspecified"],
                        "description": (
                            "from_active_case — из текущего активного дела; unspecified — неясно (сервер извлечёт из текста)."
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
                "Общий ход фоновой загрузки из kad.arbitr.ru: «как там скачивание», «статус загрузки», задача №N. "
                "НЕ для вопроса «сколько файлов скачали». НЕ для списка имён скачанных PDF — это kad_downloaded_files_list."
            ),
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "kad_downloaded_files_list",
            "description": (
                "Список конкретных файлов, сохранённых из КАД: имена PDF, «что скачалось», перечень после загрузки."
            ),
            "parameters": {"type": "object", "properties": {}},
        },
    },
]


def _router_system_prompt(db: Session, conversation: Conversation) -> str:
    if not conversation.active_case_id:
        active = "не выбрана (пользователь не открыл папку слева)."
    else:
        c = db.query(Case).filter(Case.id == conversation.active_case_id).first()
        if not c:
            active = "не выбрана."
        else:
            active = f"«{c.title}», номер {c.case_number} (id={c.id})."
    rows = db.query(Case).order_by(Case.id.desc()).limit(48).all()
    lines = [f"- «{c.title}» — {c.case_number}" for c in rows]
    catalog = "\n".join(lines) if lines else "(папок нет)"
    hist_rows = (
        db.query(ConversationMessage)
        .filter(ConversationMessage.conversation_id == conversation.id)
        .order_by(ConversationMessage.created_at.desc())
        .limit(10)
        .all()
    )
    hist_rows.reverse()
    transcript = "\n".join(
        f"{r.role}: {(r.content or '')[:3500]}" for r in hist_rows
    )
    if not transcript.strip():
        transcript = "(истории сообщений пока нет)"
    return (
        "Ты маршрутизатор намерений для ассистента по судебным материалам. "
        "У пользователя «папки» = дела (cases). "
        "Вызови ровно один инструмент, только если запрос явно требует этого действия в приложении. "
        "Если пользователь просто общается, просит объяснить или обобщить без поиска по файлам, удаления папки, "
        "переноса в новую папку или работы с КАД — не вызывай инструменты.\n"
        "Ссылкам «этот документ», «найденный файл» соответствуют номера в квадратных скобках [213] в последних сообщениях assistant.\n\n"
        f"Активная папка в чате: {active}\n"
        f"Известные папки (кратко):\n{catalog}\n\n"
        f"Последние реплики (новее внизу):\n{transcript}\n"
    )


async def run_chat_tools_router(
    db: Session,
    conversation: Conversation,
    user_message: str,
    *,
    user_role: str,
    preferred_case_number: str | None = None,
) -> tuple[str, Case, str] | None:
    """
    Один проход LLM с tools. Если модель выбрала инструмент — выполняет и возвращает (reply, case, mode).
    Иначе None — дальше работают эвристики в main.py.
    """
    if not settings.chat_tools_router_enabled or not settings.openai_api_key.strip():
        return None
    if len(user_message) > 8000:
        return None
    if looks_like_kad_downloaded_documents_list(user_message) or looks_like_court_download_count_question(user_message):
        return None

    system = _router_system_prompt(db, conversation)
    _content, tool_calls = await llm_chat_with_tool_choice(
        system=system,
        user_message=user_message,
        tools=CHAT_TOOLS,
        timeout=55.0,
    )

    if not tool_calls:
        return None

    call = tool_calls[0]
    name = call.get("name") or ""
    args = call.get("arguments") or {}

    if name == "search_documents":
        from .main import (
            get_or_create_unsorted_case,
            resolve_case_for_conversation,
            search_documents_global_with_hints,
            search_documents_union_queries,
        )

        scope = str(args.get("scope") or "").strip()
        raw_q = args.get("queries") or []
        queries = [str(x).strip() for x in raw_q if str(x).strip()]
        queries = queries[:10]
        if not queries:
            return None
        if scope == "all_folders":
            reply = search_documents_global_with_hints(db, queries, limit=45)
            return reply, get_or_create_unsorted_case(db), "chat-tools-search-global"
        if scope == "active_case":
            _conv, command_case = resolve_case_for_conversation(
                db,
                user_message,
                user_role=user_role,
                preferred_case_number=preferred_case_number,
            )
            command_docs = (
                db.query(Document)
                .filter(Document.case_id == command_case.id)
                .order_by(Document.created_at.desc())
                .all()
            )
            reply = search_documents_union_queries(command_case, command_docs, queries)
            return reply, command_case, "chat-tools-search-case"
        return None

    if name == "delete_all_empty_folders":
        from .main import get_or_create_unsorted_case, handle_delete_all_empty_case_folders_chat

        reply_text, out_case = handle_delete_all_empty_case_folders_chat(db, conversation)
        return reply_text, out_case or get_or_create_unsorted_case(db), "chat-tools-delete-empty-folders"

    if name == "delete_documents_and_folder":
        from .main import execute_delete_documents_and_optional_folder, get_or_create_unsorted_case

        raw_ids = args.get("document_ids") or []
        try:
            doc_ids = [int(x) for x in raw_ids]
        except (TypeError, ValueError):
            return None
        also = bool(args.get("also_delete_containing_folder"))
        if not doc_ids:
            return None
        reply_text, out_case = execute_delete_documents_and_optional_folder(
            db,
            document_ids=doc_ids,
            also_delete_containing_folder=also,
            user_message=user_message,
        )
        if out_case is None:
            out_case = get_or_create_unsorted_case(db)
        return reply_text, out_case, "chat-tools-delete-docs-and-folder"

    if name == "delete_case_folder":
        from .main import get_or_create_unsorted_case, handle_delete_case_folder_chat

        hint = str(args.get("case_hint") or "").strip()
        if len(hint) < 2:
            return None
        reply_text, del_case = handle_delete_case_folder_chat(db, user_message, hint_override=hint)
        case_for_reply = del_case if del_case is not None else get_or_create_unsorted_case(db)
        return reply_text, case_for_reply, "chat-tools-delete-folder"

    if name == "kad_download_jobs_status":
        dr = parse_calendar_period_ru(user_message)
        pl = describe_calendar_period_ru(user_message) if dr else None
        reply = format_recent_download_jobs_status(db, date_range=dr, period_label=pl)
        from .main import get_or_create_unsorted_case

        return reply, get_or_create_unsorted_case(db), "chat-tools-kad-status"

    if name == "kad_downloaded_files_list":
        dr = parse_calendar_period_ru(user_message)
        pl = describe_calendar_period_ru(user_message) if dr else None
        reply = format_kad_downloaded_documents_list(db, date_range=dr, period_label=pl)
        from .main import get_or_create_unsorted_case

        return reply, get_or_create_unsorted_case(db), "chat-tools-kad-files-list"

    if name == "list_duplicate_files_across_folders":
        from .main import format_duplicate_documents_across_cases_report, get_or_create_unsorted_case

        reply = format_duplicate_documents_across_cases_report(db)
        return reply, get_or_create_unsorted_case(db), "chat-tools-list-duplicates"

    if name == "cleanup_duplicate_files_keep_best_copy":
        from .duplicate_cleanup import handle_cross_folder_duplicate_cleanup_chat
        from .main import get_or_create_unsorted_case

        dry = bool(args.get("dry_run_only"))
        pref = str(args.get("preferred_folder_title") or "").strip()
        parts = []
        if dry:
            parts.append("Покажи план удаления дубликатов без удаления.")
        else:
            parts.append("Удали дубликаты между папками, оставь по одному файлу.")
        if pref:
            parts.append(f'Приоритет папки «{pref}».')
        parts.append(user_message.strip())
        reply_text, out_case = await handle_cross_folder_duplicate_cleanup_chat(
            db, " ".join(p for p in parts if p)
        )
        return reply_text, out_case or get_or_create_unsorted_case(db), "chat-tools-dup-cleanup"

    if name == "merge_folders_sharing_duplicate_filenames":
        from .main import get_or_create_unsorted_case, handle_merge_cases_linked_by_duplicate_filenames

        reply_text, target_case = handle_merge_cases_linked_by_duplicate_filenames(db)
        return reply_text, target_case or get_or_create_unsorted_case(db), "chat-tools-merge-duplicate-folders"

    if name == "propose_semantic_case_clusters":
        from .main import conversation_user_key, get_or_create_unsorted_case
        from .matter_intelligence import preview_semantic_workspace_clusters

        reply_text, _ = await preview_semantic_workspace_clusters(db, conversation_user_key(user_role))
        return reply_text, get_or_create_unsorted_case(db), "chat-tools-semantic-clusters-preview"

    if name == "semantic_consolidate_into_case":
        from .main import get_or_create_unsorted_case
        from .semantic_matter_collect import preview_semantic_collect_into_case

        blob = str(args.get("instruction") or user_message or "").strip()
        if len(blob) < 8:
            blob = user_message
        reply_text, target_case = await preview_semantic_collect_into_case(db, conversation, blob)
        return reply_text, target_case or get_or_create_unsorted_case(db), "chat-tools-semantic-consolidate"

    if name == "cross_folder_matter_narrative":
        from .main import get_or_create_unsorted_case
        from .matter_narrative import build_cross_folder_matter_narrative

        u = str(args.get("user_request") or user_message or "").strip()
        if len(u) < 8:
            u = user_message
        reply_text = await build_cross_folder_matter_narrative(db, u)
        return reply_text, get_or_create_unsorted_case(db), "chat-tools-cross-folder-narrative"

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
        reply, target_case = preview_move_all_documents_from_active_case_to_folder(db, conversation, title)
        case_for_reply = target_case if target_case is not None else get_or_create_unsorted_case(db)
        return reply, case_for_reply, "chat-tools-collect-folder"

    return None
