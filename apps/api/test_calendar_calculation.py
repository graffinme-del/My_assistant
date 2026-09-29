"""«Расчет» chat must not wipe a folder or delete the wrong document.

Pre-fix, handle_delete_documents_chat treated «все документы» as wipe-the-folder
and parsed «1-го расчета» as document id 1. The calendar-period parser does not
recognize these phrases, and earlier document-type guards do not match «расчет».
"""

from __future__ import annotations

import re
import unittest
from pathlib import Path

from app.calendar_calculation import (
    calculation_blocks_bulk_document_mutation,
    looks_like_calculation_scoped_document_request,
    mask_calculation_ordinals,
)
from app.ru_date_range import parse_calendar_period_ru


def _parse_ids_like_main(text: str) -> list[int]:
    """Mirror apps/api/app/main.py:parse_document_ids_for_delete_command after the fix."""
    raw = text or ""
    ids = [int(x) for x in re.findall(r"\[(\d+)\]", raw)]
    ids.extend(int(x) for x in re.findall(r"(?i)\bdoc[.:]?\s*(\d+)\b", raw))
    if ids:
        return sorted(set(ids))
    safe = mask_calculation_ordinals(raw)
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
    """Parser on main before calculation ordinals are masked."""
    raw = text or ""
    ids = [int(x) for x in re.findall(r"\[(\d+)\]", raw)]
    ids.extend(int(x) for x in re.findall(r"(?i)\bdoc[.:]?\s*(\d+)\b", raw))
    if ids:
        return sorted(set(ids))
    m = re.search(
        r"(?:документы?|файлы?)(?:\s+(?:с\s+)?id|\s+№|\s+#)?\s*[:.]?\s*([\d\s,;и]+)",
        raw,
        flags=re.IGNORECASE,
    )
    if m:
        return sorted({int(x) for x in re.findall(r"\d+", m.group(1))})
    m2 = re.search(r"(?:документ|файл)\s*(?:№|#)?\s*(\d+)\b", raw, flags=re.IGNORECASE)
    if m2:
        return [int(m2.group(1))]
    return []


class CalculationScopeTests(unittest.TestCase):
    def test_folder_wipe_phrases_are_calculation_scoped(self) -> None:
        for phrase in (
            "удали все документы за расчет в этой папке",
            "удали все документы за расчёт в этой папке",
            "удали все документы за перерасчет в этой папке",
            "удали все документы с расчетом в этой папке",
            "удали все документы по расчету в этой папке",
            "удали все файлы за подробный расчет в этой папке",
            "удали все документы за уточненный расчет в этой папке",
            "удали все документы за расчет задолженности в этой папке",
            "удали все документы за расчет неустойки в этой папке",
        ):
            self.assertTrue(looks_like_calculation_scoped_document_request(phrase), phrase)

    def test_demonstrative_and_current_calculation_are_detected(self) -> None:
        self.assertTrue(
            looks_like_calculation_scoped_document_request(
                "удали все документы за текущий расчет"
            )
        )
        self.assertTrue(
            looks_like_calculation_scoped_document_request(
                "удали все документы за открытые расчеты"
            )
        )
        self.assertTrue(
            looks_like_calculation_scoped_document_request("удали документы этого расчета")
        )
        self.assertTrue(
            looks_like_calculation_scoped_document_request("удали файлы этих расчетов")
        )

    def test_ordinals_and_adjective_documents_are_detected(self) -> None:
        for phrase in (
            "удали документы 1-го расчета",
            "удали документы 1-й расчет",
            "удали документы 2-х расчетов",
            "удали документы первого расчета",
            "удали все документы расчетные в этой папке",
            "удали все расчетные документы в этой папке",
            "удали документы во время расчета",
        ):
            self.assertTrue(looks_like_calculation_scoped_document_request(phrase), phrase)

    def test_unscoped_and_lookalikes_do_not_match(self) -> None:
        for phrase in (
            "удали все документы в этой папке",
            "удали все документы в папке «Расчет»",
            "удали все документы в папке Расчет",
            "удали документ «расчет.pdf»",
            "удали все документы за расчетный счет в этой папке",
            "удали все документы за доказательства в этой папке",
            "удали все документы за контракт в этой папке",
            "удали все документы за договор в этой папке",
            "удали все документы за акт в этой папке",
            "удали все документы за поручение в этой папке",
            "удали все документы за приложение в этой папке",
            "удали все документы за требование в этой папке",
            "удали все документы за пояснение в этой папке",
            "удали все документы за лицензию в этой папке",
            "удали все документы за свидетельство в этой папке",
            "удали все документы за человека в этой папке",
            "удали документы 1-го человека",
            "это расчетный аргумент, удали все документы в этой папке",
        ):
            self.assertFalse(looks_like_calculation_scoped_document_request(phrase), phrase)

    def test_human_ordinal_is_not_masked(self) -> None:
        self.assertFalse(looks_like_calculation_scoped_document_request("удали документы 1-го человека"))
        self.assertEqual(_parse_ids_like_main("удали документы 1-го человека"), [1])

    def test_folder_wipe_trigger_is_not_a_calendar_period(self) -> None:
        text = "удали все документы за расчет в этой папке"
        low = text.lower()
        self.assertIn("все документ", low)
        self.assertIn("в этой", low)
        self.assertIsNone(parse_calendar_period_ru(text))
        self.assertEqual(_pre_fix_parse_ids(text), [])
        self.assertEqual(_parse_ids_like_main(text), [])
        self.assertTrue(calculation_blocks_bulk_document_mutation(text))

    def test_with_calculation_phrase_wipes_pre_fix(self) -> None:
        """«с расчетом» is the idiomatic scope and still matched wants_all."""
        text = "удали все документы с расчетом в этой папке"
        low = text.lower()
        self.assertIn("все документ", low)
        self.assertIn("этой папк", low)
        self.assertEqual(_pre_fix_parse_ids(text), [])
        self.assertIsNone(parse_calendar_period_ru(text))
        self.assertTrue(calculation_blocks_bulk_document_mutation(text))

    def test_current_calculation_uses_active_folder_via_текущ(self) -> None:
        text = "удали все документы за текущий расчет"
        low = text.lower()
        self.assertIn("все документ", low)
        self.assertIn("текущ", low)
        self.assertIsNone(parse_calendar_period_ru(text))
        self.assertTrue(calculation_blocks_bulk_document_mutation(text))

    def test_open_calculation_uses_active_folder_via_открыт(self) -> None:
        text = "удали все документы за открытые расчеты"
        low = text.lower()
        self.assertIn("все документ", low)
        self.assertIn("открыт", low)
        self.assertIsNone(parse_calendar_period_ru(text))
        self.assertTrue(calculation_blocks_bulk_document_mutation(text))

    def test_ordinal_calculation_wrong_id_trigger(self) -> None:
        """Pre-fix: «1-го расчета» parsed as document id 1 and hard-deleted that file."""
        text = "удали документы 1-го расчета"
        self.assertEqual(_pre_fix_parse_ids(text), [1])
        self.assertEqual(_parse_ids_like_main(text), [])
        self.assertTrue(calculation_blocks_bulk_document_mutation(text))
        recalculation = "удали документы 1-го перерасчета"
        self.assertEqual(_pre_fix_parse_ids(recalculation), [1])
        self.assertEqual(_parse_ids_like_main(recalculation), [])
        self.assertTrue(calculation_blocks_bulk_document_mutation(recalculation))

    def test_move_all_with_calculation_scope_is_blocked(self) -> None:
        text = "перенеси все документы дела А40-12345/2025 за расчет в папку Архив"
        low = text.lower()
        self.assertTrue(any(k in low for k in ["перенеси", "все документы", "в папку"]))
        self.assertIn("папк", low)
        self.assertTrue(calculation_blocks_bulk_document_mutation(text))
        with_calculation = "перенеси все документы с расчетом в папку Архив"
        self.assertTrue(calculation_blocks_bulk_document_mutation(with_calculation))

    def test_explicit_id_still_allowed_even_if_calculation_is_mentioned(self) -> None:
        self.assertFalse(
            calculation_blocks_bulk_document_mutation(
                "удали документ 254 за расчет",
                explicit_document_ids=[254],
            )
        )
        self.assertEqual(_parse_ids_like_main("удали документ 254 за расчет"), [254])
        self.assertEqual(_parse_ids_like_main("удали документы [12] [18] за расчет"), [12, 18])
        self.assertEqual(_pre_fix_parse_ids("удали документ 214"), [214])
        self.assertEqual(_parse_ids_like_main("удали документ 214"), [214])

    def test_main_wires_the_guard(self) -> None:
        source = (Path(__file__).resolve().parent / "app" / "main.py").read_text(encoding="utf-8")
        self.assertIn("calculation_blocks_bulk_document_mutation", source)
        self.assertIn("mask_calculation_ordinals", source)
        self.assertIn("DELETE_REFUSED_CALCULATION", source)
        self.assertIn("MOVE_REFUSED_CALCULATION", source)


if __name__ == "__main__":
    unittest.main()
