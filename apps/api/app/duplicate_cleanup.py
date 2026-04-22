"""Удаление межпапочных дубликатов по совпадению имени файла: остаётся одна «логичная» копия."""

from __future__ import annotations

import re
from collections import defaultdict

from sqlalchemy.orm import Session

from .ai_service import extract_case_number
from .case_number import arbitr_case_number_lookup_keys, normalize_arbitr_case_number
from .models import Case, CaseEvent, Document


def _normalized_filename_key(filename: str) -> str:
    return re.sub(r"\s+", " ", (filename or "").strip().lower())


def gather_cross_folder_duplicate_groups(db: Session) -> dict[str, list[tuple[Document, Case]]]:
    groups: dict[str, list[tuple[Document, Case]]] = defaultdict(list)
    for d in db.query(Document).all():
        c = db.query(Case).filter(Case.id == d.case_id).first()
        if not c:
            continue
        key = _normalized_filename_key(d.filename)
        if len(key) < 4:
            continue
        groups[key].append((d, c))
    return {k: v for k, v in groups.items() if len({cc.id for _, cc in v}) >= 2}


def folder_preference_hint_from_text(text: str) -> str | None:
    for a, b in re.findall(r'"([^"]+)"|«([^»]+)»', text or ""):
        s = (a or b).strip()
        if len(s) >= 2:
            return s
    return None


def _keep_score(
    doc: Document,
    case: Case,
    db: Session,
    *,
    prefer_folder_substr: str | None,
) -> float:
    score = 0.0
    cn = (case.case_number or "").upper()
    title_l = (case.title or "").lower()

    if cn == "UNSORTED":
        score -= 5000.0
    elif "UNDEF" in cn:
        score -= 800.0
    elif cn.startswith("TAG-"):
        score -= 350.0

    num_fn = extract_case_number(doc.filename)
    if num_fn:
        keys = arbitr_case_number_lookup_keys(num_fn)
        cnorm = normalize_arbitr_case_number(case.case_number)
        if cnorm in keys or case.case_number in keys:
            score += 1200.0
        else:
            for k in keys:
                if k and (k == cnorm or k in cn or k in (case.case_number or "")):
                    score += 1000.0
                    break

    if prefer_folder_substr and prefer_folder_substr.lower() in title_l:
        score += 1500.0

    nd = db.query(Document).filter(Document.case_id == case.id).count()
    score += float(min(nd, 150))

    # при равенстве — более ранний id (часто первая загрузка)
    score -= doc.id * 1e-6
    return score


def pick_keep_document(
    items: list[tuple[Document, Case]],
    db: Session,
    *,
    prefer_folder_substr: str | None,
) -> tuple[Document, Case]:
    best_item = max(
        items,
        key=lambda it: (_keep_score(it[0], it[1], db, prefer_folder_substr=prefer_folder_substr), -it[0].id),
    )
    return best_item


def looks_like_cross_folder_duplicate_cleanup_request(text: str) -> bool:
    """Убрать лишние копии одного имени файла в разных папках."""
    t = (text or "").lower()
    dup = any(
        k in t
        for k in (
            "дубликат",
            "дубли",
            "дубль",
            "одинаков",
            "повтор",
            "копии файлов",
            "копий файлов",
            "лишн копи",
            "лишние копии",
            "повторяющ",
        )
    )
    action = any(
        k in t
        for k in (
            "удали",
            "убери",
            "почисти",
            "оставь од",
            "один экземпляр",
            "одну копию",
            "одна копия",
            "сотри",
        )
    )
    preview = any(
        k in t
        for k in (
            "только список",
            "без удаления",
            "не удаляй",
            "превью",
            "покажи план",
            "что удалишь",
            "что удалится",
        )
    )
    if preview and not action:
        return True
    if (("покажи" in t) or ("выведи" in t)) and dup and not action:
        return True
    if action and dup:
        return True
    if action and ("папк" in t or "между папк" in t or "между дел" in t):
        return True
    return False


def handle_cross_folder_duplicate_cleanup_chat(db: Session, text: str) -> tuple[str, Case | None]:
    from .main import delete_documents_hard, get_or_create_unsorted_case

    t = (text or "").lower()
    unsorted_case = get_or_create_unsorted_case(db)
    dry_run = (
        any(
            k in t
            for k in (
                "только список",
                "без удаления",
                "не удаляй",
                "превью",
                "покажи план",
                "что удалишь",
                "что удалится",
            )
        )
        and not any(k in t for k in ("удали", "убери", "почисти", "выполни удаление", "да, удали"))
    ) or ("покажи" in t and not any(k in t for k in ("удали", "убери", "почисти")))

    prefer = folder_preference_hint_from_text(text)
    groups = gather_cross_folder_duplicate_groups(db)
    if not groups:
        return (
            "Одинаковых имён файла в **разных** папках не найдено — чистить нечего. "
            "(Совпадение только по нормализации пробелов и регистра в имени.)",
            unsorted_case,
        )

    lines: list[str] = [
        "**План очистки дубликатов** (одно и то же имя файла в нескольких папках).",
        "",
        "Правило «кого оставить»: совпадение **номера дела из имени файла** с папкой; "
        "папки «UNDEF», «TAG-*», «Неразобранное» в конце списка; "
        "если в сообщении указана папка в кавычках — приоритет ей.",
        "",
    ]
    if prefer:
        lines.append(f"Приоритет папки по вашей подсказке: «{prefer}».")
        lines.append("")
    if dry_run:
        lines.append("*Режим превью — файлы **не** удаляются. Чтобы выполнить: «Удали дубликаты между папками».*")
        lines.append("")

    to_remove: list[Document] = []
    n_groups = 0
    for _key, items in sorted(groups.items(), key=lambda x: (-len(x[1]), x[0])):
        keep_d, keep_c = pick_keep_document(items, db, prefer_folder_substr=prefer)
        remove = [d for d, _c in items if d.id != keep_d.id]
        if not remove:
            continue
        n_groups += 1
        if n_groups <= 35:
            lines.append(f"**{keep_d.filename}** — оставляю [{keep_d.id}] в «{keep_c.title}» ({keep_c.case_number})")
            for d, c in items:
                if d.id == keep_d.id:
                    continue
                lines.append(f"  − удалить [{d.id}] из «{c.title}» ({c.case_number})")
            lines.append("")
        to_remove.extend(remove)

    if n_groups > 35:
        lines.append(f"… и ещё групп: {n_groups - 35} (в ответе сокращено).")
        lines.append("")

    lines.append(f"Итого: **{n_groups}** групп, будет удалено **{len(to_remove)}** лишних файлов.")

    if dry_run or not to_remove:
        lines.append("")
        lines.append(
            "Чтобы **выполнить** удаление лишних копий, напишите, например: "
            "«Удали дубликаты между папками» или «Убери дубликаты, оставь по одному»."
        )
        return "\n".join(lines), unsorted_case

    delete_documents_hard(db, to_remove)
    db.add(
        CaseEvent(
            case_id=unsorted_case.id,
            event_type="duplicate_cleanup",
            body=f"Межпапочная очистка дубликатов по имени файла: удалено {len(to_remove)} копий в {n_groups} группах.",
        )
    )
    db.commit()

    lines.append("")
    lines.append(
        f"Готово: удалено **{len(to_remove)}** дубликатов. В каждой группе оставлена одна копия по правилам выше."
    )
    return "\n".join(lines), unsorted_case
