"""Appeal/cassation/review-scoped chat must not wipe a folder or delete the wrong document.

«удали все документы за апелляцию в этой папке» used to match wants_all and hard-delete
every file in the open case because the appeal phrase was ignored.
«удали документы 1-й апелляции» took the leading digit as a document id.
"""

from __future__ import annotations

import re
import unittest

from app.calendar_appeal import (
    appeal_blocks_bulk_document_mutation,
    looks_like_appeal_scoped_document_request,
    mask_appeal_ordinals,
)
from app.ru_date_range import parse_calendar_period_ru


def _parse_ids_like_main(text: str) -> list[int]:
    """Mirror apps/api/app/main.py:parse_document_ids_for_delete_command after the fix."""
    raw = text or ""
    ids = [int(x) for x in re.findall(r"\[(\d+)\]", raw)]
    ids.extend(int(x) for x in re.findall(r"(?i)\bdoc[.:]?\s*(\d+)\b", raw))
    if ids:
        return sorted(set(ids))
    safe = mask_appeal_ordinals(raw)
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


class AppealScopeTests(unittest.TestCase):
    def test_appeal_phrases_are_detected(self) -> None:
        self.assertTrue(
            looks_like_appeal_scoped_document_request(
                "удали все документы за апелляцию в этой папке"
            )
        )
        self.assertTrue(
            looks_like_appeal_scoped_document_request(
                "удали все документы за кассацию в этой папке"
            )
        )
        self.assertTrue(
            looks_like_appeal_scoped_document_request(
                "удали все документы за рассмотрение в этой папке"
            )
        )
        self.assertTrue(
            looks_like_appeal_scoped_document_request(
                "удали все документы за судебное разбирательство в этой папке"
            )
        )
        self.assertTrue(
            looks_like_appeal_scoped_document_request(
                "удали все документы на апелляции"
            )
        )
        self.assertTrue(
            looks_like_appeal_scoped_document_request(
                "удали все документы на кассации"
            )
        )
        self.assertTrue(
            looks_like_appeal_scoped_document_request(
                "удали все документы на рассмотрении"
            )
        )
        self.assertTrue(
            looks_like_appeal_scoped_document_request(
                "удали все документы по апелляциям"
            )
        )
        self.assertTrue(
            looks_like_appeal_scoped_document_request(
                "удали все документы во время апелляции"
            )
        )
        self.assertTrue(
            looks_like_appeal_scoped_document_request(
                "удали все документы во время судебного разбирательства"
            )
        )
        self.assertTrue(
            looks_like_appeal_scoped_document_request(
                "удали все документы за апелляционную жалобу"
            )
        )
        self.assertTrue(
            looks_like_appeal_scoped_document_request(
                "удали все документы за кассационную жалобу"
            )
        )
        self.assertTrue(
            looks_like_appeal_scoped_document_request(
                "перенеси все документы за апелляцию в папку Банкротство"
            )
        )
        self.assertTrue(
            looks_like_appeal_scoped_document_request(
                "удали все документы за апелляцию дела А40-12345/2025"
            )
        )
        self.assertTrue(
            looks_like_appeal_scoped_document_request(
                "удали документы первой апелляции"
            )
        )
        self.assertTrue(
            looks_like_appeal_scoped_document_request(
                "удали документы первой кассации"
            )
        )

    def test_genitive_collocation_phrases_are_detected(self) -> None:
        self.assertTrue(
            looks_like_appeal_scoped_document_request(
                "удали все документы апелляции в этой папке"
            )
        )
        self.assertTrue(
            looks_like_appeal_scoped_document_request(
                "удали документы судебного разбирательства"
            )
        )
        self.assertTrue(
            looks_like_appeal_scoped_document_request("удали документы кассации")
        )
        self.assertTrue(
            looks_like_appeal_scoped_document_request(
                "удали апелляционные документы в этой папке"
            )
        )
        self.assertTrue(
            looks_like_appeal_scoped_document_request(
                "удали кассационные документы"
            )
        )
        self.assertTrue(
            looks_like_appeal_scoped_document_request(
                "удали документы апелляционной жалобы"
            )
        )

    def test_plain_wipe_or_id_commands_are_not_appeal_scoped(self) -> None:
        self.assertFalse(
            looks_like_appeal_scoped_document_request("удали все документы в этой папке")
        )
        self.assertFalse(looks_like_appeal_scoped_document_request("удали документ 254"))
        self.assertFalse(
            looks_like_appeal_scoped_document_request(
                "удали все документы дела А40-12345/2025"
            )
        )
        self.assertFalse(
            looks_like_appeal_scoped_document_request(
                "перенеси все документы в папку Банкротство"
            )
        )
        self.assertFalse(
            looks_like_appeal_scoped_document_request(
                "удали все документы за заседание в этой папке"
            )
        )
        self.assertFalse(
            looks_like_appeal_scoped_document_request(
                "удали все документы за командировку в этой папке"
            )
        )
        self.assertFalse(
            looks_like_appeal_scoped_document_request(
                "удали все документы за дежурство в этой папке"
            )
        )
        self.assertFalse(
            looks_like_appeal_scoped_document_request(
                "удали все документы в папке Апелляция"
            )
        )
        self.assertFalse(
            looks_like_appeal_scoped_document_request(
                "удали все документы в папке Кассация"
            )
        )
        self.assertFalse(
            looks_like_appeal_scoped_document_request(
                "удали все документы в папке Рассмотрение"
            )
        )
        self.assertFalse(
            looks_like_appeal_scoped_document_request(
                "удали все ежедневные документы в этой папке"
            )
        )
        self.assertFalse(
            looks_like_appeal_scoped_document_request(
                "удали все судебные документы в этой папке"
            )
        )
        self.assertFalse(
            looks_like_appeal_scoped_document_request(
                "удали все документы за жалобу в этой папке"
            )
        )


class AppealOrdinalIdTests(unittest.TestCase):
    def test_ordinal_appeal_is_not_a_document_id(self) -> None:
        self.assertEqual(_parse_ids_like_main("удали документы 1-й апелляции"), [])
        self.assertEqual(_parse_ids_like_main("удали документ 1-я апелляция"), [])
        self.assertEqual(_parse_ids_like_main("удали файлы 1-й кассации"), [])
        self.assertEqual(_parse_ids_like_main("удали все документы 1-го рассмотрения"), [])
        self.assertEqual(_parse_ids_like_main("удали документы 1 разбирательства"), [])
        self.assertEqual(_parse_ids_like_main("удали документы 2-я кассация"), [])
        self.assertEqual(
            _parse_ids_like_main("удали документы 1-й апелляционной жалобы"), []
        )

    def test_real_ids_still_parse(self) -> None:
        self.assertEqual(_parse_ids_like_main("удали документ 254"), [254])
        self.assertEqual(_parse_ids_like_main("удали документы 1 и 2"), [1, 2])
        self.assertEqual(_parse_ids_like_main("удали документы [12] [18]"), [12, 18])
        self.assertEqual(
            _parse_ids_like_main("удали документ 254 за апелляцию"),
            [254],
        )
        self.assertEqual(
            _parse_ids_like_main("удали документ [18] 1-й апелляции"),
            [18],
        )


class BulkMutationGuardTests(unittest.TestCase):
    def test_appeal_scoped_all_deletes_are_blocked(self) -> None:
        self.assertTrue(
            appeal_blocks_bulk_document_mutation(
                "удали все документы за апелляцию в этой папке"
            )
        )
        self.assertTrue(
            appeal_blocks_bulk_document_mutation(
                "удали все документы за кассацию в этой папке"
            )
        )
        self.assertTrue(
            appeal_blocks_bulk_document_mutation(
                "удали все документы за рассмотрение в этой папке"
            )
        )
        self.assertTrue(
            appeal_blocks_bulk_document_mutation(
                "удали все документы за судебное разбирательство в этой папке"
            )
        )
        self.assertTrue(
            appeal_blocks_bulk_document_mutation("удали все документы на апелляции")
        )
        self.assertTrue(
            appeal_blocks_bulk_document_mutation(
                "удали все документы во время апелляции"
            )
        )
        self.assertTrue(
            appeal_blocks_bulk_document_mutation("удали документы 1-й апелляции")
        )

    def test_genitive_collocation_deletes_are_blocked(self) -> None:
        self.assertTrue(
            appeal_blocks_bulk_document_mutation(
                "удали все документы апелляции в этой папке"
            )
        )
        self.assertTrue(
            appeal_blocks_bulk_document_mutation(
                "удали документы судебного разбирательства"
            )
        )
        self.assertTrue(
            appeal_blocks_bulk_document_mutation(
                "удали апелляционные документы в этой папке"
            )
        )

    def test_pre_fix_folder_wipe_trigger_is_exactly_the_blocked_shape(self) -> None:
        """Pre-fix: wants_all + open folder hard-deleted every file because «за апелляцию» was ignored."""
        text = "удали все документы за апелляцию в этой папке"
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
        self.assertTrue(appeal_blocks_bulk_document_mutation(text))

    def test_cassation_wipe_trigger_is_the_same_shape(self) -> None:
        text = "удали все документы за кассацию в этой папке"
        low = text.lower()
        wants_all = "все документ" in low
        uses_open_folder = "этой папк" in low
        self.assertTrue(wants_all)
        self.assertTrue(uses_open_folder)
        self.assertIsNone(parse_calendar_period_ru(text))
        self.assertTrue(appeal_blocks_bulk_document_mutation(text))

    def test_review_wipe_trigger_is_the_same_shape(self) -> None:
        text = "удали все документы за рассмотрение в этой папке"
        low = text.lower()
        wants_all = "все документ" in low
        uses_open_folder = "этой папк" in low
        self.assertTrue(wants_all)
        self.assertTrue(uses_open_folder)
        self.assertIsNone(parse_calendar_period_ru(text))
        self.assertTrue(appeal_blocks_bulk_document_mutation(text))

    def test_proceedings_wipe_trigger_is_the_same_shape(self) -> None:
        text = "удали все документы за судебное разбирательство в этой папке"
        low = text.lower()
        wants_all = "все документ" in low
        uses_open_folder = "этой папк" in low
        self.assertTrue(wants_all)
        self.assertTrue(uses_open_folder)
        self.assertIsNone(parse_calendar_period_ru(text))
        self.assertTrue(appeal_blocks_bulk_document_mutation(text))

    def test_current_appeal_uses_active_folder_via_текущ(self) -> None:
        """«текущ» is an open-folder cue, so this wiped the active case without «в этой папке»."""
        text = "удали все документы за текущую апелляцию"
        low = text.lower()
        self.assertIn("все документ", low)
        self.assertIn("текущ", low)
        self.assertIsNone(parse_calendar_period_ru(text))
        self.assertTrue(appeal_blocks_bulk_document_mutation(text))

    def test_current_review_uses_active_folder_via_текущ(self) -> None:
        text = "удали все документы за текущее рассмотрение"
        low = text.lower()
        self.assertIn("все документ", low)
        self.assertIn("текущ", low)
        self.assertTrue(appeal_blocks_bulk_document_mutation(text))

    def test_ordinal_appeal_wrong_id_trigger(self) -> None:
        """Pre-fix: «1-й апелляции» parsed as document id 1 and hard-deleted that file."""
        text = "удали документы 1-й апелляции"
        self.assertEqual(_parse_ids_like_main(text), [])
        self.assertTrue(appeal_blocks_bulk_document_mutation(text))

    def test_existing_period_parser_does_not_see_appeal(self) -> None:
        """#69–#81 cover dates, months, weeks, years, seasons, holidays, отпуск, больничный, будни, смены, дежурство, командировка, заседание — not апелляция/кассация/рассмотрение."""
        self.assertIsNone(
            parse_calendar_period_ru(
                "удали все документы за апелляцию в этой папке"
            )
        )
        self.assertIsNone(
            parse_calendar_period_ru(
                "удали все документы за кассацию в этой папке"
            )
        )
        self.assertIsNone(
            parse_calendar_period_ru(
                "удали все документы за рассмотрение в этой папке"
            )
        )
        self.assertIsNone(
            parse_calendar_period_ru(
                "удали все документы за судебное разбирательство"
            )
        )
        self.assertIsNone(parse_calendar_period_ru("удали все документы на апелляции"))
        self.assertIsNone(parse_calendar_period_ru("удали все документы апелляции"))

    def test_explicit_id_still_allowed_even_if_appeal_is_mentioned(self) -> None:
        self.assertFalse(
            appeal_blocks_bulk_document_mutation(
                "удали документ 254 за апелляцию",
                explicit_document_ids=[254],
            )
        )

    def test_unscoped_folder_wipe_is_not_blocked(self) -> None:
        self.assertFalse(
            appeal_blocks_bulk_document_mutation("удали все документы в этой папке")
        )
        self.assertFalse(
            appeal_blocks_bulk_document_mutation(
                "удали все документы дела А40-12345/2025"
            )
        )
        self.assertFalse(appeal_blocks_bulk_document_mutation("удали документ 254"))
        self.assertFalse(
            appeal_blocks_bulk_document_mutation(
                "удали все документы в папке Апелляция"
            )
        )
        self.assertFalse(
            appeal_blocks_bulk_document_mutation(
                "удали все документы в папке Кассация"
            )
        )
        self.assertFalse(
            appeal_blocks_bulk_document_mutation(
                "удали все ежедневные документы в этой папке"
            )
        )
        self.assertFalse(
            appeal_blocks_bulk_document_mutation(
                "удали все судебные документы в этой папке"
            )
        )


if __name__ == "__main__":
    unittest.main()
