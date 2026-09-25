"""Letter / notice / summons chat must not wipe a folder or delete the wrong document.

«удали все документы за письмо в этой папке» used to match wants_all and hard-delete
every file in the open case because the document-type phrase was ignored.
«удали документы 1-го письма» took the leading digit as a document id.
"""

from __future__ import annotations

import re
import unittest

from app.calendar_correspondence import (
    correspondence_blocks_bulk_document_mutation,
    looks_like_correspondence_scoped_document_request,
    mask_correspondence_ordinals,
)
from app.ru_date_range import parse_calendar_period_ru


def _parse_ids_like_main(text: str) -> list[int]:
    """Mirror apps/api/app/main.py:parse_document_ids_for_delete_command after the fix."""
    raw = text or ""
    ids = [int(x) for x in re.findall(r"\[(\d+)\]", raw)]
    ids.extend(int(x) for x in re.findall(r"(?i)\bdoc[.:]?\s*(\d+)\b", raw))
    if ids:
        return sorted(set(ids))
    safe = mask_correspondence_ordinals(raw)
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
    """Document-id parser on main before this fix — digits of «1-го письма» become an id."""
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


class CorrespondenceScopeTests(unittest.TestCase):
    def test_correspondence_phrases_are_detected(self) -> None:
        for phrase in (
            "удали все документы за письмо в этой папке",
            "удали все документы за уведомление в этой папке",
            "удали все документы за извещение в этой папке",
            "удали все документы за повестку в этой папке",
            "удали все документы по письму",
            "удали все документы на уведомлении",
            "удали все документы в извещении",
            "удали все документы по повестке",
            "удали все документы во время письма",
            "удали все документы за гарантийное письмо в этой папке",
            "удали все документы за судебную повестку",
            "удали все документы за почтовое уведомление",
            "удали все документы за заказное извещение",
        ):
            self.assertTrue(
                looks_like_correspondence_scoped_document_request(phrase),
                phrase,
            )

    def test_demonstrative_and_current_correspondence_are_detected(self) -> None:
        self.assertTrue(
            looks_like_correspondence_scoped_document_request(
                "удали все документы за текущее уведомление"
            )
        )
        self.assertTrue(
            looks_like_correspondence_scoped_document_request("удали документы этого письма")
        )
        self.assertTrue(
            looks_like_correspondence_scoped_document_request("удали файлы этой повестки")
        )
        self.assertTrue(
            looks_like_correspondence_scoped_document_request(
                "удали все документы за открытое письмо"
            )
        )

    def test_ordinal_correspondence_is_detected(self) -> None:
        self.assertTrue(
            looks_like_correspondence_scoped_document_request("удали документы 1-го письма")
        )
        self.assertTrue(
            looks_like_correspondence_scoped_document_request("удали документы 1-го уведомления")
        )
        self.assertTrue(
            looks_like_correspondence_scoped_document_request("удали документы 1-го извещения")
        )
        self.assertTrue(
            looks_like_correspondence_scoped_document_request("удали документы 1-й повестки")
        )
        self.assertTrue(
            looks_like_correspondence_scoped_document_request("удали документы первого письма")
        )

    def test_genitive_collocation_is_detected(self) -> None:
        self.assertTrue(
            looks_like_correspondence_scoped_document_request(
                "удали все документы письма в этой папке"
            )
        )
        self.assertTrue(
            looks_like_correspondence_scoped_document_request("удали документы уведомления")
        )
        self.assertTrue(
            looks_like_correspondence_scoped_document_request("удали документы извещения")
        )
        self.assertTrue(
            looks_like_correspondence_scoped_document_request("удали документы повестки")
        )
        self.assertTrue(
            looks_like_correspondence_scoped_document_request("удали документы писем")
        )

    def test_unscoped_and_lookalike_phrases_are_not_detected(self) -> None:
        for phrase in (
            "удали все документы в этой папке",
            "удали документ 254",
            "удали все документы дела А40-12345/2025",
            "удали все документы в папке Письмо",
            "удали все документы в папке Уведомление",
            "удали все документы в папке Извещение",
            "удали все документы в папке Повестка",
            "удали все документы за человека в этой папке",
            "удали все документы за приказ в этой папке",
            "удали все документы за выписку в этой папке",
            "удали все письменные документы в этой папке",
            "удали все документы за письменное подтверждение",
            "удали все документы за актуальный отчёт",
            "уведомить о заседании",
            "известить стороны",
            "удали все документы по повести",
        ):
            self.assertFalse(
                looks_like_correspondence_scoped_document_request(phrase),
                phrase,
            )


class CorrespondenceOrdinalIdTests(unittest.TestCase):
    def test_pre_fix_parser_took_ordinal_as_document_id(self) -> None:
        self.assertEqual(_pre_fix_parse_ids("удали документы 1-го письма"), [1])
        self.assertEqual(_pre_fix_parse_ids("удали документы 1-го уведомления"), [1])
        self.assertEqual(_pre_fix_parse_ids("удали документы 1-го извещения"), [1])
        self.assertEqual(_pre_fix_parse_ids("удали документы 1-й повестки"), [1])

    def test_ordinal_correspondence_is_not_a_document_id(self) -> None:
        self.assertEqual(_parse_ids_like_main("удали документы 1-го письма"), [])
        self.assertEqual(_parse_ids_like_main("удали документы 1-го уведомления"), [])
        self.assertEqual(_parse_ids_like_main("удали документы 1-го извещения"), [])
        self.assertEqual(_parse_ids_like_main("удали документы 1-й повестки"), [])
        self.assertEqual(_parse_ids_like_main("удали все документы 1-е извещение"), [])
        self.assertEqual(_parse_ids_like_main("удали документы 1 письма"), [])
        self.assertEqual(_parse_ids_like_main("удали документы 2-е уведомление"), [])

    def test_real_ids_still_parse(self) -> None:
        self.assertEqual(_parse_ids_like_main("удали документ 254"), [254])
        self.assertEqual(_parse_ids_like_main("удали документы 1 и 2"), [1, 2])
        self.assertEqual(_parse_ids_like_main("удали документы [12] [18]"), [12, 18])
        self.assertEqual(
            _parse_ids_like_main("удали документ 254 за письмо"),
            [254],
        )
        self.assertEqual(
            _parse_ids_like_main("удали документ [18] 1-го уведомления"),
            [18],
        )
        self.assertEqual(
            _parse_ids_like_main("удали документ 12 за повестку"),
            [12],
        )

    def test_human_ordinal_is_not_masked_as_letter(self) -> None:
        self.assertFalse(
            looks_like_correspondence_scoped_document_request("удали документы 1-го человека")
        )
        self.assertEqual(_parse_ids_like_main("удали документы 1-го человека"), [1])


class BulkMutationGuardTests(unittest.TestCase):
    def test_correspondence_scoped_all_deletes_are_blocked(self) -> None:
        for phrase in (
            "удали все документы за письмо в этой папке",
            "удали все документы за уведомление в этой папке",
            "удали все документы за извещение в этой папке",
            "удали все документы за повестку в этой папке",
            "удали все документы по письму",
            "удали все документы во время извещения",
            "удали документы 1-го письма",
        ):
            self.assertTrue(correspondence_blocks_bulk_document_mutation(phrase), phrase)

    def test_genitive_collocation_deletes_are_blocked(self) -> None:
        self.assertTrue(
            correspondence_blocks_bulk_document_mutation(
                "удали все документы письма в этой папке"
            )
        )
        self.assertTrue(
            correspondence_blocks_bulk_document_mutation("удали документы уведомления")
        )
        self.assertTrue(
            correspondence_blocks_bulk_document_mutation(
                "удали документы повестки в этой папке"
            )
        )

    def test_pre_fix_folder_wipe_trigger_is_exactly_the_blocked_shape(self) -> None:
        """Pre-fix: wants_all + open folder hard-deleted every file because «за письмо» was ignored."""
        for text in (
            "удали все документы за письмо в этой папке",
            "удали все документы за уведомление в этой папке",
            "удали все документы за извещение в этой папке",
            "удали все документы за повестку в этой папке",
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
            self.assertTrue(correspondence_blocks_bulk_document_mutation(text), text)

    def test_current_notice_uses_active_folder_via_текущ(self) -> None:
        """«текущ» is an open-folder cue, so this wiped the active case without «в этой папке»."""
        text = "удали все документы за текущее уведомление"
        low = text.lower()
        self.assertIn("все документ", low)
        self.assertIn("текущ", low)
        self.assertIsNone(parse_calendar_period_ru(text))
        self.assertTrue(correspondence_blocks_bulk_document_mutation(text))

    def test_open_letter_uses_active_folder_via_открыт(self) -> None:
        """«открыт» is an open-folder cue inside «открытое письмо»."""
        text = "удали все документы за открытое письмо"
        low = text.lower()
        self.assertIn("все документ", low)
        self.assertIn("открыт", low)
        self.assertIsNone(parse_calendar_period_ru(text))
        self.assertTrue(correspondence_blocks_bulk_document_mutation(text))

    def test_ordinal_letter_wrong_id_trigger(self) -> None:
        """Pre-fix: «1-го письма» parsed as document id 1 and hard-deleted that file."""
        text = "удали документы 1-го письма"
        self.assertEqual(_pre_fix_parse_ids(text), [1])
        self.assertEqual(_parse_ids_like_main(text), [])
        self.assertTrue(correspondence_blocks_bulk_document_mutation(text))

    def test_existing_period_parser_does_not_see_correspondence_scope(self) -> None:
        for phrase in (
            "удали все документы за письмо в этой папке",
            "удали все документы за уведомление в этой папке",
            "удали все документы за извещение в этой папке",
            "удали все документы за повестку",
            "удали все документы по письму",
            "удали все документы письма",
        ):
            self.assertIsNone(parse_calendar_period_ru(phrase), phrase)

    def test_named_case_move_dumps_source_folder_pre_fix(self) -> None:
        """«перенеси все документы дела А40-… за письмо в папку …» executes move-all."""
        text = "перенеси все документы дела А40-12345/2025 за письмо в папку Архив"
        low = text.lower()
        self.assertTrue(any(k in low for k in ["перенеси", "все документы", "в папку"]))
        self.assertIn("папк", low)
        self.assertTrue(correspondence_blocks_bulk_document_mutation(text))

    def test_explicit_id_still_allowed_even_if_correspondence_is_mentioned(self) -> None:
        self.assertFalse(
            correspondence_blocks_bulk_document_mutation(
                "удали документ 254 за письмо",
                explicit_document_ids=[254],
            )
        )

    def test_unscoped_folder_wipe_is_not_blocked(self) -> None:
        for phrase in (
            "удали все документы в этой папке",
            "удали все документы дела А40-12345/2025",
            "удали документ 254",
            "удали все документы в папке Письмо",
            "удали все документы в папке Повестка",
            "удали все документы за приказ в этой папке",
            "удали все документы за человека в этой папке",
            "удали все письменные документы в этой папке",
        ):
            self.assertFalse(correspondence_blocks_bulk_document_mutation(phrase), phrase)


if __name__ == "__main__":
    unittest.main()
