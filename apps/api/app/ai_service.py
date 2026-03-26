from __future__ import annotations

import re
from datetime import date
from pathlib import Path

import httpx
from pypdf import PdfReader
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


def extract_document_text(file_path: Path, filename: str) -> str:
    suffix = filename.lower().split(".")[-1] if "." in filename else ""
    if suffix in {"txt", "md"}:
        return file_path.read_text(encoding="utf-8", errors="ignore")
    if suffix == "pdf":
        reader = PdfReader(str(file_path))
        chunks: list[str] = []
        for page in reader.pages[:30]:
            chunks.append(page.extract_text() or "")
        return "\n".join(chunks).strip()
    return ""


def classify_document(filename: str, text: str) -> tuple[str, float]:
    probe = f"{filename}\n{text}".lower()
    mapping = [
        ("court_act", ["определение", "решение суда", "постановление"]),
        ("power_of_attorney", ["доверенность", "power of attorney"]),
        ("claim", ["исковое заявление", "иск", "claim"]),
        ("review", ["отзыв", "возражения"]),
        ("complaint", ["жалоба", "апелляция", "кассация"]),
        ("evidence", ["cmr", "доказательств", "приложени"]),
    ]
    for category, keys in mapping:
        if any(key in probe for key in keys):
            return category, 0.85
    return "other", 0.55


def _normalize(value: str) -> str:
    return re.sub(r"[^a-zа-я0-9]", "", value.lower())


def match_case(db: Session, filename: str, text: str, preferred_case_id: int | None = None) -> tuple[Case | None, float]:
    if preferred_case_id:
        case = db.query(Case).filter(Case.id == preferred_case_id).first()
        if case:
            return case, 0.9

    cases = db.query(Case).all()
    if not cases:
        return None, 0.0

    corpus = _normalize(f"{filename}\n{text}")[:30000]
    for case in cases:
        if _normalize(case.case_number) in corpus and len(_normalize(case.case_number)) > 4:
            return case, 0.95

    best: Case | None = None
    best_score = 0.0
    for case in cases:
        score = 0.0
        title_token = _normalize(case.title)
        court_token = _normalize(case.court_name)
        if title_token and title_token[:12] in corpus:
            score += 0.35
        if court_token and court_token[:12] in corpus:
            score += 0.25
        if score > best_score:
            best_score = score
            best = case
    if best:
        return best, max(0.6, best_score)
    return cases[0], 0.45
