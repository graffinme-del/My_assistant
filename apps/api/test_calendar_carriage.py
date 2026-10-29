"""Carriage chat must not wipe a folder.

Pre-fix, handle_delete_documents_chat treated «все документы» plus «в этой папке»
(or a case number, or «текущ» / «открыт») as wipe-the-folder and parsed
«1-й перевозки» as document id 1. The calendar period parser does not
recognize these phrases.

A folder titled «Перевозка» or «Перевозчик» is not this guard. «без перевозки»
is not this guard. «перевозить» and «перевезти» are not «перевозка».
«транспорт», «экспедитор», and «фрахт» are not this guard. «оценщик» and
«отложение» are not this guard.
"""

from __future__ import annotations

import re
import unittest
from pathlib import Path

from app.calendar_carriage import (
    carriage_blocks_bulk_document_mutation,
    looks_like_carriage_scoped_document_request,
    mask_carriage_ordinals,
)
from app.ru_date_range import parse_calendar_period_ru


def _parse_ids_like_main(text: str) -> list[int]:
    raw = text or ""
    ids = [int(x) for x in re.findall(r"\[(\d+)\]", raw)]
    ids.extend(int(x) for x in re.findall(r"(?i)\bdoc[.:]?\s*(\d+)\b", raw))
    if ids:
        return sorted(set(ids))
    safe = mask_carriage_ordinals(raw)
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


class CarriageScopeTests(unittest.TestCase):
    def test_folder_wipe_trigger_is_not_a_calendar_period(self) -> None:
        phrases = (
            "удали все документы за перевозку в этой папке",
            "удали все документы за перевозки в этой папке",
            "удали все документы по перевозке в этой папке",
            "удали все документы о перевозке в этой папке",
            "удали все документы за договор перевозки в этой папке",
            "удали все документы по договору перевозки в этой папке",
            "удали все документы за грузоперевозку в этой папке",
            "удали все документы за автоперевозку в этой папке",
            "удали все документы за авиаперевозку в этой папке",
            "удали все документы за контейнероперевозку в этой папке",
            "удали все документы за перевозчика в этой папке",
            "удали все документы по перевозчику в этой папке",
            "удали все документы за перевозчицу в этой папке",
            "удали все документы за перевозочный документ в этой папке",
            "удали все документы за перевозной тариф в этой папке",
            "удали все документы за перевоз в этой папке",
            "удали все документы по перевозу в этой папке",
            "удали все документы в ходе перевозки в этой папке",
            "удали все документы на стадии перевозки в этой папке",
            "удали все документы при перевозке в этой папке",
            "удали все документы за текущую перевозку",
            "удали все документы за текущую грузоперевозку",
            "удали все документы за открытую перевозку",
            "удали все документы за открытого перевозчика",
            "удали каждый документ за перевозку в этой папке",
            "удали все файлы за договор перевозки в этой папке",
            "удали все документы дела А40-12345/2025 за перевозку",
            "удали все документы дела А40-12345/2025 по договору перевозки",
            "удали все документы дела А40-12345/2025 за перевозчика",
            "удали все документы за Перевозку в этой папке",
            "удали все документы во время перевозки в этой папке",
            "удали все документы во время договора перевозки в этой папке",
            "удали все документы за «перевозку» в этой папке",
            "удали все документы за «договор перевозки» в этой папке",
            "удали все документы за оспаривание перевозки в этой папке",
            "удали все документы за срок перевозки в этой папке",
            "удали все документы за международную перевозку в этой папке",
        )
        for text in phrases:
            self.assertTrue(_wants_all(text), text)
            self.assertIsNone(parse_calendar_period_ru(text), text)
            self.assertTrue(carriage_blocks_bulk_document_mutation(text), text)
        for sample in (
            "удали все документы за перевозку в этой папке",
            "удали все документы по договору перевозки в этой папке",
            "удали все документы за перевозчика в этой папке",
            "удали все документы за текущую перевозку",
            "удали все документы за текущую грузоперевозку",
            "удали все документы за открытую перевозку",
            "удали все документы за открытого перевозчика",
        ):
            self.assertTrue(_pre_fix_selects_active_folder(sample), sample)

    def test_ordinal_is_not_a_document_id(self) -> None:
        samples = (
            "удали документы 1-й перевозки",
            "удали документы 1-го перевозчика",
            "удали документы 1-й грузоперевозки",
            "удали документы 1-е перевозки",
            "удали документы 2-й перевозки",
            "удали документы 1-й перевозочного",
        )
        for text in samples:
            expected = [2] if "2-" in text else [1]
            self.assertEqual(_pre_fix_parse_ids(text), expected, text)
            self.assertEqual(_parse_ids_like_main(text), [], text)
            self.assertTrue(carriage_blocks_bulk_document_mutation(text), text)
        self.assertEqual(_pre_fix_parse_ids("удали документы 100 перевозок"), [100])
        self.assertEqual(_parse_ids_like_main("удали документы 100 перевозок"), [])
        self.assertEqual(_pre_fix_parse_ids("удали документы 100 перевозчиков"), [100])
        self.assertEqual(_parse_ids_like_main("удали документы 100 перевозчиков"), [])
        self.assertEqual(_pre_fix_parse_ids("удали документы 12,5% перевозки"), [5, 12])
        self.assertEqual(_parse_ids_like_main("удали документы 12,5% перевозки"), [])
        self.assertEqual(_pre_fix_parse_ids("удали документы 12.5% перевозки"), [12])
        self.assertEqual(_parse_ids_like_main("удали документы 12.5% перевозки"), [])
        self.assertEqual(_pre_fix_parse_ids("удали документы 12,5% договора перевозки"), [5, 12])
        self.assertEqual(_parse_ids_like_main("удали документы 12,5% договора перевозки"), [])
        self.assertEqual(_pre_fix_parse_ids("удали документы 214-го перевозчика"), [214])
        self.assertEqual(_parse_ids_like_main("удали документы 214-го перевозчика"), [])
        self.assertEqual(_pre_fix_parse_ids("удали документы 214-й перевозки"), [214])
        self.assertEqual(_parse_ids_like_main("удали документы 214-й перевозки"), [])
        self.assertEqual(_pre_fix_parse_ids("удали документы 214-го договора перевозки"), [214])
        self.assertEqual(_parse_ids_like_main("удали документы 214-го договора перевозки"), [])
        self.assertEqual(_pre_fix_parse_ids("удали документы 1 перевозки"), [1])
        self.assertEqual(_parse_ids_like_main("удали документы 1 перевозки"), [])
        self.assertEqual(_parse_ids_like_main("удали документ 214 за 100 перевозок"), [214])
        self.assertEqual(_parse_ids_like_main("удали документы 214 287"), [214, 287])
        self.assertEqual(_parse_ids_like_main("удали документы 214 287 за перевозку"), [214, 287])
        self.assertEqual(_parse_ids_like_main("удали документы 1-го оценщика"), [1])
        self.assertEqual(_parse_ids_like_main("удали документы 1-е отложения"), [1])
        self.assertEqual(_parse_ids_like_main("удали документы 1-й сделки"), [1])

    def test_move_all_with_scope_is_blocked(self) -> None:
        phrases = (
            "перенеси все документы дела А40-12345/2025 за перевозку в папку Архив",
            "перенеси все документы дела А40-12345/2025 по договору перевозки в папку Архив",
            "перенеси все документы дела А40-12345/2025 за перевозчика в папку Архив",
            "перенеси все документы дела А40-12345/2025 за грузоперевозку в папку Архив",
            "перенеси все документы дела А40-12345/2025 за договор перевозки в папку Архив",
            "перенеси документ 1-й перевозки в дело Архив",
            "перемести документ 1-й перевозчика в дело Архив",
        )
        for text in phrases:
            self.assertTrue(carriage_blocks_bulk_document_mutation(text), text)
        kept = "перенеси документ 214 за перевозку в дело Архив"
        kept_ids = [
            int(x)
            for x in re.findall(
                r"(?:документ|файл)\s+(\d+)",
                mask_carriage_ordinals(kept),
                flags=re.IGNORECASE,
            )
        ]
        self.assertEqual(kept_ids, [214])
        amount = "перенеси все документы дела А40-12345/2025 за 100 перевозок в папку Архив"
        masked = mask_carriage_ordinals(amount)
        self.assertIn("12345", masked)
        self.assertIn("2025", masked)
        self.assertNotIn("100", masked)

    def test_explicit_id_still_allowed(self) -> None:
        self.assertFalse(
            carriage_blocks_bulk_document_mutation(
                "удали документ 214 за перевозку",
                explicit_document_ids=[214],
            )
        )
        self.assertEqual(_parse_ids_like_main("удали документ 214 за перевозку"), [214])
        self.assertEqual(_parse_ids_like_main("удали документ 214 по договору перевозки"), [214])
        self.assertEqual(_parse_ids_like_main("удали документ 18 по перевозчику"), [18])
        self.assertEqual(_parse_ids_like_main("удали документы [12] [18] за перевозку"), [12, 18])
        self.assertEqual(_parse_ids_like_main("удали документ 214"), [214])
        self.assertEqual(_parse_ids_like_main("doc: 214 за перевозку"), [214])

    def test_plain_folder_commands_are_not_scoped(self) -> None:
        for text in (
            "удали все документы в этой папке",
            "удали все документы из этой папки",
            "удали все документы в текущей папке",
            "удали все документы в открытой папке",
            "удали все документы это дело",
            "удали все документы дела А40-12345/2025",
            "удали все документы в папке Перевозка",
            "удали все документы в папке Перевозчик",
            "удали все документы в папке «Перевозка»",
            "удали все документы в папке «Грузоперевозка»",
            "удали все документы без перевозки в этой папке",
            "удали все документы без перевозчика в этой папке",
            "удали все документы без договора перевозки в этой папке",
            "удали все документы за банкротство в этой папке",
            "удали все документы за транспорт в этой папке",
            "удали все документы за экспедитора в этой папке",
            "удали все документы за фрахт в этой папке",
            "удали все документы за оценщика в этой папке",
            "удали все документы за отложение в этой папке",
            "удали все документы за НДФЛ в этой папке",
            "удали все документы за ФНС в этой папке",
            "удали все документы за УСН в этой папке",
            "удали все документы за недоимку в этой папке",
            "удали все документы за доначисление в этой папке",
            "удали все документы, которые надо перевозить, в этой папке",
            "удали все документы, которые надо перевезти, в этой папке",
            "удали все документы за перевезённый груз в этой папке",
            "удали все документы, перевозя груз, в этой папке",
            "удали все документы за Перевозчикова в этой папке",
            "удали все документы по делу Перевозчиков",
            "перенеси все документы в папку Архив",
            "перенеси все документы в папку Перевозка",
            "перенеси все документы в папку Перевозчик",
            "собери все документы в папку Перевозка по Гримме",
            "удали документ 214",
            "удали все документы по делу Перевозка",
            "удали все документы по делу Перевозчик",
            "удали все документы по делу Грузоперевозка",
        ):
            self.assertFalse(looks_like_carriage_scoped_document_request(text), text)
            self.assertFalse(carriage_blocks_bulk_document_mutation(text), text)

    def test_inflected_forms_are_scoped(self) -> None:
        phrases = (
            "за перевозку",
            "за перевозки",
            "по перевозке",
            "о перевозке",
            "за перевозкой",
            "за перевозкою",
            "за перевозок",
            "за перевозкам",
            "за перевозками",
            "за перевозках",
            "за грузоперевозку",
            "за автоперевозки",
            "за авиаперевозку",
            "за контейнероперевозку",
            "за перевозчика",
            "по перевозчику",
            "о перевозчике",
            "за перевозчиком",
            "за перевозчиков",
            "за перевозчиками",
            "за перевозчицу",
            "за перевозчицы",
            "за перевозчицей",
            "за перевозочный документ",
            "за перевозочного документа",
            "по перевозочному документу",
            "за перевозной тариф",
            "за перевозного тарифа",
            "за перевоз",
            "за перевоза",
            "по перевозу",
            "о перевозе",
            "за перевозом",
            "за договор перевозки",
            "по договору перевозки",
            "за договор грузоперевозки",
            "в ходе перевозки",
            "на стадии перевозки",
            "во время перевозки",
            "при перевозке",
            "за срок перевозки",
            "за оспаривание перевозки",
            "за международную перевозку",
            "за первую перевозку",
            "за текущую перевозку",
            "за открытую перевозку",
        )
        for text in phrases:
            self.assertTrue(
                looks_like_carriage_scoped_document_request(f"удали все документы {text} в этой папке"),
                text,
            )

    def test_main_wires_the_guard_before_the_wipe(self) -> None:
        source = (Path(__file__).resolve().parent / "app" / "main.py").read_text(encoding="utf-8")
        self.assertIn("carriage_blocks_bulk_document_mutation", source)
        self.assertIn("mask_carriage_ordinals", source)
        self.assertIn("DELETE_REFUSED_REPLY", source)
        self.assertIn("MOVE_REFUSED_REPLY", source)
        delete_fn = source.split("def handle_delete_documents_chat", 1)[1].split("\ndef ", 1)[0]
        self.assertLess(
            delete_fn.index("carriage_blocks_bulk_document_mutation"),
            delete_fn.index("wants_all = any"),
        )
        wipe = delete_fn.split("wants_all = any", 1)[1]
        self.assertIn("delete_documents_hard", wipe)
        parse_fn = source.split("def parse_document_ids_for_delete_command", 1)[1].split("\ndef ", 1)[0]
        self.assertLess(parse_fn.index("mask_carriage_ordinals"), parse_fn.index("re.search"))
        move_fn = source.split("def move_documents_by_chat_command", 1)[1].split("\ndef ", 1)[0]
        self.assertIn("mask_carriage_ordinals", move_fn)
        bulk = source.split("if looks_like_move_all_from_active_case_to_folder(text):", 1)[1]
        self.assertLess(
            bulk.index("carriage_blocks_bulk_document_mutation"),
            bulk.index("execute_move_all_documents_to_case_folder"),
        )


if __name__ == "__main__":
    unittest.main()
