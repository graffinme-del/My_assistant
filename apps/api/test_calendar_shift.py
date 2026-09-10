"""Shift-scoped chat must not wipe a folder or delete the wrong document.

«удали все документы за смену в этой папке» used to match wants_all and hard-delete
every file in the open case because the shift phrase was ignored.
«удали документы 1-й смены» took the leading digit as a document id.
"""

from __future__ import annotations

import re
import unittest

from app.calendar_shift import (
    looks_like_shift_scoped_document_request,
    mask_shift_ordinals,
    shift_blocks_bulk_document_mutation,
)
from app.ru_date_range import parse_calendar_period_ru


def _parse_ids_like_main(text: str) -> list[int]:
    """Mirror apps/api/app/main.py:parse_document_ids_for_delete_command after the fix."""
    raw = text or ""
    ids = [int(x) for x in re.findall(r"\[(\d+)\]", raw)]
    ids.extend(int(x) for x in re.findall(r"(?i)\bdoc[.:]?\s*(\d+)\b", raw))
    if ids:
        return sorted(set(ids))
    safe = mask_shift_ordinals(raw)
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


class ShiftScopeTests(unittest.TestCase):
    def test_shift_phrases_are_detected(self) -> None:
        self.assertTrue(
            looks_like_shift_scoped_document_request(
                "удали все документы за смену в этой папке"
            )
        )
        self.assertTrue(
            looks_like_shift_scoped_document_request(
                "удали все документы за ночную смену в этой папке"
            )
        )
        self.assertTrue(
            looks_like_shift_scoped_document_request(
                "удали все документы за дневную смену"
            )
        )
        self.assertTrue(
            looks_like_shift_scoped_document_request(
                "удали все документы по сменам"
            )
        )
        self.assertTrue(
            looks_like_shift_scoped_document_request(
                "удали все документы на смене"
            )
        )
        self.assertTrue(
            looks_like_shift_scoped_document_request(
                "удали все документы во время смены"
            )
        )
        self.assertTrue(
            looks_like_shift_scoped_document_request(
                "удали все документы за текущую смену"
            )
        )
        self.assertTrue(
            looks_like_shift_scoped_document_request(
                "удали документы этой смены"
            )
        )
        self.assertTrue(
            looks_like_shift_scoped_document_request(
                "перенеси все документы за смену в папку Банкротство"
            )
        )
        self.assertTrue(
            looks_like_shift_scoped_document_request(
                "удали все документы за смену дела А40-12345/2025"
            )
        )
        self.assertTrue(
            looks_like_shift_scoped_document_request(
                "удали документы первой смены"
            )
        )

    def test_night_and_collocation_phrases_are_detected(self) -> None:
        self.assertTrue(
            looks_like_shift_scoped_document_request(
                "удали все документы за ночь в этой папке"
            )
        )
        self.assertTrue(
            looks_like_shift_scoped_document_request(
                "удали все документы по ночам"
            )
        )
        self.assertTrue(
            looks_like_shift_scoped_document_request(
                "удали все документы ночью в этой папке"
            )
        )
        self.assertTrue(
            looks_like_shift_scoped_document_request(
                "удали все ночные документы в этой папке"
            )
        )
        self.assertTrue(
            looks_like_shift_scoped_document_request(
                "удали все дневные документы"
            )
        )
        self.assertTrue(
            looks_like_shift_scoped_document_request(
                "удали все сменные документы в этой папке"
            )
        )
        self.assertTrue(
            looks_like_shift_scoped_document_request(
                "удали документы ночные"
            )
        )

    def test_plain_wipe_or_id_commands_are_not_shift_scoped(self) -> None:
        self.assertFalse(
            looks_like_shift_scoped_document_request("удали все документы в этой папке")
        )
        self.assertFalse(
            looks_like_shift_scoped_document_request("удали документ 254")
        )
        self.assertFalse(
            looks_like_shift_scoped_document_request(
                "удали все документы дела А40-12345/2025"
            )
        )
        self.assertFalse(
            looks_like_shift_scoped_document_request(
                "перенеси все документы в папку Банкротство"
            )
        )
        self.assertFalse(
            looks_like_shift_scoped_document_request(
                "удали все документы за будни в этой папке"
            )
        )
        self.assertFalse(
            looks_like_shift_scoped_document_request(
                "удали все документы за отпуск в этой папке"
            )
        )
        self.assertFalse(
            looks_like_shift_scoped_document_request(
                "удали все документы за выходные в этой папке"
            )
        )
        self.assertFalse(
            looks_like_shift_scoped_document_request(
                "удали все документы в папке Смена"
            )
        )
        self.assertFalse(
            looks_like_shift_scoped_document_request(
                "смени название папки Старое на Новое"
            )
        )
        # Daily files, not daytime/shift-scoped.
        self.assertFalse(
            looks_like_shift_scoped_document_request(
                "удали все ежедневные документы в этой папке"
            )
        )


class ShiftOrdinalIdTests(unittest.TestCase):
    def test_ordinal_shift_is_not_a_document_id(self) -> None:
        self.assertEqual(_parse_ids_like_main("удали документы 1-й смены"), [])
        self.assertEqual(_parse_ids_like_main("удали документ 1-я смена"), [])
        self.assertEqual(_parse_ids_like_main("удали файлы 2-ю смену"), [])
        self.assertEqual(_parse_ids_like_main("удали все документы 1-й смены"), [])
        self.assertEqual(_parse_ids_like_main("удали документы 1 смены"), [])

    def test_real_ids_still_parse(self) -> None:
        self.assertEqual(_parse_ids_like_main("удали документ 254"), [254])
        self.assertEqual(_parse_ids_like_main("удали документы 1 и 2"), [1, 2])
        self.assertEqual(_parse_ids_like_main("удали документы [12] [18]"), [12, 18])
        self.assertEqual(
            _parse_ids_like_main("удали документ 254 за смену"),
            [254],
        )
        self.assertEqual(
            _parse_ids_like_main("удали документ [18] 1-й смены"),
            [18],
        )


class BulkMutationGuardTests(unittest.TestCase):
    def test_shift_scoped_all_deletes_are_blocked(self) -> None:
        self.assertTrue(
            shift_blocks_bulk_document_mutation(
                "удали все документы за смену в этой папке"
            )
        )
        self.assertTrue(
            shift_blocks_bulk_document_mutation(
                "удали все документы за ночную смену в этой папке"
            )
        )
        self.assertTrue(
            shift_blocks_bulk_document_mutation(
                "удали все документы по сменам"
            )
        )
        self.assertTrue(
            shift_blocks_bulk_document_mutation(
                "удали все документы во время смены"
            )
        )
        self.assertTrue(
            shift_blocks_bulk_document_mutation("удали документы 1-й смены")
        )

    def test_night_collocation_deletes_are_blocked(self) -> None:
        self.assertTrue(
            shift_blocks_bulk_document_mutation(
                "удали все ночные документы в этой папке"
            )
        )
        self.assertTrue(
            shift_blocks_bulk_document_mutation(
                "удали все документы за ночь в этой папке"
            )
        )
        self.assertTrue(
            shift_blocks_bulk_document_mutation(
                "удали все сменные документы в этой папке"
            )
        )

    def test_pre_fix_folder_wipe_trigger_is_exactly_the_blocked_shape(self) -> None:
        """Pre-fix: wants_all + open folder hard-deleted every file because «за смену» was ignored."""
        text = "удали все документы за смену в этой папке"
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
        self.assertTrue(wants_all)
        self.assertTrue(uses_open_folder)
        self.assertIsNone(parse_calendar_period_ru(text))
        self.assertFalse(re.search(r"\[(\d+)\]", text))
        self.assertEqual(_parse_ids_like_main(text), [])
        self.assertTrue(shift_blocks_bulk_document_mutation(text))

    def test_night_shift_wipe_trigger_is_the_same_shape(self) -> None:
        text = "удали все документы за ночную смену в этой папке"
        low = text.lower()
        wants_all = "все документ" in low
        uses_open_folder = "этой папк" in low
        self.assertTrue(wants_all)
        self.assertTrue(uses_open_folder)
        self.assertIsNone(parse_calendar_period_ru(text))
        self.assertTrue(shift_blocks_bulk_document_mutation(text))

    def test_current_shift_uses_active_folder_via_текущ(self) -> None:
        """«текущ» is an open-folder cue, so this wiped the active case without «в этой папке»."""
        text = "удали все документы за текущую смену"
        low = text.lower()
        self.assertIn("все документ", low)
        self.assertIn("текущ", low)
        self.assertIsNone(parse_calendar_period_ru(text))
        self.assertTrue(shift_blocks_bulk_document_mutation(text))

    def test_ordinal_shift_wrong_id_trigger(self) -> None:
        """Pre-fix: «1-й смены» parsed as document id 1 and hard-deleted that file."""
        text = "удали документы 1-й смены"
        self.assertEqual(_parse_ids_like_main(text), [])
        self.assertTrue(shift_blocks_bulk_document_mutation(text))

    def test_existing_period_parser_does_not_see_shifts(self) -> None:
        """#69–#77 cover dates, months, weeks, years, seasons, holidays, отпуск, больничный, будни — not смены."""
        self.assertIsNone(
            parse_calendar_period_ru("удали все документы за смену в этой папке")
        )
        self.assertIsNone(
            parse_calendar_period_ru("удали все документы за ночную смену")
        )
        self.assertIsNone(parse_calendar_period_ru("удали все документы по сменам"))
        self.assertIsNone(parse_calendar_period_ru("удали все ночные документы"))
        self.assertIsNone(parse_calendar_period_ru("удали все документы за ночь"))

    def test_explicit_id_still_allowed_even_if_shift_is_mentioned(self) -> None:
        self.assertFalse(
            shift_blocks_bulk_document_mutation(
                "удали документ 254 за смену",
                explicit_document_ids=[254],
            )
        )

    def test_unscoped_folder_wipe_is_not_blocked(self) -> None:
        self.assertFalse(
            shift_blocks_bulk_document_mutation("удали все документы в этой папке")
        )
        self.assertFalse(
            shift_blocks_bulk_document_mutation(
                "удали все документы дела А40-12345/2025"
            )
        )
        self.assertFalse(
            shift_blocks_bulk_document_mutation("удали документ 254")
        )
        self.assertFalse(
            shift_blocks_bulk_document_mutation(
                "удали все документы в папке Смена"
            )
        )
        self.assertFalse(
            shift_blocks_bulk_document_mutation(
                "удали все ежедневные документы в этой папке"
            )
        )


if __name__ == "__main__":
    unittest.main()
