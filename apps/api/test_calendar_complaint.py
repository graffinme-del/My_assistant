"""Complaint/petition/expert/security-measures chat must not wipe a folder or delete the wrong document.

«удали все документы за жалобу в этой папке» used to match wants_all and hard-delete
every file in the open case because the complaint phrase was ignored.
«удали документы 1-й жалобы» took the leading digit as a document id.
"""

from __future__ import annotations

import re
import unittest

from app.calendar_complaint import (
    complaint_blocks_bulk_document_mutation,
    looks_like_complaint_scoped_document_request,
    mask_complaint_ordinals,
)
from app.ru_date_range import parse_calendar_period_ru


def _parse_ids_like_main(text: str) -> list[int]:
    """Mirror apps/api/app/main.py:parse_document_ids_for_delete_command after the fix."""
    raw = text or ""
    ids = [int(x) for x in re.findall(r"\[(\d+)\]", raw)]
    ids.extend(int(x) for x in re.findall(r"(?i)\bdoc[.:]?\s*(\d+)\b", raw))
    if ids:
        return sorted(set(ids))
    safe = mask_complaint_ordinals(raw)
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
    """Document-id parser on main before this fix — digits of «1-й жалобы» become an id."""
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


class ComplaintScopeTests(unittest.TestCase):
    def test_complaint_phrases_are_detected(self) -> None:
        self.assertTrue(
            looks_like_complaint_scoped_document_request(
                "удали все документы за жалобу в этой папке"
            )
        )
        self.assertTrue(
            looks_like_complaint_scoped_document_request(
                "удали все документы за заявление в этой папке"
            )
        )
        self.assertTrue(
            looks_like_complaint_scoped_document_request(
                "удали все документы за экспертизу в этой папке"
            )
        )
        self.assertTrue(
            looks_like_complaint_scoped_document_request(
                "удали все документы за обеспечение в этой папке"
            )
        )
        self.assertTrue(
            looks_like_complaint_scoped_document_request(
                "удали все документы за обеспечительные меры в этой папке"
            )
        )
        self.assertTrue(
            looks_like_complaint_scoped_document_request(
                "удали все документы за апелляционную жалобу в этой папке"
            )
        )
        self.assertTrue(
            looks_like_complaint_scoped_document_request(
                "удали все документы за исковое заявление в этой папке"
            )
        )
        self.assertTrue(
            looks_like_complaint_scoped_document_request("удали все документы на жалобе")
        )
        self.assertTrue(
            looks_like_complaint_scoped_document_request(
                "удали все документы по заявлению"
            )
        )
        self.assertTrue(
            looks_like_complaint_scoped_document_request(
                "удали все документы во время экспертизы"
            )
        )
        self.assertTrue(
            looks_like_complaint_scoped_document_request(
                "перенеси все документы за жалобу в папку Банкротство"
            )
        )
        self.assertTrue(
            looks_like_complaint_scoped_document_request(
                "удали все документы за жалобу дела А40-12345/2025"
            )
        )
        self.assertTrue(
            looks_like_complaint_scoped_document_request("удали документы первой жалобы")
        )
        self.assertTrue(
            looks_like_complaint_scoped_document_request(
                "удали документы первого заявления"
            )
        )

    def test_genitive_collocation_phrases_are_detected(self) -> None:
        self.assertTrue(
            looks_like_complaint_scoped_document_request(
                "удали все документы жалобы в этой папке"
            )
        )
        self.assertTrue(
            looks_like_complaint_scoped_document_request("удали документы заявления")
        )
        self.assertTrue(
            looks_like_complaint_scoped_document_request("удали документы экспертизы")
        )
        self.assertTrue(
            looks_like_complaint_scoped_document_request("удали документы обеспечения")
        )
        self.assertTrue(
            looks_like_complaint_scoped_document_request(
                "удали жалобные документы в этой папке"
            )
        )
        self.assertTrue(
            looks_like_complaint_scoped_document_request(
                "удали экспертные документы в этой папке"
            )
        )
        self.assertTrue(
            looks_like_complaint_scoped_document_request(
                "удали обеспечительные документы в этой папке"
            )
        )

    def test_plain_wipe_or_id_commands_are_not_complaint_scoped(self) -> None:
        self.assertFalse(
            looks_like_complaint_scoped_document_request("удали все документы в этой папке")
        )
        self.assertFalse(looks_like_complaint_scoped_document_request("удали документ 254"))
        self.assertFalse(
            looks_like_complaint_scoped_document_request(
                "удали все документы дела А40-12345/2025"
            )
        )
        self.assertFalse(
            looks_like_complaint_scoped_document_request(
                "перенеси все документы в папку Банкротство"
            )
        )
        self.assertFalse(
            looks_like_complaint_scoped_document_request(
                "удали все документы за иск в этой папке"
            )
        )
        self.assertFalse(
            looks_like_complaint_scoped_document_request(
                "удали все документы за ходатайство в этой папке"
            )
        )
        self.assertFalse(
            looks_like_complaint_scoped_document_request(
                "удали все документы за протокол в этой папке"
            )
        )
        self.assertFalse(
            looks_like_complaint_scoped_document_request(
                "удали все документы за заседание в этой папке"
            )
        )
        self.assertFalse(
            looks_like_complaint_scoped_document_request(
                "удали все документы в папке Жалоба"
            )
        )
        self.assertFalse(
            looks_like_complaint_scoped_document_request(
                "удали все документы в папке Заявление"
            )
        )
        self.assertFalse(
            looks_like_complaint_scoped_document_request(
                "удали все документы в папке Экспертиза"
            )
        )
        self.assertFalse(
            looks_like_complaint_scoped_document_request(
                "удали все документы в папке Обеспечение"
            )
        )
        self.assertFalse(
            looks_like_complaint_scoped_document_request(
                "удали все документы которые жалобщик подписал в этой папке"
            )
        )
        self.assertFalse(
            looks_like_complaint_scoped_document_request(
                "удали все документы заявленные как лишние в этой папке"
            )
        )


class ComplaintOrdinalIdTests(unittest.TestCase):
    def test_pre_fix_parser_took_ordinal_as_document_id(self) -> None:
        self.assertEqual(_pre_fix_parse_ids("удали документы 1-й жалобы"), [1])
        self.assertEqual(_pre_fix_parse_ids("удали документы 1-го заявления"), [1])
        self.assertEqual(_pre_fix_parse_ids("удали файлы 1-й экспертизы"), [1])
        self.assertEqual(_pre_fix_parse_ids("удали файлы 1-го обеспечения"), [1])
        self.assertEqual(
            _pre_fix_parse_ids("удали документы 1-х обеспечительных мер"), [1]
        )

    def test_ordinal_complaint_is_not_a_document_id(self) -> None:
        self.assertEqual(_parse_ids_like_main("удали документы 1-й жалобы"), [])
        self.assertEqual(_parse_ids_like_main("удали документ 1-я жалоба"), [])
        self.assertEqual(_parse_ids_like_main("удали файлы 1-го заявления"), [])
        self.assertEqual(_parse_ids_like_main("удали все документы 1-й экспертизы"), [])
        self.assertEqual(_parse_ids_like_main("удали документы 1 жалобы"), [])
        self.assertEqual(_parse_ids_like_main("удали документы 2-е заявление"), [])
        self.assertEqual(
            _parse_ids_like_main("удали документы 1-го обеспечения"), []
        )

    def test_real_ids_still_parse(self) -> None:
        self.assertEqual(_parse_ids_like_main("удали документ 254"), [254])
        self.assertEqual(_parse_ids_like_main("удали документы 1 и 2"), [1, 2])
        self.assertEqual(_parse_ids_like_main("удали документы [12] [18]"), [12, 18])
        self.assertEqual(
            _parse_ids_like_main("удали документ 254 за жалобу"),
            [254],
        )
        self.assertEqual(
            _parse_ids_like_main("удали документ [18] 1-й жалобы"),
            [18],
        )


class BulkMutationGuardTests(unittest.TestCase):
    def test_complaint_scoped_all_deletes_are_blocked(self) -> None:
        self.assertTrue(
            complaint_blocks_bulk_document_mutation(
                "удали все документы за жалобу в этой папке"
            )
        )
        self.assertTrue(
            complaint_blocks_bulk_document_mutation(
                "удали все документы за заявление в этой папке"
            )
        )
        self.assertTrue(
            complaint_blocks_bulk_document_mutation(
                "удали все документы за экспертизу в этой папке"
            )
        )
        self.assertTrue(
            complaint_blocks_bulk_document_mutation(
                "удали все документы за обеспечение в этой папке"
            )
        )
        self.assertTrue(
            complaint_blocks_bulk_document_mutation("удали все документы на жалобе")
        )
        self.assertTrue(
            complaint_blocks_bulk_document_mutation(
                "удали все документы во время заявления"
            )
        )
        self.assertTrue(
            complaint_blocks_bulk_document_mutation("удали документы 1-й жалобы")
        )

    def test_genitive_collocation_deletes_are_blocked(self) -> None:
        self.assertTrue(
            complaint_blocks_bulk_document_mutation(
                "удали все документы жалобы в этой папке"
            )
        )
        self.assertTrue(
            complaint_blocks_bulk_document_mutation("удали документы заявления")
        )
        self.assertTrue(
            complaint_blocks_bulk_document_mutation(
                "удали жалобные документы в этой папке"
            )
        )

    def test_pre_fix_folder_wipe_trigger_is_exactly_the_blocked_shape(self) -> None:
        """Pre-fix: wants_all + open folder hard-deleted every file because «за жалобу» was ignored."""
        text = "удали все документы за жалобу в этой папке"
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
        self.assertTrue(complaint_blocks_bulk_document_mutation(text))

    def test_petition_wipe_trigger_is_the_same_shape(self) -> None:
        text = "удали все документы за заявление в этой папке"
        low = text.lower()
        wants_all = "все документ" in low
        uses_open_folder = "этой папк" in low
        self.assertTrue(wants_all)
        self.assertTrue(uses_open_folder)
        self.assertIsNone(parse_calendar_period_ru(text))
        self.assertTrue(complaint_blocks_bulk_document_mutation(text))

    def test_expert_wipe_trigger_is_the_same_shape(self) -> None:
        text = "удали все документы за экспертизу в этой папке"
        low = text.lower()
        wants_all = "все документ" in low
        uses_open_folder = "этой папк" in low
        self.assertTrue(wants_all)
        self.assertTrue(uses_open_folder)
        self.assertIsNone(parse_calendar_period_ru(text))
        self.assertTrue(complaint_blocks_bulk_document_mutation(text))

    def test_security_measures_wipe_trigger_is_the_same_shape(self) -> None:
        text = "удали все документы за обеспечение в этой папке"
        low = text.lower()
        wants_all = "все документ" in low
        uses_open_folder = "этой папк" in low
        self.assertTrue(wants_all)
        self.assertTrue(uses_open_folder)
        self.assertIsNone(parse_calendar_period_ru(text))
        self.assertTrue(complaint_blocks_bulk_document_mutation(text))

    def test_current_complaint_uses_active_folder_via_текущ(self) -> None:
        """«текущ» is an open-folder cue, so this wiped the active case without «в этой папке»."""
        text = "удали все документы за текущую жалобу"
        low = text.lower()
        self.assertIn("все документ", low)
        self.assertIn("текущ", low)
        self.assertIsNone(parse_calendar_period_ru(text))
        self.assertTrue(complaint_blocks_bulk_document_mutation(text))

    def test_current_petition_uses_active_folder_via_текущ(self) -> None:
        text = "удали все документы за текущее заявление"
        low = text.lower()
        self.assertIn("все документ", low)
        self.assertIn("текущ", low)
        self.assertTrue(complaint_blocks_bulk_document_mutation(text))

    def test_ordinal_complaint_wrong_id_trigger(self) -> None:
        """Pre-fix: «1-й жалобы» parsed as document id 1 and hard-deleted that file."""
        text = "удали документы 1-й жалобы"
        self.assertEqual(_pre_fix_parse_ids(text), [1])
        self.assertEqual(_parse_ids_like_main(text), [])
        self.assertTrue(complaint_blocks_bulk_document_mutation(text))

    def test_existing_period_parser_does_not_see_complaint(self) -> None:
        """#69–#85 cover dates through claim/protocol — not жалоба/заявление/экспертиза/обеспечение."""
        self.assertIsNone(
            parse_calendar_period_ru("удали все документы за жалобу в этой папке")
        )
        self.assertIsNone(
            parse_calendar_period_ru("удали все документы за заявление в этой папке")
        )
        self.assertIsNone(
            parse_calendar_period_ru("удали все документы за экспертизу в этой папке")
        )
        self.assertIsNone(parse_calendar_period_ru("удали все документы за обеспечение"))
        self.assertIsNone(parse_calendar_period_ru("удали все документы на жалобе"))
        self.assertIsNone(parse_calendar_period_ru("удали все документы жалобы"))

    def test_explicit_id_still_allowed_even_if_complaint_is_mentioned(self) -> None:
        self.assertFalse(
            complaint_blocks_bulk_document_mutation(
                "удали документ 254 за жалобу",
                explicit_document_ids=[254],
            )
        )

    def test_unscoped_folder_wipe_is_not_blocked(self) -> None:
        self.assertFalse(
            complaint_blocks_bulk_document_mutation("удали все документы в этой папке")
        )
        self.assertFalse(
            complaint_blocks_bulk_document_mutation(
                "удали все документы дела А40-12345/2025"
            )
        )
        self.assertFalse(complaint_blocks_bulk_document_mutation("удали документ 254"))
        self.assertFalse(
            complaint_blocks_bulk_document_mutation("удали все документы в папке Жалоба")
        )
        self.assertFalse(
            complaint_blocks_bulk_document_mutation(
                "удали все документы в папке Заявление"
            )
        )
        self.assertFalse(
            complaint_blocks_bulk_document_mutation(
                "удали все документы за иск в этой папке"
            )
        )


if __name__ == "__main__":
    unittest.main()
