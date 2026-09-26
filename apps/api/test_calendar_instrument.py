"""Work-act / report chat must not wipe a folder or delete the wrong document.

«удали все документы за акт выполненных работ в этой папке» used to match wants_all
and hard-delete every file in the open case because the document-type phrase was ignored.
«удали документы 1-го акта» took the leading digit as a document id.

The same gap covers распоряжение, положение, заключение, отчёт, and платежное поручение.
«Акт сверки» is a separate collocation and is not this guard.
"""

from __future__ import annotations

import re
import unittest
from pathlib import Path

from app.calendar_instrument import (
    instrument_blocks_bulk_document_mutation,
    looks_like_instrument_scoped_document_request,
    mask_instrument_ordinals,
)
from app.ru_date_range import parse_calendar_period_ru


def _parse_ids_like_main(text: str) -> list[int]:
    """Mirror apps/api/app/main.py:parse_document_ids_for_delete_command after the fix."""
    raw = text or ""
    ids = [int(x) for x in re.findall(r"\[(\d+)\]", raw)]
    ids.extend(int(x) for x in re.findall(r"(?i)\bdoc[.:]?\s*(\d+)\b", raw))
    if ids:
        return sorted(set(ids))
    safe = mask_instrument_ordinals(raw)
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
    """Document-id parser on main before this fix — digits of «1-го акта» become an id."""
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


class InstrumentScopeTests(unittest.TestCase):
    def test_instrument_phrases_are_detected(self) -> None:
        for phrase in (
            "удали все документы за акт в этой папке",
            "удали все документы за акт выполненных работ в этой папке",
            "удали все документы за акт приёма-передачи в этой папке",
            "удали все документы за акт приема-передачи в этой папке",
            "удали все документы за акт сдачи-приемки",
            "удали все документы за распоряжение в этой папке",
            "удали все документы за положение в этой папке",
            "удали все документы за заключение в этой папке",
            "удали все документы за отчёт в этой папке",
            "удали все документы за отчет в этой папке",
            "удали все документы за платежное поручение в этой папке",
            "удали все документы за платёжное поручение в этой папке",
            "удали все документы по акту выполненных работ",
            "удали все документы по распоряжению",
            "удали все документы по положению",
            "удали все документы по заключению",
            "удали все документы по отчёту",
            "удали все документы по платежному поручению",
            "удали все документы на акте",
            "удали все документы в заключении",
            "удали все документы во время акта",
            "удали все документы во время отчёта",
            "удали все документы за выполненный акт",
            "удали все документы за годовой отчёт",
            "удали все документы за исходящее платежное поручение",
            "удали все документы за положительное заключение",
            "удали все документы за заключительный акт",
        ):
            self.assertTrue(
                looks_like_instrument_scoped_document_request(phrase),
                phrase,
            )

    def test_demonstrative_and_current_instrument_are_detected(self) -> None:
        self.assertTrue(
            looks_like_instrument_scoped_document_request(
                "удали все документы за текущий акт"
            )
        )
        self.assertTrue(
            looks_like_instrument_scoped_document_request(
                "удали все документы за текущее платежное поручение"
            )
        )
        self.assertTrue(
            looks_like_instrument_scoped_document_request("удали документы этого акта")
        )
        self.assertTrue(
            looks_like_instrument_scoped_document_request("удали файлы этого отчёта")
        )
        self.assertTrue(
            looks_like_instrument_scoped_document_request(
                "удали все документы за открытый отчёт"
            )
        )
        self.assertTrue(
            looks_like_instrument_scoped_document_request(
                "удали все документы за открытое положение"
            )
        )

    def test_ordinal_instrument_is_detected(self) -> None:
        for phrase in (
            "удали документы 1-го акта",
            "удали документы 1-го распоряжения",
            "удали документы 1-го положения",
            "удали документы 1-го заключения",
            "удали документы 1-го отчёта",
            "удали документы 1-го отчета",
            "удали документы 1-го платежного поручения",
            "удали документы 1-й акт",
            "удали документы первого акта",
            "удали документы первого отчёта",
            "удали документы первое заключение",
        ):
            self.assertTrue(
                looks_like_instrument_scoped_document_request(phrase),
                phrase,
            )

    def test_genitive_collocation_is_detected(self) -> None:
        for phrase in (
            "удали все документы акта в этой папке",
            "удали документы распоряжения",
            "удали документы положения",
            "удали документы заключения",
            "удали документы отчёта",
            "удали документы отчета",
            "удали документы платежного поручения",
            "удали все документы акта выполненных работ в этой папке",
        ):
            self.assertTrue(
                looks_like_instrument_scoped_document_request(phrase),
                phrase,
            )

    def test_unscoped_and_lookalike_phrases_are_not_detected(self) -> None:
        for phrase in (
            "удали все документы в этой папке",
            "удали документ 254",
            "удали все документы дела А40-12345/2025",
            "удали все документы в папке Акт",
            "удали все документы в папке Отчёт",
            "удали все документы в папке Распоряжение",
            "удали все документы в папке Платежное поручение",
            "удали все документы за человека в этой папке",
            "удали все документы за приказ в этой папке",
            "удали все документы за письмо в этой папке",
            "удали все документы за акт сверки в этой папке",
            "удали все документы за акта сверки",
            "удали документы 1-го акта сверки",
            "удали все актуальные документы в этой папке",
            "удали все документы за актуальный период",
            "удали все активные документы в этой папке",
            "удали все документы за контракт в этой папке",
            "удали все документы за факт в этой папке",
            "удали все документы за расположение",
            "удали все документы за отчётность",
            "удали все документы за отчетность",
            "удали все документы за отчётный период",
            "удали все документы за заключительный период",
            "удали все документы за положительный ответ",
            "распорядиться о выплате",
            "удали все документы за поручение в этой папке",
            "удали все письменные документы в этой папке",
        ):
            self.assertFalse(
                looks_like_instrument_scoped_document_request(phrase),
                phrase,
            )


class InstrumentOrdinalIdTests(unittest.TestCase):
    def test_pre_fix_parser_took_ordinal_as_document_id(self) -> None:
        self.assertEqual(_pre_fix_parse_ids("удали документы 1-го акта"), [1])
        self.assertEqual(_pre_fix_parse_ids("удали документы 1-го распоряжения"), [1])
        self.assertEqual(_pre_fix_parse_ids("удали документы 1-го положения"), [1])
        self.assertEqual(_pre_fix_parse_ids("удали документы 1-го заключения"), [1])
        self.assertEqual(_pre_fix_parse_ids("удали документы 1-го отчёта"), [1])
        self.assertEqual(_pre_fix_parse_ids("удали документы 1-го отчета"), [1])
        self.assertEqual(_pre_fix_parse_ids("удали документы 1-го платежного поручения"), [1])
        self.assertEqual(_pre_fix_parse_ids("удали документы 1-й акт"), [1])

    def test_ordinal_instrument_is_not_a_document_id(self) -> None:
        self.assertEqual(_parse_ids_like_main("удали документы 1-го акта"), [])
        self.assertEqual(_parse_ids_like_main("удали документы 1-го распоряжения"), [])
        self.assertEqual(_parse_ids_like_main("удали документы 1-го положения"), [])
        self.assertEqual(_parse_ids_like_main("удали документы 1-го заключения"), [])
        self.assertEqual(_parse_ids_like_main("удали документы 1-го отчёта"), [])
        self.assertEqual(_parse_ids_like_main("удали документы 1-го отчета"), [])
        self.assertEqual(_parse_ids_like_main("удали документы 1-го платежного поручения"), [])
        self.assertEqual(_parse_ids_like_main("удали документы 1-й акт"), [])
        self.assertEqual(_parse_ids_like_main("удали все документы 1-е заключение"), [])
        self.assertEqual(_parse_ids_like_main("удали документы 1 акта"), [])
        self.assertEqual(_parse_ids_like_main("удали документы 2-е положение"), [])
        self.assertEqual(
            _parse_ids_like_main("удали документы 1-го акта выполненных работ"),
            [],
        )

    def test_real_ids_still_parse(self) -> None:
        self.assertEqual(_parse_ids_like_main("удали документ 254"), [254])
        self.assertEqual(_parse_ids_like_main("удали документы 1 и 2"), [1, 2])
        self.assertEqual(_parse_ids_like_main("удали документы [12] [18]"), [12, 18])
        self.assertEqual(_parse_ids_like_main("удали документ 254 за акт"), [254])
        self.assertEqual(_parse_ids_like_main("удали документ [18] 1-го отчёта"), [18])
        self.assertEqual(_parse_ids_like_main("удали документ 12 за распоряжение"), [12])
        # Three-digit ids stay ids, matching the earlier date/document guards.
        self.assertEqual(_parse_ids_like_main("удали документы 214 акта"), [214])

    def test_reconciliation_act_ordinal_is_not_this_guard(self) -> None:
        self.assertFalse(
            looks_like_instrument_scoped_document_request("удали документы 1-го акта сверки")
        )
        self.assertEqual(_pre_fix_parse_ids("удали документы 1-го акта сверки"), [1])
        self.assertEqual(_parse_ids_like_main("удали документы 1-го акта сверки"), [1])

    def test_human_ordinal_is_not_masked(self) -> None:
        self.assertFalse(
            looks_like_instrument_scoped_document_request("удали документы 1-го человека")
        )
        self.assertEqual(_parse_ids_like_main("удали документы 1-го человека"), [1])


class BulkMutationGuardTests(unittest.TestCase):
    def test_instrument_scoped_all_deletes_are_blocked(self) -> None:
        for phrase in (
            "удали все документы за акт в этой папке",
            "удали все документы за акт выполненных работ в этой папке",
            "удали все документы за акт приёма-передачи в этой папке",
            "удали все документы за распоряжение в этой папке",
            "удали все документы за положение в этой папке",
            "удали все документы за заключение в этой папке",
            "удали все документы за отчёт в этой папке",
            "удали все документы за платежное поручение в этой папке",
            "удали все документы по акту",
            "удали все документы во время отчёта",
            "удали документы 1-го акта",
        ):
            self.assertTrue(instrument_blocks_bulk_document_mutation(phrase), phrase)

    def test_genitive_collocation_deletes_are_blocked(self) -> None:
        self.assertTrue(
            instrument_blocks_bulk_document_mutation(
                "удали все документы акта выполненных работ в этой папке"
            )
        )
        self.assertTrue(
            instrument_blocks_bulk_document_mutation("удали документы платежного поручения")
        )
        self.assertTrue(
            instrument_blocks_bulk_document_mutation("удали документы отчёта в этой папке")
        )

    def test_pre_fix_folder_wipe_trigger_is_exactly_the_blocked_shape(self) -> None:
        """Pre-fix: wants_all + open folder hard-deleted every file because the phrase was ignored."""
        for text in (
            "удали все документы за акт в этой папке",
            "удали все документы за акт выполненных работ в этой папке",
            "удали все документы за акт приёма-передачи в этой папке",
            "удали все документы за распоряжение в этой папке",
            "удали все документы за положение в этой папке",
            "удали все документы за заключение в этой папке",
            "удали все документы за отчёт в этой папке",
            "удали все документы за отчет в этой папке",
            "удали все документы за платежное поручение в этой папке",
            "удали все документы за платёжное поручение в этой папке",
        ):
            low = text.lower()
            wants_all = any(
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
            uses_open_folder = any(
                p in low for p in ("этой папк", "текущ", "открыт", "в этой", "из этой", "это дело")
            )
            self.assertTrue(wants_all, text)
            self.assertTrue(uses_open_folder, text)
            self.assertIsNone(parse_calendar_period_ru(text), text)
            self.assertFalse(re.search(r"\[(\d+)\]", text))
            self.assertEqual(_pre_fix_parse_ids(text), [])
            self.assertEqual(_parse_ids_like_main(text), [])
            self.assertTrue(instrument_blocks_bulk_document_mutation(text), text)

    def test_current_act_uses_active_folder_via_текущ(self) -> None:
        """«текущ» is an open-folder cue, so this wiped the active case without «в этой папке»."""
        text = "удали все документы за текущий акт"
        low = text.lower()
        self.assertIn("все документ", low)
        self.assertIn("текущ", low)
        self.assertIsNone(parse_calendar_period_ru(text))
        self.assertTrue(instrument_blocks_bulk_document_mutation(text))

    def test_open_report_uses_active_folder_via_открыт(self) -> None:
        """«открыт» is an open-folder cue inside «открытый отчёт»."""
        text = "удали все документы за открытый отчёт"
        low = text.lower()
        self.assertIn("все документ", low)
        self.assertIn("открыт", low)
        self.assertIsNone(parse_calendar_period_ru(text))
        self.assertTrue(instrument_blocks_bulk_document_mutation(text))

    def test_ordinal_act_wrong_id_trigger(self) -> None:
        """Pre-fix: «1-го акта» parsed as document id 1 and hard-deleted that file."""
        text = "удали документы 1-го акта"
        self.assertEqual(_pre_fix_parse_ids(text), [1])
        self.assertEqual(_parse_ids_like_main(text), [])
        self.assertTrue(instrument_blocks_bulk_document_mutation(text))

    def test_existing_period_parser_does_not_see_instrument_scope(self) -> None:
        for phrase in (
            "удали все документы за акт выполненных работ в этой папке",
            "удали все документы за распоряжение",
            "удали все документы за положение",
            "удали все документы за заключение",
            "удали все документы за отчёт",
            "удали все документы за платежное поручение",
            "удали все документы акта",
        ):
            self.assertIsNone(parse_calendar_period_ru(phrase), phrase)

    def test_named_case_move_dumps_source_folder_pre_fix(self) -> None:
        """«перенеси все документы дела А40-… за акт … в папку …» executes move-all."""
        text = (
            "перенеси все документы дела А40-12345/2025 за акт выполненных работ в папку Архив"
        )
        low = text.lower()
        self.assertTrue(any(k in low for k in ["перенеси", "все документы", "в папку"]))
        self.assertIn("папк", low)
        self.assertTrue(instrument_blocks_bulk_document_mutation(text))
        report = "перенеси все документы дела А40-12345/2025 за отчёт в папку Архив"
        self.assertTrue(instrument_blocks_bulk_document_mutation(report))
        payment = (
            "перенеси все документы дела А40-12345/2025 за платежное поручение в папку Архив"
        )
        self.assertTrue(instrument_blocks_bulk_document_mutation(payment))

    def test_explicit_id_still_allowed_even_if_instrument_is_mentioned(self) -> None:
        self.assertFalse(
            instrument_blocks_bulk_document_mutation(
                "удали документ 254 за акт выполненных работ",
                explicit_document_ids=[254],
            )
        )

    def test_unscoped_folder_wipe_is_not_blocked(self) -> None:
        for phrase in (
            "удали все документы в этой папке",
            "удали все документы дела А40-12345/2025",
            "удали документ 254",
            "удали все документы в папке Акт",
            "удали все документы в папке Отчёт",
            "удали все документы за приказ в этой папке",
            "удали все документы за письмо в этой папке",
            "удали все документы за акт сверки в этой папке",
            "удали все документы за человека в этой папке",
            "удали все актуальные документы в этой папке",
            "удали все документы за актуальный период",
            "удали все документы за поручение в этой папке",
        ):
            self.assertFalse(instrument_blocks_bulk_document_mutation(phrase), phrase)

    def test_main_wires_the_guard(self) -> None:
        source = (Path(__file__).resolve().parent / "app" / "main.py").read_text(encoding="utf-8")
        self.assertIn("instrument_blocks_bulk_document_mutation", source)
        self.assertIn("mask_instrument_ordinals", source)
        self.assertIn("DELETE_REFUSED_INSTRUMENT", source)
        self.assertIn("MOVE_REFUSED_INSTRUMENT", source)


if __name__ == "__main__":
    unittest.main()
