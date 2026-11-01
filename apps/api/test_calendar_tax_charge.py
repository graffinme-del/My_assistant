"""Tax-charge chat must not wipe a folder.

Pre-fix, handle_delete_documents_chat treated «все документы» plus «в этой папке»
(or a case number, or «текущ» / «открыт») as wipe-the-folder and parsed
«2-НДФЛ», «6% УСН», «13% НДФЛ», and «1-й недоимки» as document ids. The
calendar period parser does not recognize these phrases.

«налог» / «НДС» / «инкассо» are a separate guard. A folder titled «НДФЛ» is
not this guard. «без НДФЛ» is not this guard. «доначислить» is not
«доначисление». «искусный» is not «УСН».
"""

from __future__ import annotations

import re
import unittest
from pathlib import Path

from app.calendar_tax_charge import (
    looks_like_tax_charge_scoped_document_request,
    mask_tax_charge_ordinals,
    tax_charge_blocks_bulk_document_mutation,
)
from app.ru_date_range import parse_calendar_period_ru


def _parse_ids_like_main(text: str) -> list[int]:
    raw = text or ""
    ids = [int(x) for x in re.findall(r"\[(\d+)\]", raw)]
    ids.extend(int(x) for x in re.findall(r"(?i)\bdoc[.:]?\s*(\d+)\b", raw))
    if ids:
        return sorted(set(ids))
    safe = mask_tax_charge_ordinals(raw)
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


class TaxChargeScopeTests(unittest.TestCase):
    def test_folder_wipe_trigger_is_not_a_calendar_period(self) -> None:
        phrases = (
            "удали все документы за НДФЛ в этой папке",
            "удали все документы по НДФЛ в этой папке",
            "удали все документы об НДФЛ в этой папке",
            "удали все документы за 2-НДФЛ в этой папке",
            "удали все документы за 3-НДФЛ в этой папке",
            "удали все документы за 6-НДФЛ в этой папке",
            "удали все документы за справку 2-НДФЛ в этой папке",
            "удали все документы за 13% НДФЛ в этой папке",
            "удали все документы за уплату НДФЛ в этой папке",
            "удали все документы за ФНС в этой папке",
            "удали все документы по требованиям ФНС в этой папке",
            "удали все документы в ФНС в этой папке",
            "удали все документы из ФНС в этой папке",
            "удали все документы за УСН в этой папке",
            "удали все документы на УСН в этой папке",
            "удали все документы по УСНО в этой папке",
            "удали все документы за 6% УСН в этой папке",
            "удали все документы за 15% УСНО в этой папке",
            "удали все документы за недоимку в этой папке",
            "удали все документы по недоимке в этой папке",
            "удали все документы за недоимки в этой папке",
            "удали все документы за срок недоимки в этой папке",
            "удали все документы за текущую недоимку",
            "удали все документы за открытую недоимку",
            "удали все документы за доначисление в этой папке",
            "удали все документы по доначислению в этой папке",
            "удали все документы за доначисления в этой папке",
            "удали все документы за доначисленный налог в этой папке",
            "удали все документы за недоимочную задолженность в этой папке",
            "удали каждый документ за НДФЛ в этой папке",
            "удали все файлы за недоимку в этой папке",
            "удали все документы дела А40-12345/2025 за НДФЛ",
            "удали все документы дела А40-12345/2025 за недоимку",
            "удали все документы дела А40-12345/2025 по доначислению",
            "удали все документы за «НДФЛ» в этой папке",
            "удали все документы за «2-НДФЛ» в этой папке",
            "удали все документы во время недоимки в этой папке",
            "удали все документы до доначисления в этой папке",
            "удали все документы в рамках НДФЛ в этой папке",
            "удали все документы по результатам ФНС в этой папке",
            "удали все документы с недоимкой в этой папке",
            "удали все документы после доначисления в этой папке",
        )
        for text in phrases:
            self.assertTrue(_wants_all(text), text)
            self.assertIsNone(parse_calendar_period_ru(text), text)
            self.assertTrue(tax_charge_blocks_bulk_document_mutation(text), text)
        for sample in (
            "удали все документы за НДФЛ в этой папке",
            "удали все документы за 2-НДФЛ в этой папке",
            "удали все документы за недоимку в этой папке",
            "удали все документы за текущую недоимку",
            "удали все документы за открытую недоимку",
            "удали все документы за ФНС в этой папке",
            "удали все документы по УСНО в этой папке",
        ):
            self.assertTrue(_pre_fix_selects_active_folder(sample), sample)

    def test_ordinal_is_not_a_document_id(self) -> None:
        samples = (
            ("удали документы 2-НДФЛ", [2]),
            ("удали документы 3-НДФЛ", [3]),
            ("удали документы 6-НДФЛ", [6]),
            ("удали документы 2 НДФЛ", [2]),
            ("удали документы 2НДФЛ", [2]),
            ("удали документы 1-й недоимки", [1]),
            ("удали документы 1-го доначисления", [1]),
            ("удали документы 1 УСН", [1]),
            ("удали документы 1 ФНС", [1]),
        )
        for text, expected in samples:
            self.assertEqual(_pre_fix_parse_ids(text), expected, text)
            self.assertEqual(_parse_ids_like_main(text), [], text)
            self.assertTrue(tax_charge_blocks_bulk_document_mutation(text), text)
        self.assertEqual(_pre_fix_parse_ids("удали документы 100 недоимок"), [100])
        self.assertEqual(_parse_ids_like_main("удали документы 100 недоимок"), [])
        self.assertEqual(_pre_fix_parse_ids("удали документы 100 УСН"), [100])
        self.assertEqual(_parse_ids_like_main("удали документы 100 УСН"), [])
        self.assertEqual(_pre_fix_parse_ids("удали документы 12,5% недоимки"), [5, 12])
        self.assertEqual(_parse_ids_like_main("удали документы 12,5% недоимки"), [])
        self.assertEqual(_pre_fix_parse_ids("удали документы 12.5% доначисления"), [12])
        self.assertEqual(_parse_ids_like_main("удали документы 12.5% доначисления"), [])
        self.assertEqual(_pre_fix_parse_ids("удали документы 13% НДФЛ"), [13])
        self.assertEqual(_parse_ids_like_main("удали документы 13% НДФЛ"), [])
        self.assertEqual(_pre_fix_parse_ids("удали документы 6% УСН"), [6])
        self.assertEqual(_parse_ids_like_main("удали документы 6% УСН"), [])
        self.assertEqual(_pre_fix_parse_ids("удали документы 15% УСНО"), [15])
        self.assertEqual(_parse_ids_like_main("удали документы 15% УСНО"), [])
        self.assertEqual(_pre_fix_parse_ids("удали документы 214-го доначисления"), [214])
        self.assertEqual(_parse_ids_like_main("удали документы 214-го доначисления"), [])
        self.assertEqual(_pre_fix_parse_ids("удали документы 214-й ФНС"), [214])
        self.assertEqual(_parse_ids_like_main("удали документы 214-й ФНС"), [])
        self.assertEqual(_parse_ids_like_main("удали документ 214 за 2-НДФЛ"), [214])
        self.assertEqual(_parse_ids_like_main("удали документ 214 за НДФЛ"), [214])
        self.assertEqual(_parse_ids_like_main("удали документы 214 287"), [214, 287])
        self.assertEqual(_parse_ids_like_main("удали документы 214 287 за недоимку"), [214, 287])
        self.assertEqual(_parse_ids_like_main("удали документы 6% НДС"), [6])
        self.assertEqual(_parse_ids_like_main("удали документы 1-й налога"), [1])
        self.assertEqual(_parse_ids_like_main("удали документы 1-е отложения"), [1])

    def test_move_all_with_scope_is_blocked(self) -> None:
        phrases = (
            "перенеси все документы дела А40-12345/2025 за НДФЛ в папку Архив",
            "перенеси все документы дела А40-12345/2025 за 2-НДФЛ в папку Архив",
            "перенеси все документы дела А40-12345/2025 за недоимку в папку Архив",
            "перенеси все документы дела А40-12345/2025 по доначислению в папку Архив",
            "перенеси все документы дела А40-12345/2025 за ФНС в папку Архив",
            "перенеси все документы дела А40-12345/2025 на УСН в папку Архив",
            "перенеси документ 2-НДФЛ в дело Архив",
            "перемести документ 6-НДФЛ в дело Архив",
            "перенеси документ 1-й недоимки в дело Архив",
        )
        for text in phrases:
            self.assertTrue(tax_charge_blocks_bulk_document_mutation(text), text)
        kept = "перенеси документ 214 за НДФЛ в дело Архив"
        kept_ids = [
            int(x)
            for x in re.findall(
                r"(?:документ|файл)\s+(\d+)",
                mask_tax_charge_ordinals(kept),
                flags=re.IGNORECASE,
            )
        ]
        self.assertEqual(kept_ids, [214])
        amount = "перенеси все документы дела А40-12345/2025 за 100 недоимок в папку Архив"
        masked = mask_tax_charge_ordinals(amount)
        self.assertIn("12345", masked)
        self.assertIn("2025", masked)
        self.assertNotIn("100", masked)
        form = "перенеси все документы дела А40-12345/2025 за 2-НДФЛ в папку Архив"
        masked_form = mask_tax_charge_ordinals(form)
        self.assertIn("12345", masked_form)
        self.assertIn("2025", masked_form)
        self.assertNotRegex(masked_form, r"(?<!\d)2(?!\d)")

    def test_explicit_id_still_allowed(self) -> None:
        self.assertFalse(
            tax_charge_blocks_bulk_document_mutation(
                "удали документ 214 за НДФЛ",
                explicit_document_ids=[214],
            )
        )
        self.assertEqual(_parse_ids_like_main("удали документ 214 за НДФЛ"), [214])
        self.assertEqual(_parse_ids_like_main("удали документ 214 за 2-НДФЛ"), [214])
        self.assertEqual(_parse_ids_like_main("удали документ 18 по недоимке"), [18])
        self.assertEqual(_parse_ids_like_main("удали документы [12] [18] за ФНС"), [12, 18])
        self.assertEqual(_parse_ids_like_main("удали документ 214"), [214])
        self.assertEqual(_parse_ids_like_main("doc: 214 за УСН"), [214])

    def test_plain_folder_commands_are_not_scoped(self) -> None:
        for text in (
            "удали все документы в этой папке",
            "удали все документы из этой папки",
            "удали все документы в текущей папке",
            "удали все документы в открытой папке",
            "удали все документы это дело",
            "удали все документы дела А40-12345/2025",
            "удали все документы в папке НДФЛ",
            "удали все документы в папке «ФНС»",
            "удали все документы в папке УСН",
            "удали все документы по делу Недоимка",
            "удали все документы по делу Доначисление",
            "удали все документы без НДФЛ в этой папке",
            "удали все документы без 2-НДФЛ в этой папке",
            "удали все документы без недоимки в этой папке",
            "удали все документы без доначисления в этой папке",
            "удали все документы за налог в этой папке",
            "удали все документы за НДС в этой папке",
            "удали все документы за инкассо в этой папке",
            "удали все документы за отложение в этой папке",
            "удали все документы за банкротство в этой папке",
            "удали все документы за искусный перевод в этой папке",
            "удали все документы, которые надо доначислить, в этой папке",
            "удали все документы за доначислять в этой папке",
            "удали все документы за Недоимкину в этой папке",
            "удали все документы за Доначисленову в этой папке",
            "удали все документы за Уснову в этой папке",
            "удали все документы за период в этой папке",
            "перенеси все документы в папку Архив",
            "перенеси все документы в папку НДФЛ",
            "собери все документы в папку ФНС по Гримме",
            "удали документ 214",
            "удали все документы по делу УСН",
        ):
            self.assertFalse(looks_like_tax_charge_scoped_document_request(text), text)
            self.assertFalse(tax_charge_blocks_bulk_document_mutation(text), text)

    def test_inflected_forms_are_scoped(self) -> None:
        phrases = (
            "за НДФЛ",
            "по НДФЛ",
            "за 2-НДФЛ",
            "за 3-НДФЛ",
            "за 6-НДФЛ",
            "за справку 2-НДФЛ",
            "за 13% НДФЛ",
            "за ФНС",
            "в ФНС",
            "по требованиям ФНС",
            "за УСН",
            "на УСН",
            "по УСНО",
            "за 6% УСН",
            "за недоимку",
            "по недоимке",
            "за недоимкой",
            "за недоимок",
            "за недоимки",
            "за текущую недоимку",
            "за открытую недоимку",
            "за доначисление",
            "по доначислению",
            "за доначислением",
            "за доначисления",
            "за доначисленный",
            "за первое доначисление",
            "в рамках НДФЛ",
            "до доначисления",
        )
        for text in phrases:
            self.assertTrue(
                looks_like_tax_charge_scoped_document_request(f"удали все документы {text} в этой папке"),
                text,
            )

    def test_main_wires_the_guard_before_the_wipe(self) -> None:
        source = (Path(__file__).resolve().parent / "app" / "main.py").read_text(encoding="utf-8")
        self.assertIn("tax_charge_blocks_bulk_document_mutation", source)
        self.assertIn("mask_tax_charge_ordinals", source)
        self.assertIn("DELETE_REFUSED_REPLY", source)
        self.assertIn("MOVE_REFUSED_REPLY", source)
        delete_fn = source.split("def handle_delete_documents_chat", 1)[1].split("\ndef ", 1)[0]
        self.assertLess(
            delete_fn.index("tax_charge_blocks_bulk_document_mutation"),
            delete_fn.index("wants_all = any"),
        )
        wipe = delete_fn.split("wants_all = any", 1)[1]
        self.assertIn("delete_documents_hard", wipe)
        parse_fn = source.split("def parse_document_ids_for_delete_command", 1)[1].split("\ndef ", 1)[0]
        self.assertLess(parse_fn.index("mask_tax_charge_ordinals"), parse_fn.index("re.search"))
        move_fn = source.split("def move_documents_by_chat_command", 1)[1].split("\ndef ", 1)[0]
        self.assertIn("mask_tax_charge_ordinals", move_fn)
        bulk = source.split("if looks_like_move_all_from_active_case_to_folder(text):", 1)[1]
        self.assertLess(
            bulk.index("tax_charge_blocks_bulk_document_mutation"),
            bulk.index("execute_move_all_documents_to_case_folder"),
        )


if __name__ == "__main__":
    unittest.main()
