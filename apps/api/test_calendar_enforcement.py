"""Writ / interim-measures / creditors'-meeting chat must not wipe a folder.

Pre-fix, handle_delete_documents_chat treated «все документы» plus «в этой папке»
(or a case number) as wipe-the-folder and parsed «1-го исполнительного листа»
as document id 1. The calendar period parser does not recognize these phrases.

«мировое соглашение», «судебный приказ», and «исполнительное производство»
belong to other guards. A folder titled «Исполнительный лист» is not this guard.
Bare «банкротство» is not this guard.
"""

from __future__ import annotations

import re
import unittest
from pathlib import Path

from app.calendar_enforcement import (
    enforcement_blocks_bulk_document_mutation,
    looks_like_enforcement_scoped_document_request,
    mask_enforcement_ordinals,
)
from app.ru_date_range import parse_calendar_period_ru


def _parse_ids_like_main(text: str) -> list[int]:
    raw = text or ""
    ids = [int(x) for x in re.findall(r"\[(\d+)\]", raw)]
    ids.extend(int(x) for x in re.findall(r"(?i)\bdoc[.:]?\s*(\d+)\b", raw))
    if ids:
        return sorted(set(ids))
    safe = mask_enforcement_ordinals(raw)
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


class EnforcementScopeTests(unittest.TestCase):
    def test_folder_wipe_trigger_is_not_a_calendar_period(self) -> None:
        phrases = (
            "удали все документы за исполнительный лист в этой папке",
            "удали все документы по исполнительному листу в этой папке",
            "удали все документы по исполнительным листам в этой папке",
            "удали все документы от исполнительного листа в этой папке",
            "удали все документы для исполнительного листа в этой папке",
            "удали все документы за Исполнительный лист в этой папке",
            "удали все документы за выдачу исполнительного листа в этой папке",
            "удали все документы за дубликат исполнительного листа в этой папке",
            "удали все документы за текущий исполнительный лист в этой папке",
            "удали все документы за открытый исполнительный лист в этой папке",
            "удали все документы за исполнительные листы в этой папке",
            "удали все документы за обеспечительные меры в этой папке",
            "удали все документы по обеспечительным мерам в этой папке",
            "удали все документы за отмену обеспечительных мер в этой папке",
            "удали все документы за принятие обеспечительных мер в этой папке",
            "удали все документы за введение обеспечительных мер в этой папке",
            "удали все документы за обеспечительную меру в этой папке",
            "удали все документы во время обеспечительных мер в этой папке",
            "удали все документы за собрание кредиторов в этой папке",
            "удали все документы по собранию кредиторов в этой папке",
            "удали все документы за протокол собрания кредиторов в этой папке",
            "удали все документы за собрание комитета кредиторов в этой папке",
            "удали все документы за комитет кредиторов в этой папке",
            "удали все документы по комитету кредиторов в этой папке",
            "удали все документы за собрание всех кредиторов в этой папке",
            "удали все документы за первое собрание кредиторов в этой папке",
            "удали все документы за внеочередное собрание кредиторов в этой папке",
            "удали все документы во время собрания кредиторов в этой папке",
            "удали каждый документ за исполнительный лист в этой папке",
            "удали все файлы за обеспечительные меры в этой папке",
            "удали все документы дела А40-12345/2025 за исполнительный лист",
            "удали все документы дела А40-12345/2025 за обеспечительные меры",
            "удали все документы дела А40-12345/2025 за собрание кредиторов",
        )
        for text in phrases:
            self.assertTrue(_wants_all(text), text)
            self.assertIsNone(parse_calendar_period_ru(text), text)
            self.assertTrue(enforcement_blocks_bulk_document_mutation(text), text)
        self.assertTrue(
            _pre_fix_selects_active_folder(
                "удали все документы за исполнительный лист в этой папке"
            )
        )
        self.assertTrue(
            _pre_fix_selects_active_folder(
                "удали все документы за обеспечительные меры в этой папке"
            )
        )
        self.assertTrue(
            _pre_fix_selects_active_folder(
                "удали все документы за собрание кредиторов в этой папке"
            )
        )
        self.assertTrue(
            _pre_fix_selects_active_folder(
                "удали все документы за текущий исполнительный лист в этой папке"
            )
        )

    def test_ordinal_is_not_a_document_id(self) -> None:
        samples = (
            "удали документы 1-го исполнительного листа",
            "удали документы 1-й исполнительный лист",
            "удали документы 1-му исполнительному листу",
            "удали документы 1-х обеспечительных мер",
            "удали документы 1-е обеспечительные меры",
            "удали документы 1-го собрания кредиторов",
            "удали документы 2-го исполнительного листа",
        )
        for text in samples:
            expected = [2] if "2-" in text else [1]
            self.assertEqual(_pre_fix_parse_ids(text), expected, text)
            self.assertEqual(_parse_ids_like_main(text), [], text)
            self.assertTrue(enforcement_blocks_bulk_document_mutation(text), text)
        self.assertEqual(_pre_fix_parse_ids("удали документы 100 исполнительного листа"), [100])
        self.assertEqual(_parse_ids_like_main("удали документы 100 исполнительного листа"), [])
        self.assertEqual(_pre_fix_parse_ids("удали документы 100 обеспечительных мер"), [100])
        self.assertEqual(_parse_ids_like_main("удали документы 100 обеспечительных мер"), [])
        self.assertEqual(_pre_fix_parse_ids("удали документы 100 собрания кредиторов"), [100])
        self.assertEqual(_parse_ids_like_main("удали документы 100 собрания кредиторов"), [])
        self.assertEqual(_pre_fix_parse_ids("удали документы 12,5 исполнительного листа"), [5, 12])
        self.assertEqual(_parse_ids_like_main("удали документы 12,5 исполнительного листа"), [])
        self.assertEqual(
            _parse_ids_like_main("удали документ 214 за 100 исполнительного листа"),
            [214],
        )
        self.assertEqual(_parse_ids_like_main("удали документы 214 287"), [214, 287])

    def test_move_all_with_scope_is_blocked(self) -> None:
        phrases = (
            "перенеси все документы дела А40-12345/2025 за исполнительный лист в папку Архив",
            "перенеси все документы дела А40-12345/2025 за обеспечительные меры в папку Архив",
            "перенеси все документы дела А40-12345/2025 за собрание кредиторов в папку Архив",
            "перенеси документ 1-го исполнительного листа в дело Архив",
            "перемести документ 1-х обеспечительных мер в дело Архив",
            "перемести документ 1-го собрания кредиторов в дело Архив",
        )
        for text in phrases:
            self.assertTrue(enforcement_blocks_bulk_document_mutation(text), text)
        kept = "перенеси документ 214 за исполнительный лист в дело Архив"
        kept_ids = [
            int(x)
            for x in re.findall(
                r"(?:документ|файл)\s+(\d+)",
                mask_enforcement_ordinals(kept),
                flags=re.IGNORECASE,
            )
        ]
        self.assertEqual(kept_ids, [214])
        amount = (
            "перенеси все документы дела А40-12345/2025 за 100 исполнительного листа в папку Архив"
        )
        masked = mask_enforcement_ordinals(amount)
        self.assertIn("12345", masked)
        self.assertIn("2025", masked)
        self.assertNotIn("100", masked)

    def test_explicit_id_still_allowed(self) -> None:
        self.assertFalse(
            enforcement_blocks_bulk_document_mutation(
                "удали документ 214 за исполнительный лист",
                explicit_document_ids=[214],
            )
        )
        self.assertEqual(_parse_ids_like_main("удали документ 214 за исполнительный лист"), [214])
        self.assertEqual(_parse_ids_like_main("удали документ 18 за обеспечительные меры"), [18])
        self.assertEqual(_parse_ids_like_main("удали документ 18 за собрание кредиторов"), [18])
        self.assertEqual(
            _parse_ids_like_main("удали документы [12] [18] за исполнительный лист"),
            [12, 18],
        )
        self.assertEqual(_parse_ids_like_main("удали документ 214"), [214])

    def test_plain_folder_commands_are_not_scoped(self) -> None:
        for text in (
            "удали все документы в этой папке",
            "удали все документы в текущей папке",
            "удали все документы в открытой папке",
            "удали все документы в этой папке без исполнительного листа",
            "удали все документы в этой папке без обеспечительных мер",
            "удали все документы в этой папке без собрания кредиторов",
            "удали все документы в папке «Исполнительный лист»",
            "удали все документы в папке Исполнительный лист",
            "удали все документы в папке Обеспечительные меры",
            "удали все документы в папке Собрание кредиторов",
            "удали все документы из папки Исполнительный лист",
            "перенеси все документы в папку Исполнительный лист",
            "перенеси все документы в папку Собрание кредиторов",
            "удали все документы по делу Исполнительный лист",
            "удали все документы по делу Обеспечительные меры",
            "удали все документы по делу Собрание кредиторов",
            "удали все документы по делу Банкротство Эмиль",
            "удали все документы дела А53-13969/2026",
            "удали все документы по Вартанов Эмиль Валерьевич",
            "удали все документы за исполнительное производство в этой папке",
            "удали все документы за судебный приказ в этой папке",
            "удали все документы за мировое соглашение в этой папке",
            "удали все документы за больничный лист в этой папке",
            "удали все документы за конкурсного управляющего в этой папке",
            "удали все документы за банкротство в этой папке",
            "удали все документы за лист в этой папке",
            "удали все документы за меры в этой папке",
            "удали все документы за собрание в этой папке",
            "удали все документы за кредиторов в этой папке",
            "удали все документы в папке Комитет кредиторов",
            "удали все документы по делу Комитет кредиторов",
            "удали все документы за кредиторскую задолженность в этой папке",
            "удали документы 1-го приказа",
            "удали документы 1-го соглашения",
            "удали документы 1-го листа",
            "удали документы 1-го производства",
        ):
            self.assertFalse(looks_like_enforcement_scoped_document_request(text), text)
            self.assertFalse(enforcement_blocks_bulk_document_mutation(text), text)

    def test_genitive_document_forms_are_scoped(self) -> None:
        for text in (
            "удали документы исполнительного листа в этой папке",
            "удали документы обеспечительных мер в этой папке",
            "удали документы собрания кредиторов в этой папке",
            "удали документы собрания комитета кредиторов в этой папке",
            "удали документы комитета кредиторов в этой папке",
            "удали все документы за первого исполнительного листа в этой папке",
            "удали эти обеспечительные меры в этой папке",
            "удали все документы за этот исполнительный лист в этой папке",
        ):
            self.assertTrue(enforcement_blocks_bulk_document_mutation(text), text)

    def test_inflected_forms_are_scoped(self) -> None:
        phrases = (
            "за исполнительный лист",
            "за исполнительного листа",
            "за исполнительному листу",
            "за исполнительным листом",
            "за исполнительном листе",
            "за исполнительные листы",
            "за исполнительных листов",
            "за исполнительными листами",
            "за обеспечительную меру",
            "за обеспечительной меры",
            "за обеспечительной мерой",
            "за обеспечительные меры",
            "за обеспечительных мер",
            "за обеспечительными мерами",
            "за собрание кредиторов",
            "за собрания кредиторов",
            "за собранию кредиторов",
            "за собранием кредиторов",
            "за собрании кредиторов",
            "за собрание кредитора",
            "за собрание комитета кредиторов",
            "за комитет кредиторов",
            "за комитета кредиторов",
            "по комитету кредиторов",
            "по собранию кредиторов",
        )
        for text in phrases:
            self.assertTrue(
                looks_like_enforcement_scoped_document_request(f"удали все документы {text} в этой папке"),
                text,
            )

    def test_main_wires_the_guard_before_the_wipe(self) -> None:
        source = (Path(__file__).resolve().parent / "app" / "main.py").read_text(encoding="utf-8")
        self.assertIn("enforcement_blocks_bulk_document_mutation", source)
        self.assertIn("mask_enforcement_ordinals", source)
        self.assertIn("DELETE_REFUSED_REPLY", source)
        self.assertIn("MOVE_REFUSED_REPLY", source)
        delete_fn = source.split("def handle_delete_documents_chat", 1)[1].split("\ndef ", 1)[0]
        self.assertLess(
            delete_fn.index("enforcement_blocks_bulk_document_mutation"),
            delete_fn.index("wants_all = any"),
        )
        parse_fn = source.split("def parse_document_ids_for_delete_command", 1)[1].split("\ndef ", 1)[0]
        self.assertLess(parse_fn.index("mask_enforcement_ordinals"), parse_fn.index("re.search"))
        move_fn = source.split("def move_documents_by_chat_command", 1)[1].split("\ndef ", 1)[0]
        self.assertIn("mask_enforcement_ordinals", move_fn)
        bulk = source.split("if looks_like_move_all_from_active_case_to_folder(text):", 1)[1]
        self.assertLess(
            bulk.index("enforcement_blocks_bulk_document_mutation"),
            bulk.index("execute_move_all_documents_to_case_folder"),
        )


if __name__ == "__main__":
    unittest.main()
