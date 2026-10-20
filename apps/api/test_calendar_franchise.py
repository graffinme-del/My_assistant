"""Franchise / dividend / subsidy chat must not wipe a folder.

Pre-fix, handle_delete_documents_chat treated «все документы» plus «в этой папке»
(or a case number, or «текущ» / «открыт») as wipe-the-folder and parsed
«1-го дивиденда» as document id 1. The calendar period parser does not recognize
these phrases.

«субсидиарная» is not «субсидия». A folder titled «Франшиза» is not this guard.
Bare «банкротство» is not this guard. «франчайзинг» is not this guard.
«кредит» / «овердрафт» / «рента» stay with their own guards.
"""

from __future__ import annotations

import re
import unittest
from pathlib import Path

from app.calendar_franchise import (
    franchise_blocks_bulk_document_mutation,
    looks_like_franchise_scoped_document_request,
    mask_franchise_ordinals,
)
from app.ru_date_range import parse_calendar_period_ru


def _parse_ids_like_main(text: str) -> list[int]:
    raw = text or ""
    ids = [int(x) for x in re.findall(r"\[(\d+)\]", raw)]
    ids.extend(int(x) for x in re.findall(r"(?i)\bdoc[.:]?\s*(\d+)\b", raw))
    if ids:
        return sorted(set(ids))
    safe = mask_franchise_ordinals(raw)
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


class FranchiseScopeTests(unittest.TestCase):
    def test_folder_wipe_trigger_is_not_a_calendar_period(self) -> None:
        phrases = (
            "удали все документы за франшизу в этой папке",
            "удали все документы по франшизе в этой папке",
            "удали все документы о франшизе в этой папке",
            "удали все документы за договор франшизы в этой папке",
            "удали все документы за размер франшизы в этой папке",
            "удали все документы за безусловную франшизу в этой папке",
            "удали все документы за условную франшизу в этой папке",
            "удали все документы за франшизный взнос в этой папке",
            "удали все документы за 12,5% франшизы в этой папке",
            "удали все документы за текущую франшизу в этой папке",
            "удали все документы за открытую франшизу в этой папке",
            "удали все документы во время франшизы в этой папке",
            "удали все документы за дивиденд в этой папке",
            "удали все документы по дивидендам в этой папке",
            "удали все документы за выплату дивидендов в этой папке",
            "удали все документы за начисление дивидендов в этой папке",
            "удали все документы за распределение дивидендов в этой папке",
            "удали все документы за дивидендную политику в этой папке",
            "удали все документы за политику дивидендов в этой папке",
            "удали все документы за объявление дивидендов в этой папке",
            "удали все документы за субсидию в этой папке",
            "удали все документы по субсидии в этой папке",
            "удали все документы за получение субсидии в этой папке",
            "удали все документы за предоставление субсидии в этой папке",
            "удали все документы за возврат субсидии в этой папке",
            "удали все документы за субсидирование в этой папке",
            "удали все документы за субсидируемый проект в этой папке",
            "удали все документы за субсидированный проект в этой папке",
            "удали все документы за государственную субсидию в этой папке",
            "удали все документы за целевую субсидию в этой папке",
            "удали все документы за текущий дивиденд",
            "удали все документы за открытую субсидию",
            "удали все документы за текущую франшизу",
            "удали каждый документ за франшизу в этой папке",
            "удали все файлы за дивиденды в этой папке",
            "удали все документы каждого дивиденда в этой папке",
            "удали все документы по всем субсидиям в этой папке",
            "удали все документы дела А40-12345/2025 за франшизу",
            "удали все документы дела А40-12345/2025 за дивиденды",
            "удали все документы дела А40-12345/2025 за субсидию",
            "удали все документы за Франшизу в этой папке",
            "удали все документы за Дивиденд в этой папке",
            "удали все документы за Субсидию в этой папке",
        )
        for text in phrases:
            self.assertTrue(_wants_all(text), text)
            self.assertIsNone(parse_calendar_period_ru(text), text)
            self.assertTrue(franchise_blocks_bulk_document_mutation(text), text)
        for sample in (
            "удали все документы за франшизу в этой папке",
            "удали все документы за дивиденд в этой папке",
            "удали все документы за субсидию в этой папке",
            "удали все документы за текущий дивиденд",
            "удали все документы за открытую субсидию",
            "удали все документы за открытую франшизу в этой папке",
            "удали все документы за текущую франшизу",
        ):
            self.assertTrue(_pre_fix_selects_active_folder(sample), sample)

    def test_ordinal_is_not_a_document_id(self) -> None:
        samples = (
            "удали документы 1-го дивиденда",
            "удали документы 1-й дивиденд",
            "удали документы 1-му дивиденду",
            "удали документы 1-й франшизы",
            "удали документы 1-ю франшизу",
            "удали документы 1-й субсидии",
            "удали документы 1-ю субсидию",
            "удали документы 2-го дивиденда",
        )
        for text in samples:
            expected = [2] if "2-" in text else [1]
            self.assertEqual(_pre_fix_parse_ids(text), expected, text)
            self.assertEqual(_parse_ids_like_main(text), [], text)
            self.assertTrue(franchise_blocks_bulk_document_mutation(text), text)
        self.assertEqual(_pre_fix_parse_ids("удали документы 100 франшизы"), [100])
        self.assertEqual(_parse_ids_like_main("удали документы 100 франшизы"), [])
        self.assertEqual(_pre_fix_parse_ids("удали документы 100 субсидии"), [100])
        self.assertEqual(_parse_ids_like_main("удали документы 100 субсидии"), [])
        self.assertEqual(_pre_fix_parse_ids("удали документы 100 дивидендов"), [100])
        self.assertEqual(_parse_ids_like_main("удали документы 100 дивидендов"), [])
        self.assertEqual(_pre_fix_parse_ids("удали документы 12,5 франшизы"), [5, 12])
        self.assertEqual(_parse_ids_like_main("удали документы 12,5 франшизы"), [])
        self.assertEqual(_pre_fix_parse_ids("удали документы 12,5% франшизы"), [5, 12])
        self.assertEqual(_parse_ids_like_main("удали документы 12,5% франшизы"), [])
        self.assertEqual(_pre_fix_parse_ids("удали документы 12,5% субсидии"), [5, 12])
        self.assertEqual(_parse_ids_like_main("удали документы 12,5% субсидии"), [])
        self.assertEqual(_pre_fix_parse_ids("удали документы 214-го дивиденда"), [214])
        self.assertEqual(_parse_ids_like_main("удали документы 214-го дивиденда"), [])
        self.assertEqual(_pre_fix_parse_ids("удали документы 214-й субсидии"), [214])
        self.assertEqual(_parse_ids_like_main("удали документы 214-й субсидии"), [])
        self.assertEqual(_pre_fix_parse_ids("удали документы 214-го субсидирования"), [214])
        self.assertEqual(_parse_ids_like_main("удали документы 214-го субсидирования"), [])
        self.assertEqual(
            _parse_ids_like_main("удали документ 214 за 100 франшизы"),
            [214],
        )
        self.assertEqual(_parse_ids_like_main("удали документы 214 287"), [214, 287])
        self.assertEqual(_pre_fix_parse_ids("удали документы 1-й субсидиарной ответственности"), [1])
        self.assertEqual(_parse_ids_like_main("удали документы 1-й субсидиарной ответственности"), [1])
        self.assertEqual(_parse_ids_like_main("удали документы 1-го овердрафта"), [1])
        self.assertEqual(_parse_ids_like_main("удали документы 1-й ренты"), [1])
        self.assertEqual(_parse_ids_like_main("удали документы 1-го кредита"), [1])

    def test_move_all_with_scope_is_blocked(self) -> None:
        phrases = (
            "перенеси все документы дела А40-12345/2025 за франшизу в папку Архив",
            "перенеси все документы дела А40-12345/2025 за дивиденды в папку Архив",
            "перенеси все документы дела А40-12345/2025 за субсидию в папку Архив",
            "перенеси документ 1-го дивиденда в дело Архив",
            "перемести документ 1-й франшизы в дело Архив",
            "перемести документ 1-й субсидии в дело Архив",
        )
        for text in phrases:
            self.assertTrue(franchise_blocks_bulk_document_mutation(text), text)
        kept = "перенеси документ 214 за франшизу в дело Архив"
        kept_ids = [
            int(x)
            for x in re.findall(
                r"(?:документ|файл)\s+(\d+)",
                mask_franchise_ordinals(kept),
                flags=re.IGNORECASE,
            )
        ]
        self.assertEqual(kept_ids, [214])
        amount = "перенеси все документы дела А40-12345/2025 за 100 франшизы в папку Архив"
        masked = mask_franchise_ordinals(amount)
        self.assertIn("12345", masked)
        self.assertIn("2025", masked)
        self.assertNotIn("100", masked)

    def test_explicit_id_still_allowed(self) -> None:
        self.assertFalse(
            franchise_blocks_bulk_document_mutation(
                "удали документ 214 за франшизу",
                explicit_document_ids=[214],
            )
        )
        self.assertEqual(_parse_ids_like_main("удали документ 214 за франшизу"), [214])
        self.assertEqual(_parse_ids_like_main("удали документ 18 за дивиденд"), [18])
        self.assertEqual(_parse_ids_like_main("удали документ 18 за субсидию"), [18])
        self.assertEqual(
            _parse_ids_like_main("удали документы [12] [18] за дивиденд"),
            [12, 18],
        )
        self.assertEqual(_parse_ids_like_main("удали документ 214"), [214])
        self.assertEqual(_parse_ids_like_main("doc: 214 за субсидию"), [214])

    def test_plain_folder_commands_are_not_scoped(self) -> None:
        for text in (
            "удали все документы в этой папке",
            "удали все документы в текущей папке",
            "удали все документы в открытой папке",
            "удали все документы в этой папке без франшизы",
            "удали все документы в этой папке без дивидендов",
            "удали все документы в этой папке без субсидии",
            "удали все документы в папке «Франшиза»",
            "удали все документы в папке Франшиза",
            "удали все документы в папке Дивиденды",
            "удали все документы в папке Субсидия",
            "удали все документы в папке «Дивидендная политика»",
            "удали все документы из папки Франшиза",
            "перенеси все документы в папку Франшиза",
            "перенеси все документы в папку Дивиденды",
            "перенеси все документы в папку Субсидия",
            "удали все документы по делу Франшиза",
            "удали все документы по делу Дивиденды",
            "удали все документы по делу Субсидия",
            "удали все документы по делу Банкротство Эмиль",
            "удали все документы дела А53-13969/2026",
            "удали все документы по Вартанов Эмиль Валерьевич",
            "удали все документы за банкротство в этой папке",
            "удали все документы за платеж в этой папке",
            "удали все документы за кредит в этой папке",
            "удали все документы за овердрафт в этой папке",
            "удали все документы за ренту в этой папке",
            "удали все документы за ссуду в этой папке",
            "удали все документы за субсидиарную ответственность в этой папке",
            "удали все документы за субсидиарку в этой папке",
            "удали все документы за субсидиарный иск в этой папке",
            "удали все документы за франчайзинг в этой папке",
            "удали все документы за франчайзи в этой папке",
            "удали все документы за франчайзера в этой папке",
            "удали все документы за договор в этой папке",
            "удали все документы за график в этой папке",
            "удали все документы о том в этой папке",
            "удали все документы за тем в этой папке",
            "удали все документы после открытия",
            "удали все документы по текущей задолженности",
            "удали документы 1-го приказа",
            "удали документы 1-й субсидиарной ответственности",
            "удали документы 1-го овердрафта",
            "перенеси все документы в папку Архив",
        ):
            self.assertFalse(looks_like_franchise_scoped_document_request(text), text)
            self.assertFalse(franchise_blocks_bulk_document_mutation(text), text)

    def test_genitive_document_forms_are_scoped(self) -> None:
        for text in (
            "удали документы франшизы в этой папке",
            "удали документы дивидендов в этой папке",
            "удали документы субсидии в этой папке",
            "удали документы субсидирования в этой папке",
            "удали все документы за первый дивиденд в этой папке",
            "удали все документы за первую франшизу в этой папке",
            "удали все документы за первую субсидию в этой папке",
            "удали все документы за эту субсидию в этой папке",
            "удали все документы за тот дивиденд в этой папке",
            "удали все документы о той франшизе в этой папке",
        ):
            self.assertTrue(franchise_blocks_bulk_document_mutation(text), text)

    def test_inflected_forms_are_scoped(self) -> None:
        phrases = (
            "за франшизу",
            "за франшизы",
            "по франшизе",
            "о франшизе",
            "за франшизой",
            "за франшизою",
            "за франшизам",
            "за франшизами",
            "за франшизах",
            "за франшиз",
            "за франшизный взнос",
            "за франшизную программу",
            "за франшизное соглашение",
            "за дивиденд",
            "за дивиденда",
            "за дивиденду",
            "за дивидендом",
            "по дивиденду",
            "о дивиденде",
            "за дивиденды",
            "за дивидендов",
            "за дивидендам",
            "за дивидендами",
            "за дивидендах",
            "за дивидендный доход",
            "за дивидендную политику",
            "за субсидию",
            "за субсидии",
            "по субсидии",
            "о субсидии",
            "за субсидией",
            "за субсидиею",
            "за субсидиям",
            "за субсидиями",
            "за субсидиях",
            "за субсидий",
            "за субсидирование",
            "за субсидирования",
            "по субсидированию",
            "о субсидировании",
            "за субсидированием",
            "за субсидируемый проект",
            "за субсидируемого заемщика",
            "за субсидированный проект",
            "за субсидированную программу",
            "за выплату дивидендов",
            "за невыплату дивидендов",
            "за условие франшизы",
            "за безусловную франшизу",
        )
        for text in phrases:
            self.assertTrue(
                looks_like_franchise_scoped_document_request(f"удали все документы {text} в этой папке"),
                text,
            )

    def test_main_wires_the_guard_before_the_wipe(self) -> None:
        source = (Path(__file__).resolve().parent / "app" / "main.py").read_text(encoding="utf-8")
        self.assertIn("franchise_blocks_bulk_document_mutation", source)
        self.assertIn("mask_franchise_ordinals", source)
        self.assertIn("DELETE_REFUSED_REPLY", source)
        self.assertIn("MOVE_REFUSED_REPLY", source)
        delete_fn = source.split("def handle_delete_documents_chat", 1)[1].split("\ndef ", 1)[0]
        self.assertLess(
            delete_fn.index("franchise_blocks_bulk_document_mutation"),
            delete_fn.index("wants_all = any"),
        )
        parse_fn = source.split("def parse_document_ids_for_delete_command", 1)[1].split("\ndef ", 1)[0]
        self.assertLess(parse_fn.index("mask_franchise_ordinals"), parse_fn.index("re.search"))
        move_fn = source.split("def move_documents_by_chat_command", 1)[1].split("\ndef ", 1)[0]
        self.assertIn("mask_franchise_ordinals", move_fn)
        bulk = source.split("if looks_like_move_all_from_active_case_to_folder(text):", 1)[1]
        self.assertLess(
            bulk.index("franchise_blocks_bulk_document_mutation"),
            bulk.index("execute_move_all_documents_to_case_folder"),
        )


if __name__ == "__main__":
    unittest.main()
