"""Appraisal chat must not wipe a folder.

Pre-fix, handle_delete_documents_chat treated «все документы» plus «в этой папке»
(or a case number, or «текущ» / «открыт») as wipe-the-folder and parsed
«1-й оценки» as document id 1. The calendar period parser does not
recognize these phrases.

A folder titled «Оценка» or «Оценщик» is not this guard. «без оценки»
is not this guard. «оценить» and «оценённый» are not «оценка».
«отложение» is not this guard. The surname «Оценщикова» is not «оценщика».
"""

from __future__ import annotations

import re
import unittest
from pathlib import Path

from app.calendar_appraisal import (
    appraisal_blocks_bulk_document_mutation,
    looks_like_appraisal_scoped_document_request,
    mask_appraisal_ordinals,
)
from app.ru_date_range import parse_calendar_period_ru


def _parse_ids_like_main(text: str) -> list[int]:
    raw = text or ""
    ids = [int(x) for x in re.findall(r"\[(\d+)\]", raw)]
    ids.extend(int(x) for x in re.findall(r"(?i)\bdoc[.:]?\s*(\d+)\b", raw))
    if ids:
        return sorted(set(ids))
    safe = mask_appraisal_ordinals(raw)
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


def _pre_fix_selects_active_folder(text: str) -> bool:
    """Current main treats these substrings as the open folder once wants_all is true."""
    low = (text or "").lower()
    return _wants_all(text) and any(
        p in low for p in ("этой папк", "текущ", "открыт", "в этой", "из этой", "это дело")
    )


class AppraisalScopeTests(unittest.TestCase):
    def test_folder_wipe_trigger_is_not_a_calendar_period(self) -> None:
        phrases = (
            "удали все документы за оценку в этой папке",
            "удали все документы за оценки в этой папке",
            "удали все документы по оценке в этой папке",
            "удали все документы об оценке в этой папке",
            "удали все документы за договор оценки в этой папке",
            "удали все документы по договору оценки в этой папке",
            "удали все документы за переоценку в этой папке",
            "удали все документы за недооценку в этой папке",
            "удали все документы за дооценку в этой папке",
            "удали все документы за оценщика в этой папке",
            "удали все документы по оценщику в этой папке",
            "удали все документы за оценщицу в этой папке",
            "удали все документы за оценочный отчет в этой папке",
            "удали все документы за оценочную стоимость в этой папке",
            "удали все документы за стоимость оценки в этой папке",
            "удали все документы за имущество оценки в этой папке",
            "удали все документы в ходе оценки в этой папке",
            "удали все документы на стадии оценки в этой папке",
            "удали все документы при оценке в этой папке",
            "удали все документы за текущую оценку",
            "удали все документы за текущую переоценку",
            "удали все документы за открытую оценку",
            "удали все документы за открытого оценщика",
            "удали каждый документ за оценку в этой папке",
            "удали все файлы за договор оценки в этой папке",
            "удали все документы дела А40-12345/2025 за оценку",
            "удали все документы дела А40-12345/2025 по договору оценки",
            "удали все документы дела А40-12345/2025 за оценщика",
            "удали все документы за Оценку в этой папке",
            "удали все документы во время оценки в этой папке",
            "удали все документы во время договора оценки в этой папке",
            "удали все документы за «оценку» в этой папке",
            "удали все документы за «договор оценки» в этой папке",
            "удали все документы за оспаривание оценки в этой папке",
            "удали все документы за срок оценки в этой папке",
            "удали все документы за рыночную оценку в этой папке",
            "удали все документы за его оценку в этой папке",
            "удали все документы за её оценку в этой папке",
            "удали все документы до оценки в этой папке",
            "удали все документы за период оценки в этой папке",
            "удали все документы в рамках оценки в этой папке",
            "удали все документы по результатам оценки в этой папке",
        )
        for text in phrases:
            self.assertTrue(_wants_all(text), text)
            self.assertIsNone(parse_calendar_period_ru(text), text)
            self.assertTrue(appraisal_blocks_bulk_document_mutation(text), text)
        for sample in (
            "удали все документы за оценку в этой папке",
            "удали все документы по договору оценки в этой папке",
            "удали все документы за оценщика в этой папке",
            "удали все документы за текущую оценку",
            "удали все документы за текущую переоценку",
            "удали все документы за открытую оценку",
            "удали все документы за открытого оценщика",
        ):
            self.assertTrue(_pre_fix_selects_active_folder(sample), sample)

    def test_ordinal_is_not_a_document_id(self) -> None:
        samples = (
            "удали документы 1-й оценки",
            "удали документы 1-го оценщика",
            "удали документы 1-й переоценки",
            "удали документы 1-е оценки",
            "удали документы 2-й оценки",
            "удали документы 1-й оценочного",
        )
        for text in samples:
            expected = [2] if "2-" in text else [1]
            self.assertEqual(_pre_fix_parse_ids(text), expected, text)
            self.assertEqual(_parse_ids_like_main(text), [], text)
            self.assertTrue(appraisal_blocks_bulk_document_mutation(text), text)
        self.assertEqual(_pre_fix_parse_ids("удали документы 100 оценок"), [100])
        self.assertEqual(_parse_ids_like_main("удали документы 100 оценок"), [])
        self.assertEqual(_pre_fix_parse_ids("удали документы 100 оценщиков"), [100])
        self.assertEqual(_parse_ids_like_main("удали документы 100 оценщиков"), [])
        self.assertEqual(_pre_fix_parse_ids("удали документы 12,5% оценки"), [5, 12])
        self.assertEqual(_parse_ids_like_main("удали документы 12,5% оценки"), [])
        self.assertEqual(_pre_fix_parse_ids("удали документы 12.5% оценки"), [12])
        self.assertEqual(_parse_ids_like_main("удали документы 12.5% оценки"), [])
        self.assertEqual(_pre_fix_parse_ids("удали документы 12,5% договора оценки"), [5, 12])
        self.assertEqual(_parse_ids_like_main("удали документы 12,5% договора оценки"), [])
        self.assertEqual(_pre_fix_parse_ids("удали документы 214-го оценщика"), [214])
        self.assertEqual(_parse_ids_like_main("удали документы 214-го оценщика"), [])
        self.assertEqual(_pre_fix_parse_ids("удали документы 214-й оценки"), [214])
        self.assertEqual(_parse_ids_like_main("удали документы 214-й оценки"), [])
        self.assertEqual(_pre_fix_parse_ids("удали документы 214-го договора оценки"), [214])
        self.assertEqual(_parse_ids_like_main("удали документы 214-го договора оценки"), [])
        self.assertEqual(_pre_fix_parse_ids("удали документы 1 оценки"), [1])
        self.assertEqual(_parse_ids_like_main("удали документы 1 оценки"), [])
        self.assertEqual(_parse_ids_like_main("удали документ 214 за 100 оценок"), [214])
        self.assertEqual(_parse_ids_like_main("удали документы 214 287"), [214, 287])
        self.assertEqual(_parse_ids_like_main("удали документы 214 287 за оценку"), [214, 287])
        self.assertEqual(_parse_ids_like_main("удали документы 1-е отложения"), [1])
        self.assertEqual(_parse_ids_like_main("удали документы 1-й перевозки"), [1])

    def test_move_all_with_scope_is_blocked(self) -> None:
        phrases = (
            "перенеси все документы дела А40-12345/2025 за оценку в папку Архив",
            "перенеси все документы дела А40-12345/2025 по договору оценки в папку Архив",
            "перенеси все документы дела А40-12345/2025 за оценщика в папку Архив",
            "перенеси все документы дела А40-12345/2025 за переоценку в папку Архив",
            "перенеси все документы дела А40-12345/2025 за договор оценки в папку Архив",
            "перенеси документ 1-й оценки в дело Архив",
            "перемести документ 1-й оценщика в дело Архив",
        )
        for text in phrases:
            self.assertTrue(appraisal_blocks_bulk_document_mutation(text), text)
        kept = "перенеси документ 214 за оценку в дело Архив"
        kept_ids = [
            int(x)
            for x in re.findall(
                r"(?:документ|файл)\s+(\d+)",
                mask_appraisal_ordinals(kept),
                flags=re.IGNORECASE,
            )
        ]
        self.assertEqual(kept_ids, [214])
        amount = "перенеси все документы дела А40-12345/2025 за 100 оценок в папку Архив"
        masked = mask_appraisal_ordinals(amount)
        self.assertIn("12345", masked)
        self.assertIn("2025", masked)
        self.assertNotIn("100", masked)

    def test_explicit_id_still_allowed(self) -> None:
        self.assertFalse(
            appraisal_blocks_bulk_document_mutation(
                "удали документ 214 за оценку",
                explicit_document_ids=[214],
            )
        )
        self.assertEqual(_parse_ids_like_main("удали документ 214 за оценку"), [214])
        self.assertEqual(_parse_ids_like_main("удали документ 214 по договору оценки"), [214])
        self.assertEqual(_parse_ids_like_main("удали документ 18 по оценщику"), [18])
        self.assertEqual(_parse_ids_like_main("удали документы [12] [18] за оценку"), [12, 18])
        self.assertEqual(_parse_ids_like_main("удали документ 214"), [214])
        self.assertEqual(_parse_ids_like_main("doc: 214 за оценку"), [214])

    def test_plain_folder_commands_are_not_scoped(self) -> None:
        for text in (
            "удали все документы в этой папке",
            "удали все документы из этой папки",
            "удали все документы в текущей папке",
            "удали все документы в открытой папке",
            "удали все документы это дело",
            "удали все документы дела А40-12345/2025",
            "удали все документы в папке Оценка",
            "удали все документы в папке Оценщик",
            "удали все документы в папке «Оценка»",
            "удали все документы в папке «Переоценка»",
            "удали все документы без оценки в этой папке",
            "удали все документы без оценщика в этой папке",
            "удали все документы без договора оценки в этой папке",
            "удали все документы за банкротство в этой папке",
            "удали все документы за отложение в этой папке",
            "удали все документы за НДФЛ в этой папке",
            "удали все документы за ФНС в этой папке",
            "удали все документы за УСН в этой папке",
            "удали все документы за недоимку в этой папке",
            "удали все документы за доначисление в этой папке",
            "удали все документы по договору в этой папке",
            "удали все документы за период в этой папке",
            "удали все документы за стоимость в этой папке",
            "удали все документы за имущество в этой папке",
            "удали все документы в рамках отложения в этой папке",
            "удали все документы до отложения в этой папке",
            "удали все документы, которые надо оценить, в этой папке",
            "удали все документы, которые надо оценивать, в этой папке",
            "удали все документы за оценённый актив в этой папке",
            "удали все документы, оценивая актив, в этой папке",
            "удали все документы за Оценщикова в этой папке",
            "удали все документы по делу Оценщиков",
            "перенеси все документы в папку Архив",
            "перенеси все документы в папку Оценка",
            "перенеси все документы в папку Оценщик",
            "собери все документы в папку Оценка по Гримме",
            "удали документ 214",
            "удали все документы по делу Оценка",
            "удали все документы по делу Оценщик",
            "удали все документы по делу Переоценка",
        ):
            self.assertFalse(looks_like_appraisal_scoped_document_request(text), text)
            self.assertFalse(appraisal_blocks_bulk_document_mutation(text), text)

    def test_inflected_forms_are_scoped(self) -> None:
        phrases = (
            "за оценку",
            "за оценки",
            "по оценке",
            "об оценке",
            "за оценкой",
            "за оценкою",
            "за оценок",
            "за оценкам",
            "за оценками",
            "за оценках",
            "за переоценку",
            "за недооценку",
            "за дооценку",
            "за самооценку",
            "за оценщика",
            "по оценщику",
            "об оценщике",
            "за оценщиком",
            "за оценщиков",
            "за оценщиками",
            "за оценщицу",
            "за оценщицы",
            "за оценщицей",
            "за оценочный отчет",
            "за оценочного отчета",
            "по оценочному отчету",
            "за переоценочную стоимость",
            "за стоимость оценки",
            "за имущество оценки",
            "за договор оценки",
            "по договору оценки",
            "за договор переоценки",
            "в ходе оценки",
            "на стадии оценки",
            "во время оценки",
            "при оценке",
            "за срок оценки",
            "за оспаривание оценки",
            "за рыночную оценку",
            "за первую оценку",
            "за текущую оценку",
            "за открытую оценку",
            "за его оценку",
            "за её оценку",
            "до оценки",
            "до оценщика",
            "за период оценки",
            "в рамках оценки",
            "по результатам оценки",
        )
        for text in phrases:
            self.assertTrue(
                looks_like_appraisal_scoped_document_request(f"удали все документы {text} в этой папке"),
                text,
            )

    def test_main_wires_the_guard_before_the_wipe(self) -> None:
        source = (Path(__file__).resolve().parent / "app" / "main.py").read_text(encoding="utf-8")
        self.assertIn("appraisal_blocks_bulk_document_mutation", source)
        self.assertIn("mask_appraisal_ordinals", source)
        self.assertIn("DELETE_REFUSED_REPLY", source)
        self.assertIn("MOVE_REFUSED_REPLY", source)
        delete_fn = source.split("def handle_delete_documents_chat", 1)[1].split("\ndef ", 1)[0]
        self.assertLess(
            delete_fn.index("appraisal_blocks_bulk_document_mutation"),
            delete_fn.index("wants_all = any"),
        )
        wipe = delete_fn.split("wants_all = any", 1)[1]
        self.assertIn("delete_documents_hard", wipe)
        parse_fn = source.split("def parse_document_ids_for_delete_command", 1)[1].split("\ndef ", 1)[0]
        self.assertLess(parse_fn.index("mask_appraisal_ordinals"), parse_fn.index("re.search"))
        move_fn = source.split("def move_documents_by_chat_command", 1)[1].split("\ndef ", 1)[0]
        self.assertIn("mask_appraisal_ordinals", move_fn)
        bulk = source.split("if looks_like_move_all_from_active_case_to_folder(text):", 1)[1]
        self.assertLess(
            bulk.index("appraisal_blocks_bulk_document_mutation"),
            bulk.index("execute_move_all_documents_to_case_folder"),
        )


if __name__ == "__main__":
    unittest.main()
