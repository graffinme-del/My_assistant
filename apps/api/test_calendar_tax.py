"""Tax and collection chat must not wipe a folder.

Pre-fix, handle_delete_documents_chat treated «все документы» plus «в этой папке»
(or a case number, or «текущ» / «открыт») as wipe-the-folder and parsed
«1-й налога» as document id 1. The calendar period parser does not recognize
these phrases.

A folder titled «Налог», «Инкассо», or «НДС» is not this guard.
«без налога» is not this guard. Bare «банкротство» is not this guard.
«инкассация» is not «инкассо». «наложение» is not «налог».
"""

from __future__ import annotations

import re
import unittest
from pathlib import Path

from app.calendar_tax import (
    looks_like_tax_scoped_document_request,
    mask_tax_ordinals,
    tax_blocks_bulk_document_mutation,
)
from app.ru_date_range import parse_calendar_period_ru


def _parse_ids_like_main(text: str) -> list[int]:
    raw = text or ""
    ids = [int(x) for x in re.findall(r"\[(\d+)\]", raw)]
    ids.extend(int(x) for x in re.findall(r"(?i)\bdoc[.:]?\s*(\d+)\b", raw))
    if ids:
        return sorted(set(ids))
    safe = mask_tax_ordinals(raw)
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


class TaxScopeTests(unittest.TestCase):
    def test_folder_wipe_trigger_is_not_a_calendar_period(self) -> None:
        phrases = (
            "удали все документы за налог в этой папке",
            "удали все документы по налогу в этой папке",
            "удали все документы о налоге в этой папке",
            "удали все документы за уплату налога в этой папке",
            "удали все документы за налоговую проверку в этой папке",
            "удали все документы за налогообложение в этой папке",
            "удали все документы за налогоплательщика в этой папке",
            "удали все документы за неналогооблагаемую операцию в этой папке",
            "удали все документы за декларацию НДС в этой папке",
            "удали все документы за инкассо в этой папке",
            "удали все документы по инкассо в этой папке",
            "удали все документы за инкассовое поручение в этой папке",
            "удали все документы за НДС в этой папке",
            "удали все документы по НДС в этой папке",
            "удали все документы об НДС в этой папке",
            "удали все документы за текущий налог",
            "удали все документы за текущее инкассо",
            "удали все документы за открытую налоговую",
            "удали все документы за открытое инкассо",
            "удали каждый документ за налог в этой папке",
            "удали все файлы за НДС в этой папке",
            "удали все документы дела А40-12345/2025 за налог",
            "удали все документы дела А40-12345/2025 за инкассо",
            "удали все документы дела А40-12345/2025 за НДС",
            "удали все документы за Налог в этой папке",
            "удали все документы во время налогообложения в этой папке",
            "удали все документы во время инкассо в этой папке",
            "удали все документы за «налог» в этой папке",
            "удали все документы за «договор инкассо» в этой папке",
            "удали все документы за ставку налога в этой папке",
        )
        for text in phrases:
            self.assertTrue(_wants_all(text), text)
            self.assertIsNone(parse_calendar_period_ru(text), text)
            self.assertTrue(tax_blocks_bulk_document_mutation(text), text)
        for sample in (
            "удали все документы за налог в этой папке",
            "удали все документы за инкассо в этой папке",
            "удали все документы за НДС в этой папке",
            "удали все документы за текущий налог",
            "удали все документы за текущее инкассо",
            "удали все документы за открытую налоговую в этой папке",
            "удали все документы за открытое инкассо",
        ):
            self.assertTrue(_pre_fix_selects_active_folder(sample), sample)

    def test_ordinal_is_not_a_document_id(self) -> None:
        samples = (
            "удали документы 1-й налога",
            "удали документы 1-го налога",
            "удали документы 1-й инкассо",
            "удали документы 1-й НДС",
            "удали документы 1-го налогоплательщика",
            "удали документы 2-й налоговой",
        )
        for text in samples:
            expected = [2] if "2-" in text else [1]
            self.assertEqual(_pre_fix_parse_ids(text), expected, text)
            self.assertEqual(_parse_ids_like_main(text), [], text)
            self.assertTrue(tax_blocks_bulk_document_mutation(text), text)
        self.assertEqual(_pre_fix_parse_ids("удали документы 100 налога"), [100])
        self.assertEqual(_parse_ids_like_main("удали документы 100 налога"), [])
        self.assertEqual(_pre_fix_parse_ids("удали документы 100 налогов"), [100])
        self.assertEqual(_parse_ids_like_main("удали документы 100 налогов"), [])
        self.assertEqual(_pre_fix_parse_ids("удали документы 100 инкассо"), [100])
        self.assertEqual(_parse_ids_like_main("удали документы 100 инкассо"), [])
        self.assertEqual(_pre_fix_parse_ids("удали документы 100 НДС"), [100])
        self.assertEqual(_parse_ids_like_main("удали документы 100 НДС"), [])
        self.assertEqual(_pre_fix_parse_ids("удали документы 12,5% налога"), [5, 12])
        self.assertEqual(_parse_ids_like_main("удали документы 12,5% налога"), [])
        self.assertEqual(_pre_fix_parse_ids("удали документы 12.5% инкассо"), [12])
        self.assertEqual(_parse_ids_like_main("удали документы 12.5% инкассо"), [])
        self.assertEqual(_pre_fix_parse_ids("удали документы 12,5% НДС"), [5, 12])
        self.assertEqual(_parse_ids_like_main("удали документы 12,5% НДС"), [])
        self.assertEqual(_pre_fix_parse_ids("удали документы 214-го налога"), [214])
        self.assertEqual(_parse_ids_like_main("удали документы 214-го налога"), [])
        self.assertEqual(_pre_fix_parse_ids("удали документы 214-й инкассо"), [214])
        self.assertEqual(_parse_ids_like_main("удали документы 214-й инкассо"), [])
        self.assertEqual(_pre_fix_parse_ids("удали документы 214-го налогоплательщика"), [214])
        self.assertEqual(_parse_ids_like_main("удали документы 214-го налогоплательщика"), [])
        self.assertEqual(_pre_fix_parse_ids("удали документы 1 налога"), [1])
        self.assertEqual(_parse_ids_like_main("удали документы 1 налога"), [])
        self.assertEqual(_parse_ids_like_main("удали документ 214 за 100 налога"), [214])
        self.assertEqual(_parse_ids_like_main("удали документы 214 287"), [214, 287])
        self.assertEqual(_parse_ids_like_main("удали документы 214 287 за налог"), [214, 287])
        self.assertEqual(_parse_ids_like_main("удали документы 1-й поставки"), [1])
        self.assertEqual(_parse_ids_like_main("удали документы 1-го дарения"), [1])

    def test_move_all_with_scope_is_blocked(self) -> None:
        phrases = (
            "перенеси все документы дела А40-12345/2025 за налог в папку Архив",
            "перенеси все документы дела А40-12345/2025 за инкассо в папку Архив",
            "перенеси все документы дела А40-12345/2025 за НДС в папку Архив",
            "перенеси все документы дела А40-12345/2025 за налогоплательщика в папку Архив",
            "перенеси все документы дела А40-12345/2025 за уплату налога в папку Архив",
            "перенеси документ 1-й налога в дело Архив",
            "перемести документ 1-й НДС в дело Архив",
        )
        for text in phrases:
            self.assertTrue(tax_blocks_bulk_document_mutation(text), text)
        kept = "перенеси документ 214 за налог в дело Архив"
        kept_ids = [
            int(x)
            for x in re.findall(
                r"(?:документ|файл)\s+(\d+)",
                mask_tax_ordinals(kept),
                flags=re.IGNORECASE,
            )
        ]
        self.assertEqual(kept_ids, [214])
        amount = "перенеси все документы дела А40-12345/2025 за 100 налога в папку Архив"
        masked = mask_tax_ordinals(amount)
        self.assertIn("12345", masked)
        self.assertIn("2025", masked)
        self.assertNotIn("100", masked)

    def test_explicit_id_still_allowed(self) -> None:
        self.assertFalse(
            tax_blocks_bulk_document_mutation(
                "удали документ 214 за налог",
                explicit_document_ids=[214],
            )
        )
        self.assertEqual(_parse_ids_like_main("удали документ 214 за налог"), [214])
        self.assertEqual(_parse_ids_like_main("удали документ 214 за инкассо"), [214])
        self.assertEqual(_parse_ids_like_main("удали документ 18 за НДС"), [18])
        self.assertEqual(_parse_ids_like_main("удали документы [12] [18] за налог"), [12, 18])
        self.assertEqual(_parse_ids_like_main("удали документ 214"), [214])
        self.assertEqual(_parse_ids_like_main("doc: 214 за налог"), [214])

    def test_plain_folder_commands_are_not_scoped(self) -> None:
        for text in (
            "удали все документы в этой папке",
            "удали все документы в текущей папке",
            "удали все документы в открытой папке",
            "удали все документы дела А40-12345/2025",
            "удали все документы в папке Налог",
            "удали все документы в папке Инкассо",
            "удали все документы в папке НДС",
            "удали все документы в папке «Налог»",
            "удали все документы в папке «Налоговая проверка»",
            "удали все документы без налога в этой папке",
            "удали все документы без инкассо в этой папке",
            "удали все документы без НДС в этой папке",
            "удали все документы за банкротство в этой папке",
            "удали все документы за наложение ареста в этой папке",
            "удали все документы за инкассацию в этой папке",
            "удали все документы за сделку в этой папке",
            "удали все документы за оспаривание в этой папке",
            "удали все документы за поставку в этой папке",
            "удали все документы за дарение в этой папке",
            "перенеси все документы в папку Архив",
            "удали документ 214",
            "удали все документы по делу Налог",
            "удали все документы по делу НДС",
        ):
            self.assertFalse(looks_like_tax_scoped_document_request(text), text)
            self.assertFalse(tax_blocks_bulk_document_mutation(text), text)

    def test_inflected_forms_are_scoped(self) -> None:
        phrases = (
            "за налог",
            "за налога",
            "по налогу",
            "о налоге",
            "за налогом",
            "за налоги",
            "за налогов",
            "за налогами",
            "за налогах",
            "за налоговую проверку",
            "за налоговый орган",
            "за налоговым вычетом",
            "за налогообложение",
            "по налогообложению",
            "за налогообложением",
            "за налогоплательщика",
            "за налогоплательщику",
            "за налогоплательщиком",
            "за налогоплательщиков",
            "за неналогооблагаемую операцию",
            "за инкассо",
            "по инкассо",
            "за инкассовое поручение",
            "за инкассового поручения",
            "за инкассовым поручением",
            "за НДС",
            "по НДС",
            "об НДС",
            "за декларацию НДС",
            "за ставку налога",
            "за уплату налога",
            "за сумму налога",
        )
        for text in phrases:
            self.assertTrue(
                looks_like_tax_scoped_document_request(f"удали все документы {text} в этой папке"),
                text,
            )

    def test_main_wires_the_guard_before_the_wipe(self) -> None:
        source = (Path(__file__).resolve().parent / "app" / "main.py").read_text(encoding="utf-8")
        self.assertIn("tax_blocks_bulk_document_mutation", source)
        self.assertIn("mask_tax_ordinals", source)
        self.assertIn("DELETE_REFUSED_REPLY", source)
        self.assertIn("MOVE_REFUSED_REPLY", source)
        delete_fn = source.split("def handle_delete_documents_chat", 1)[1].split("\ndef ", 1)[0]
        self.assertLess(
            delete_fn.index("tax_blocks_bulk_document_mutation"),
            delete_fn.index("wants_all = any"),
        )
        wipe = delete_fn.split("wants_all = any", 1)[1]
        self.assertIn("delete_documents_hard", wipe)
        parse_fn = source.split("def parse_document_ids_for_delete_command", 1)[1].split("\ndef ", 1)[0]
        self.assertLess(parse_fn.index("mask_tax_ordinals"), parse_fn.index("re.search"))
        move_fn = source.split("def move_documents_by_chat_command", 1)[1].split("\ndef ", 1)[0]
        self.assertIn("mask_tax_ordinals", move_fn)
        bulk = source.split("if looks_like_move_all_from_active_case_to_folder(text):", 1)[1]
        self.assertLess(
            bulk.index("tax_blocks_bulk_document_mutation"),
            bulk.index("execute_move_all_documents_to_case_folder"),
        )


if __name__ == "__main__":
    unittest.main()
