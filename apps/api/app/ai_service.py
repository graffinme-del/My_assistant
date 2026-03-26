from __future__ import annotations

import re
from datetime import date

import httpx
from sqlalchemy.orm import Session

from .config import settings
from .models import Case, CaseEvent, Task


def _extract_date(text: str) -> date | None:
    match = re.search(r"(\d{1,2})\.(\d{1,2})(?:\.(\d{2,4}))?", text)
    if not match:
        return None
    day = int(match.group(1))
    month = int(match.group(2))
    year_raw = match.group(3)
    year = int(year_raw) if year_raw else date.today().year
    if year < 100:
        year += 2000
    try:
        return date(year, month, day)
    except ValueError:
        return None


def build_case_summary(case: Case, events: list[CaseEvent], tasks: list[Task]) -> str:
    open_tasks = [t for t in tasks if t.status != "done"]
    latest_events = sorted(events, key=lambda e: e.created_at, reverse=True)[:3]
    events_block = "\n".join([f"- {e.event_type}: {e.body[:160]}" for e in latest_events]) or "- нет"
    tasks_block = "\n".join([f"- {t.title} ({t.priority})" for t in open_tasks[:5]]) or "- нет"
    return (
        f"Дело: {case.title}\n"
        f"Статус: {case.status}, стадия: {case.stage}\n"
        f"Следующее заседание: {case.next_hearing_date or 'не указано'}\n"
        f"Последние события:\n{events_block}\n"
        f"Открытые задачи:\n{tasks_block}"
    )


async def llm_summary(prompt: str) -> str:
    if not settings.openai_api_key:
        return "LLM ключ не настроен. Возвращаю локальную сводку без внешнего ИИ."

    headers = {
        "Authorization": f"Bearer {settings.openai_api_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": settings.openai_model,
        "input": (
            "Ты личный помощник по судебным делам. Дай короткую сводку в 5-8 строках. "
            "Только факты из входных данных.\n\n"
            f"{prompt}"
        ),
    }
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(
            "https://api.openai.com/v1/responses",
            headers=headers,
            json=payload,
        )
        resp.raise_for_status()
        data = resp.json()
        return data.get("output_text", "").strip() or "Не удалось получить ответ модели."


def parse_hearing_note(db: Session, case: Case, text: str) -> tuple[CaseEvent, list[Task], date | None]:
    extracted_date = _extract_date(text)
    if extracted_date:
        case.next_hearing_date = extracted_date

    event = CaseEvent(case_id=case.id, event_type="hearing_note", body=text)
    db.add(event)

    tasks: list[Task] = []
    for line in text.splitlines():
        normalized = line.strip("- ").strip()
        if not normalized:
            continue
        if any(token in normalized.lower() for token in ["подготов", "приобщ", "направ", "предостав"]):
            task = Task(
                case_id=case.id,
                title=normalized[:200],
                description="Создано автоматически из сообщения после заседания",
                priority="high",
                status="open",
            )
            db.add(task)
            tasks.append(task)

    db.commit()
    db.refresh(event)
    for task in tasks:
        db.refresh(task)

    return event, tasks, extracted_date
