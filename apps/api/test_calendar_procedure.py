"""Procedure-scoped chat must not wipe a folder or delete the wrong document.

Pre-fix, handle_delete_documents_chat treated «все документы» plus «в этой папке»
as wipe-the-folder and parsed «1-го наблюдения» as document id 1. The calendar
period parser does not recognize these phrases. Bare «банкротство» is not this
guard. A folder titled «Наблюдение» is not this guard.
"""

from __future__ import annotations

import re
import unittest
from pathlib import Path

from app.active_folder_scope import looks_like_active_folder_reference
from app.calendar_procedure import (
    looks_like_procedure_scoped_document_request,
    mask_procedure_ordinals,
    procedure_blocks_bulk_document_mutation,
)
from app.ru_date_range import parse_calendar_period_ru


def _parse_ids_like_main(text: str) -> list[int]:
    raw = text or ""
    ids = [int(x) for x in re.findall(r"\[(\d+)\]", raw)]
    ids.extend(int(x) for x in re.findall(r"(?i)\bdoc[.:]?\s*(\d+)\b", raw))
    if ids:
        return sorted(set(ids))
    safe = mask_procedure_ordinals(raw)
    m = re.search(
        r"(?:документы?|файлы?)(?:\s+(?:с\s+)?id|\s+№|\s+#)?\s*[:.]?\s*([\d\s,;и]+)",
        safe,
        flags=re.IGNORECASE,
    )
    if m:
        return sorted({int(x) for x in re.findall(r"\d+", m.group(1))})
    m2 = re.search(r"(?:документ|файл)\s*(?:№|#)?\s*(\d+)\b", safe, flags=re.IGNORECASE)
    if m2:
        return [int(m2.group(1))]
    return []


def _pre_fix_parse_ids(text: str) -> list[int]:
    raw = text or ""
    ids = [int(x) for x in re.findall(r"\[(\d+)\]", raw)]
    ids.extend(int(x) for x in re.findall(r"(?i)\bdoc[.:]?\s*(\d+)\b", raw))
    if ids:
        return sorted(set(ids))
    m = re.search(
        r"(?:документы?|файлы?)(?:\s+(?:с\s+)?id|\s+№|\s+#)?\s*[:.]?\s*([\d\s,;и]+)",
        text or "",
        flags=re.IGNORECASE,
    )
    if m:
        return sorted({int(x) for x in re.findall(r"\d+", m.group(1))})
    m2 = re.search(r"(?:документ|файл)\s*(?:№|#)?\s*(\d+)\b", text or "", flags=re.IGNORECASE)
    if m2:
        return [int(m2.group(1))]
    return []


def _wants_all(text: str) -> bool:
    low = (text or "").lower()
    return any(
        w in low
        for w in (
            "все документ",
            "все файлы",
            "всех документ",
            "всех файлов",
            "каждый документ",
            "каждый файл",
        )
    )


class ProcedureScopeTests(unittest.TestCase):
    def test_folder_wipe_trigger_is_not_a_calendar_period(self) -> None:
        phrases = (
            "удали все документы за конкурсное производство в этой папке",
            "удали все документы за конкурсного производства в этой папке",
            "удали все документы по конкурсному производству в этой папке",
            "удали все документы в конкурсном производстве в этой папке",
            "удали все документы за процедуру конкурсного производства в этой папке",
            "удали все документы за открытие конкурсного производства в этой папке",
            "удали все документы за упрощенное конкурсное производство в этой папке",
            "удали все документы за конкурсную массу в этой папке",
            "удали все документы по конкурсной массе в этой папке",
            "удали все документы за формирование конкурсной массы в этой папке",
            "удали все документы за наблюдение в этой папке",
            "удали все документы по наблюдению в этой папке",
            "удали все документы в наблюдении в этой папке",
            "удали все документы за введение наблюдения в этой папке",
            "удали все документы за процедуру наблюдения в этой папке",
            "удали все документы за внешнее управление в этой папке",
            "удали все документы по внешнему управлению в этой папке",
            "удали все документы за введение внешнего управления в этой папке",
            "удали все документы за финансовое оздоровление в этой папке",
            "удали все документы по финансовому оздоровлению в этой папке",
            "удали все документы за процедуру финансового оздоровления в этой папке",
            "удали все документы за исполнительное производство в этой папке",
            "удали все документы по исполнительному производству в этой папке",
            "удали все документы в исполнительном производстве в этой папке",
            "удали все документы за возбуждение исполнительного производства в этой папке",
            "удали все документы во время наблюдения в этой папке",
            "удали все документы за всю конкурсную массу в этой папке",
            "удали каждый документ за наблюдение в этой папке",
            "удали все файлы за конкурсное производство в этой папке",
        )
        for text in phrases:
            self.assertTrue(_wants_all(text), text)
            self.assertTrue(looks_like_active_folder_reference(text), text)
            self.assertEqual(_pre_fix_parse_ids(text), [], text)
            self.assertIsNone(parse_calendar_period_ru(text), text)
            self.assertTrue(procedure_blocks_bulk_document_mutation(text), text)

    def test_ordinal_is_not_a_document_id(self) -> None:
        samples = (
            "удали документы 1-го конкурсного производства",
            "удали документы 1-е конкурсное производство",
            "удали документы 1-й конкурсной массы",
            "удали документы 1-го наблюдения",
            "удали документы 1-е наблюдение",
            "удали документы 1-го внешнего управления",
            "удали документы 1-е внешнее управление",
            "удали документы 1-го финансового оздоровления",
            "удали документы 1-е финансовое оздоровление",
            "удали документы 1-го исполнительного производства",
            "удали документы 2-го наблюдения",
        )
        for text in samples:
            expected = [2] if "2-" in text else [1]
            self.assertEqual(_pre_fix_parse_ids(text), expected, text)
            self.assertEqual(_parse_ids_like_main(text), [], text)
            self.assertTrue(procedure_blocks_bulk_document_mutation(text), text)
        self.assertEqual(_pre_fix_parse_ids("удали документы 100 конкурсной массы"), [100])
        self.assertEqual(_parse_ids_like_main("удали документы 100 конкурсной массы"), [])
        self.assertEqual(_pre_fix_parse_ids("удали документы 12,5 конкурсной массы"), [5, 12])
        self.assertEqual(_parse_ids_like_main("удали документы 12,5 конкурсной массы"), [])
        self.assertEqual(_parse_ids_like_main("удали документ 214 за 100 конкурсной массы"), [214])

    def test_move_all_with_scope_is_blocked(self) -> None:
        phrases = (
            "перенеси все документы дела А40-12345/2025 за конкурсное производство в папку Архив",
            "перенеси все документы дела А40-12345/2025 за конкурсную массу в папку Архив",
            "перенеси все документы дела А40-12345/2025 за наблюдение в папку Архив",
            "перенеси все документы дела А40-12345/2025 за внешнее управление в папку Архив",
            "перенеси все документы дела А40-12345/2025 за финансовое оздоровление в папку Архив",
            "перенеси все документы дела А40-12345/2025 за исполнительное производство в папку Архив",
            "перенеси документ 1-го наблюдения в дело Архив",
            "перенеси документ 1-е внешнее управление в дело Архив",
        )
        for text in phrases:
            self.assertTrue(procedure_blocks_bulk_document_mutation(text), text)
        kept = "перенеси документ 214 за наблюдение в дело Архив"
        kept_ids = [
            int(x)
            for x in re.findall(
                r"(?:документ|файл)\s+(\d+)",
                mask_procedure_ordinals(kept),
                flags=re.IGNORECASE,
            )
        ]
        self.assertEqual(kept_ids, [214])
        amount = "перенеси все документы дела А40-12345/2025 за 100 конкурсной массы в папку Архив"
        masked = mask_procedure_ordinals(amount)
        self.assertIn("12345", masked)
        self.assertIn("2025", masked)
        self.assertNotIn("100", masked)

    def test_explicit_id_still_allowed(self) -> None:
        self.assertFalse(
            procedure_blocks_bulk_document_mutation(
                "удали документ 214 за конкурсное производство",
                explicit_document_ids=[214],
            )
        )
        self.assertEqual(_parse_ids_like_main("удали документ 214 за конкурсное производство"), [214])
        self.assertEqual(_parse_ids_like_main("удали документ 18 за наблюдение"), [18])
        self.assertEqual(_parse_ids_like_main("удали документ 18 за внешнее управление"), [18])
        self.assertEqual(_parse_ids_like_main("удали документ 18 за финансовое оздоровление"), [18])
        self.assertEqual(_parse_ids_like_main("удали документ 18 за исполнительное производство"), [18])
        self.assertEqual(_parse_ids_like_main("удали документы [12] [18] за наблюдение"), [12, 18])
        self.assertEqual(_parse_ids_like_main("удали документ 214"), [214])
        self.assertEqual(_parse_ids_like_main("удали документы 214 287"), [214, 287])

    def test_plain_folder_commands_are_not_scoped(self) -> None:
        for text in (
            "удали все документы в этой папке",
            "удали все документы в текущей папке",
            "удали все документы в открытой папке",
            "удали все документы в этой папке без наблюдения",
            "удали все документы в этой папке без конкурсного производства",
            "удали все документы в этой папке без внешнего управления",
            "удали все документы в этой папке без финансового оздоровления",
            "удали все документы в этой папке без исполнительного производства",
            "удали все документы в папке Наблюдение",
            "удали все документы в папке Конкурсное производство",
            "удали все документы в папке Внешнее управление",
            "удали все документы в папке Финансовое оздоровление",
            "удали все документы из папки Исполнительное производство",
            "перенеси все документы в папку Наблюдение",
            "удали все документы по делу Банкротство Эмиль",
            "удали все документы по делу Наблюдение",
            "удали все документы по делу Конкурсное производство",
            "удали все документы дела А53-13969/2026",
            "удали все документы по Вартанов Эмиль Валерьевич",
            "удали все документы за конкурсного управляющего в этой папке",
            "удали все документы за внешнего управляющего в этой папке",
            "удали все документы за финансового управляющего в этой папке",
            "удали все документы за арбитражного управляющего в этой папке",
            "удали все документы за исполнительный лист в этой папке",
            "удали все документы за производство в этой папке",
            "удали все документы за управление в этой папке",
            "удали все документы за массу в этой папке",
            "удали все документы за банкротство в этой папке",
            "удали документы 1-го управляющего",
            "удали все документы за наблюдать в этой папке",
        ):
            self.assertFalse(looks_like_procedure_scoped_document_request(text), text)
            self.assertFalse(procedure_blocks_bulk_document_mutation(text), text)

    def test_genitive_document_forms_are_scoped(self) -> None:
        for text in (
            "удали документы конкурсного производства в этой папке",
            "удали документы конкурсной массы в этой папке",
            "удали документы наблюдения в этой папке",
            "удали документы внешнего управления в этой папке",
            "удали документы финансового оздоровления в этой папке",
            "удали документы исполнительного производства в этой папке",
            "удали все документы за первое наблюдение в этой папке",
            "удали эти наблюдения в этой папке",
        ):
            self.assertTrue(procedure_blocks_bulk_document_mutation(text), text)

    def test_main_wires_the_guard_before_the_wipe(self) -> None:
        source = (Path(__file__).resolve().parent / "app" / "main.py").read_text(encoding="utf-8")
        self.assertIn("procedure_blocks_bulk_document_mutation", source)
        self.assertIn("mask_procedure_ordinals", source)
        self.assertIn("DELETE_REFUSED_REPLY", source)
        self.assertIn("MOVE_REFUSED_REPLY", source)
        delete_fn = source.split("def handle_delete_documents_chat", 1)[1].split("\ndef ", 1)[0]
        self.assertLess(
            delete_fn.index("procedure_blocks_bulk_document_mutation"),
            delete_fn.index("wants_all = any"),
        )
        parse_fn = source.split("def parse_document_ids_for_delete_command", 1)[1].split("\ndef ", 1)[0]
        self.assertLess(parse_fn.index("mask_procedure_ordinals"), parse_fn.index("re.search"))
        move_fn = source.split("def move_documents_by_chat_command", 1)[1].split("\ndef ", 1)[0]
        self.assertIn("mask_procedure_ordinals", move_fn)
        bulk = source.split("if looks_like_move_all_from_active_case_to_folder(text):", 1)[1]
        self.assertLess(
            bulk.index("procedure_blocks_bulk_document_mutation"),
            bulk.index("execute_move_all_documents_to_case_folder"),
        )


if __name__ == "__main__":
    unittest.main()
