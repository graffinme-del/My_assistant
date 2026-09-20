"""Agreement / receipt / invoice / waybill chat must not wipe a folder or delete the wrong document.

«удали все документы за соглашение в этой папке» used to match wants_all and hard-delete
every file in the open case because the agreement phrase was ignored.
«удали документы 1-го соглашения» took the leading digit as a document id.
"""

from __future__ import annotations

import re
import unittest

from app.calendar_agreement import (
    agreement_blocks_bulk_document_mutation,
    looks_like_agreement_scoped_document_request,
    mask_agreement_ordinals,
)
from app.ru_date_range import parse_calendar_period_ru


def _parse_ids_like_main(text: str) -> list[int]:
    """Mirror apps/api/app/main.py:parse_document_ids_for_delete_command after the fix."""
    raw = text or ""
    ids = [int(x) for x in re.findall(r"\[(\d+)\]", raw)]
    ids.extend(int(x) for x in re.findall(r"(?i)\bdoc[.:]?\s*(\d+)\b", raw))
    if ids:
        return sorted(set(ids))
    safe = mask_agreement_ordinals(raw)
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
    """Document-id parser on main before this fix — digits of «1-го соглашения» become an id."""
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


class AgreementScopeTests(unittest.TestCase):
    def test_agreement_phrases_are_detected(self) -> None:
        self.assertTrue(
            looks_like_agreement_scoped_document_request(
                "удали все документы за соглашение в этой папке"
            )
        )
        self.assertTrue(
            looks_like_agreement_scoped_document_request(
                "удали все документы за расписку в этой папке"
            )
        )
        self.assertTrue(
            looks_like_agreement_scoped_document_request(
                "удали все документы за счёт в этой папке"
            )
        )
        self.assertTrue(
            looks_like_agreement_scoped_document_request(
                "удали все документы за счет в этой папке"
            )
        )
        self.assertTrue(
            looks_like_agreement_scoped_document_request(
                "удали все документы за накладную в этой папке"
            )
        )
        self.assertTrue(
            looks_like_agreement_scoped_document_request(
                "удали все документы за мировое соглашение в этой папке"
            )
        )
        self.assertTrue(
            looks_like_agreement_scoped_document_request(
                "удали все документы за товарную накладную в этой папке"
            )
        )
        self.assertTrue(
            looks_like_agreement_scoped_document_request(
                "удали все документы за дополнительное соглашение в этой папке"
            )
        )
        self.assertTrue(
            looks_like_agreement_scoped_document_request("удали все документы на соглашении")
        )
        self.assertTrue(
            looks_like_agreement_scoped_document_request(
                "удали все документы по расписке"
            )
        )
        self.assertTrue(
            looks_like_agreement_scoped_document_request(
                "удали все документы во время счёта"
            )
        )
        self.assertTrue(
            looks_like_agreement_scoped_document_request(
                "перенеси все документы за соглашение в папку Банкротство"
            )
        )
        self.assertTrue(
            looks_like_agreement_scoped_document_request(
                "удали все документы за соглашение дела А40-12345/2025"
            )
        )
        self.assertTrue(
            looks_like_agreement_scoped_document_request("удали документы первого соглашения")
        )
        self.assertTrue(
            looks_like_agreement_scoped_document_request(
                "удали документы первой расписки"
            )
        )

    def test_genitive_collocation_phrases_are_detected(self) -> None:
        self.assertTrue(
            looks_like_agreement_scoped_document_request(
                "удали все документы соглашения в этой папке"
            )
        )
        self.assertTrue(
            looks_like_agreement_scoped_document_request("удали документы расписки")
        )
        self.assertTrue(
            looks_like_agreement_scoped_document_request("удали документы счёта")
        )
        self.assertTrue(
            looks_like_agreement_scoped_document_request("удали документы накладной")
        )
        self.assertTrue(
            looks_like_agreement_scoped_document_request(
                "удали счётные документы в этой папке"
            )
        )
        self.assertTrue(
            looks_like_agreement_scoped_document_request(
                "удали счетные документы в этой папке"
            )
        )
        self.assertTrue(
            looks_like_agreement_scoped_document_request(
                "удали накладные документы в этой папке"
            )
        )

    def test_plain_wipe_or_id_commands_are_not_agreement_scoped(self) -> None:
        self.assertFalse(
            looks_like_agreement_scoped_document_request("удали все документы в этой папке")
        )
        self.assertFalse(looks_like_agreement_scoped_document_request("удали документ 254"))
        self.assertFalse(
            looks_like_agreement_scoped_document_request(
                "удали все документы дела А40-12345/2025"
            )
        )
        self.assertFalse(
            looks_like_agreement_scoped_document_request(
                "перенеси все документы в папку Банкротство"
            )
        )
        self.assertFalse(
            looks_like_agreement_scoped_document_request(
                "удали все документы за договор в этой папке"
            )
        )
        self.assertFalse(
            looks_like_agreement_scoped_document_request(
                "удали все документы за жалобу в этой папке"
            )
        )
        self.assertFalse(
            looks_like_agreement_scoped_document_request(
                "удали все документы за иск в этой папке"
            )
        )
        self.assertFalse(
            looks_like_agreement_scoped_document_request(
                "удали все документы в папке Соглашение"
            )
        )
        self.assertFalse(
            looks_like_agreement_scoped_document_request(
                "удали все документы в папке Расписка"
            )
        )
        self.assertFalse(
            looks_like_agreement_scoped_document_request(
                "удали все документы в папке Счёт"
            )
        )
        self.assertFalse(
            looks_like_agreement_scoped_document_request(
                "удали все документы в папке Накладная"
            )
        )
        self.assertFalse(
            looks_like_agreement_scoped_document_request(
                "удали все документы по согласованности сторон в этой папке"
            )
        )
        self.assertFalse(
            looks_like_agreement_scoped_document_request(
                "удали все документы расписания в этой папке"
            )
        )
        self.assertFalse(
            looks_like_agreement_scoped_document_request(
                "удали все документы за счетчик в этой папке"
            )
        )


class AgreementOrdinalIdTests(unittest.TestCase):
    def test_pre_fix_parser_took_ordinal_as_document_id(self) -> None:
        self.assertEqual(_pre_fix_parse_ids("удали документы 1-го соглашения"), [1])
        self.assertEqual(_pre_fix_parse_ids("удали документы 1-й расписки"), [1])
        self.assertEqual(_pre_fix_parse_ids("удали файлы 1-го счёта"), [1])
        self.assertEqual(_pre_fix_parse_ids("удали файлы 1-й накладной"), [1])
        self.assertEqual(_pre_fix_parse_ids("удали документы 1-х соглашений"), [1])

    def test_ordinal_agreement_is_not_a_document_id(self) -> None:
        self.assertEqual(_parse_ids_like_main("удали документы 1-го соглашения"), [])
        self.assertEqual(_parse_ids_like_main("удали документ 1-е соглашение"), [])
        self.assertEqual(_parse_ids_like_main("удали файлы 1-й расписки"), [])
        self.assertEqual(_parse_ids_like_main("удали все документы 1-го счёта"), [])
        self.assertEqual(_parse_ids_like_main("удали документы 1 соглашения"), [])
        self.assertEqual(_parse_ids_like_main("удали документы 2-я накладная"), [])
        self.assertEqual(_parse_ids_like_main("удали документы 1-й накладной"), [])

    def test_real_ids_still_parse(self) -> None:
        self.assertEqual(_parse_ids_like_main("удали документ 254"), [254])
        self.assertEqual(_parse_ids_like_main("удали документы 1 и 2"), [1, 2])
        self.assertEqual(_parse_ids_like_main("удали документы [12] [18]"), [12, 18])
        self.assertEqual(
            _parse_ids_like_main("удали документ 254 за соглашение"),
            [254],
        )
        self.assertEqual(
            _parse_ids_like_main("удали документ [18] 1-го соглашения"),
            [18],
        )


class BulkMutationGuardTests(unittest.TestCase):
    def test_agreement_scoped_all_deletes_are_blocked(self) -> None:
        self.assertTrue(
            agreement_blocks_bulk_document_mutation(
                "удали все документы за соглашение в этой папке"
            )
        )
        self.assertTrue(
            agreement_blocks_bulk_document_mutation(
                "удали все документы за расписку в этой папке"
            )
        )
        self.assertTrue(
            agreement_blocks_bulk_document_mutation(
                "удали все документы за счёт в этой папке"
            )
        )
        self.assertTrue(
            agreement_blocks_bulk_document_mutation(
                "удали все документы за накладную в этой папке"
            )
        )
        self.assertTrue(
            agreement_blocks_bulk_document_mutation("удали все документы на соглашении")
        )
        self.assertTrue(
            agreement_blocks_bulk_document_mutation(
                "удали все документы во время расписки"
            )
        )
        self.assertTrue(
            agreement_blocks_bulk_document_mutation("удали документы 1-го соглашения")
        )

    def test_genitive_collocation_deletes_are_blocked(self) -> None:
        self.assertTrue(
            agreement_blocks_bulk_document_mutation(
                "удали все документы соглашения в этой папке"
            )
        )
        self.assertTrue(
            agreement_blocks_bulk_document_mutation("удали документы расписки")
        )
        self.assertTrue(
            agreement_blocks_bulk_document_mutation(
                "удали счётные документы в этой папке"
            )
        )

    def test_pre_fix_folder_wipe_trigger_is_exactly_the_blocked_shape(self) -> None:
        """Pre-fix: wants_all + open folder hard-deleted every file because «за соглашение» was ignored."""
        text = "удали все документы за соглашение в этой папке"
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
        self.assertTrue(agreement_blocks_bulk_document_mutation(text))

    def test_receipt_wipe_trigger_is_the_same_shape(self) -> None:
        text = "удали все документы за расписку в этой папке"
        low = text.lower()
        wants_all = "все документ" in low
        uses_open_folder = "этой папк" in low
        self.assertTrue(wants_all)
        self.assertTrue(uses_open_folder)
        self.assertIsNone(parse_calendar_period_ru(text))
        self.assertTrue(agreement_blocks_bulk_document_mutation(text))

    def test_invoice_wipe_trigger_is_the_same_shape(self) -> None:
        text = "удали все документы за счёт в этой папке"
        low = text.lower()
        wants_all = "все документ" in low
        uses_open_folder = "этой папк" in low
        self.assertTrue(wants_all)
        self.assertTrue(uses_open_folder)
        self.assertIsNone(parse_calendar_period_ru(text))
        self.assertTrue(agreement_blocks_bulk_document_mutation(text))

    def test_waybill_wipe_trigger_is_the_same_shape(self) -> None:
        text = "удали все документы за накладную в этой папке"
        low = text.lower()
        wants_all = "все документ" in low
        uses_open_folder = "этой папк" in low
        self.assertTrue(wants_all)
        self.assertTrue(uses_open_folder)
        self.assertIsNone(parse_calendar_period_ru(text))
        self.assertTrue(agreement_blocks_bulk_document_mutation(text))

    def test_current_agreement_uses_active_folder_via_текущ(self) -> None:
        """«текущ» is an open-folder cue, so this wiped the active case without «в этой папке»."""
        text = "удали все документы за текущее соглашение"
        low = text.lower()
        self.assertIn("все документ", low)
        self.assertIn("текущ", low)
        self.assertIsNone(parse_calendar_period_ru(text))
        self.assertTrue(agreement_blocks_bulk_document_mutation(text))

    def test_current_receipt_uses_active_folder_via_текущ(self) -> None:
        text = "удали все документы за текущую расписку"
        low = text.lower()
        self.assertIn("все документ", low)
        self.assertIn("текущ", low)
        self.assertTrue(agreement_blocks_bulk_document_mutation(text))

    def test_ordinal_agreement_wrong_id_trigger(self) -> None:
        """Pre-fix: «1-го соглашения» parsed as document id 1 and hard-deleted that file."""
        text = "удали документы 1-го соглашения"
        self.assertEqual(_pre_fix_parse_ids(text), [1])
        self.assertEqual(_parse_ids_like_main(text), [])
        self.assertTrue(agreement_blocks_bulk_document_mutation(text))

    def test_existing_period_parser_does_not_see_agreement(self) -> None:
        """#69–#87 cover dates through contract/certificate — not соглашение/расписка/счёт/накладная."""
        self.assertIsNone(
            parse_calendar_period_ru("удали все документы за соглашение в этой папке")
        )
        self.assertIsNone(
            parse_calendar_period_ru("удали все документы за расписку в этой папке")
        )
        self.assertIsNone(
            parse_calendar_period_ru("удали все документы за счёт в этой папке")
        )
        self.assertIsNone(parse_calendar_period_ru("удали все документы за накладную"))
        self.assertIsNone(parse_calendar_period_ru("удали все документы на соглашении"))
        self.assertIsNone(parse_calendar_period_ru("удали все документы соглашения"))

    def test_explicit_id_still_allowed_even_if_agreement_is_mentioned(self) -> None:
        self.assertFalse(
            agreement_blocks_bulk_document_mutation(
                "удали документ 254 за соглашение",
                explicit_document_ids=[254],
            )
        )

    def test_unscoped_folder_wipe_is_not_blocked(self) -> None:
        self.assertFalse(
            agreement_blocks_bulk_document_mutation("удали все документы в этой папке")
        )
        self.assertFalse(
            agreement_blocks_bulk_document_mutation(
                "удали все документы дела А40-12345/2025"
            )
        )
        self.assertFalse(agreement_blocks_bulk_document_mutation("удали документ 254"))
        self.assertFalse(
            agreement_blocks_bulk_document_mutation("удали все документы в папке Соглашение")
        )
        self.assertFalse(
            agreement_blocks_bulk_document_mutation(
                "удали все документы в папке Расписка"
            )
        )
        self.assertFalse(
            agreement_blocks_bulk_document_mutation(
                "удали все документы за договор в этой папке"
            )
        )


if __name__ == "__main__":
    unittest.main()
