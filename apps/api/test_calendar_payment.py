"""Payment-receipt / check / specification / offer chat must not wipe a folder or delete the wrong document.

«удали все документы за квитанцию в этой папке» used to match wants_all and hard-delete
every file in the open case because the receipt phrase was ignored.
«удали документы 1-й квитанции» took the leading digit as a document id.
"""

from __future__ import annotations

import re
import unittest

from app.calendar_payment import (
    looks_like_payment_scoped_document_request,
    mask_payment_ordinals,
    payment_blocks_bulk_document_mutation,
)
from app.ru_date_range import parse_calendar_period_ru


def _parse_ids_like_main(text: str) -> list[int]:
    """Mirror apps/api/app/main.py:parse_document_ids_for_delete_command after the fix."""
    raw = text or ""
    ids = [int(x) for x in re.findall(r"\[(\d+)\]", raw)]
    ids.extend(int(x) for x in re.findall(r"(?i)\bdoc[.:]?\s*(\d+)\b", raw))
    if ids:
        return sorted(set(ids))
    safe = mask_payment_ordinals(raw)
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
    """Document-id parser on main before this fix — digits of «1-й квитанции» become an id."""
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


class PaymentScopeTests(unittest.TestCase):
    def test_payment_phrases_are_detected(self) -> None:
        self.assertTrue(
            looks_like_payment_scoped_document_request(
                "удали все документы за квитанцию в этой папке"
            )
        )
        self.assertTrue(
            looks_like_payment_scoped_document_request(
                "удали все документы за чек в этой папке"
            )
        )
        self.assertTrue(
            looks_like_payment_scoped_document_request(
                "удали все документы за спецификацию в этой папке"
            )
        )
        self.assertTrue(
            looks_like_payment_scoped_document_request(
                "удали все документы за оферту в этой папке"
            )
        )
        self.assertTrue(
            looks_like_payment_scoped_document_request("удали все документы на квитанции")
        )
        self.assertTrue(
            looks_like_payment_scoped_document_request("удали все документы по чеку")
        )
        self.assertTrue(
            looks_like_payment_scoped_document_request(
                "удали все документы во время квитанции"
            )
        )
        self.assertTrue(
            looks_like_payment_scoped_document_request("удали все документы на оферте")
        )
        self.assertTrue(
            looks_like_payment_scoped_document_request(
                "удали все документы за кассовый чек в этой папке"
            )
        )
        self.assertTrue(
            looks_like_payment_scoped_document_request(
                "удали все документы за публичную оферту"
            )
        )
        self.assertTrue(
            looks_like_payment_scoped_document_request(
                "удали все документы за техническую спецификацию"
            )
        )
        self.assertTrue(
            looks_like_payment_scoped_document_request(
                "удали все документы за платёжную квитанцию"
            )
        )

    def test_demonstrative_and_current_payment_are_detected(self) -> None:
        self.assertTrue(
            looks_like_payment_scoped_document_request(
                "удали все документы за текущую квитанцию"
            )
        )
        self.assertTrue(
            looks_like_payment_scoped_document_request("удали документы этой оферты")
        )
        self.assertTrue(
            looks_like_payment_scoped_document_request("удали файлы текущего чека")
        )

    def test_ordinal_payment_is_detected(self) -> None:
        self.assertTrue(
            looks_like_payment_scoped_document_request("удали документы 1-й квитанции")
        )
        self.assertTrue(
            looks_like_payment_scoped_document_request("удали документы 1-го чека")
        )
        self.assertTrue(
            looks_like_payment_scoped_document_request("удали документы первой оферты")
        )
        self.assertTrue(
            looks_like_payment_scoped_document_request(
                "удали файлы 1-й спецификации"
            )
        )

    def test_genitive_collocation_is_detected(self) -> None:
        self.assertTrue(
            looks_like_payment_scoped_document_request(
                "удали все документы квитанции в этой папке"
            )
        )
        self.assertTrue(looks_like_payment_scoped_document_request("удали документы чека"))
        self.assertTrue(
            looks_like_payment_scoped_document_request("удали документы спецификации")
        )
        self.assertTrue(
            looks_like_payment_scoped_document_request("удали документы оферты")
        )
        self.assertTrue(
            looks_like_payment_scoped_document_request(
                "удали чековые документы в этой папке"
            )
        )
        self.assertTrue(
            looks_like_payment_scoped_document_request("удали офертные документы")
        )

    def test_unscoped_and_lookalike_phrases_are_not_detected(self) -> None:
        self.assertFalse(
            looks_like_payment_scoped_document_request("удали все документы в этой папке")
        )
        self.assertFalse(looks_like_payment_scoped_document_request("удали документ 254"))
        self.assertFalse(
            looks_like_payment_scoped_document_request(
                "удали все документы дела А40-12345/2025"
            )
        )
        self.assertFalse(
            looks_like_payment_scoped_document_request(
                "удали все документы в папке Квитанция"
            )
        )
        self.assertFalse(
            looks_like_payment_scoped_document_request("удали все документы в папке Чек")
        )
        self.assertFalse(
            looks_like_payment_scoped_document_request(
                "удали все документы в папке Спецификация"
            )
        )
        self.assertFalse(
            looks_like_payment_scoped_document_request(
                "удали все документы в папке Оферта"
            )
        )
        self.assertFalse(
            looks_like_payment_scoped_document_request(
                "удали все документы за человека в этой папке"
            )
        )
        self.assertFalse(
            looks_like_payment_scoped_document_request(
                "удали все документы за соглашение в этой папке"
            )
        )
        self.assertFalse(
            looks_like_payment_scoped_document_request(
                "удали все документы за договор в этой папке"
            )
        )
        self.assertFalse(
            looks_like_payment_scoped_document_request(
                "удали все документы за специфику в этой папке"
            )
        )


class PaymentOrdinalIdTests(unittest.TestCase):
    def test_pre_fix_parser_took_ordinal_as_document_id(self) -> None:
        self.assertEqual(_pre_fix_parse_ids("удали документы 1-й квитанции"), [1])
        self.assertEqual(_pre_fix_parse_ids("удали документы 1-го чека"), [1])
        self.assertEqual(_pre_fix_parse_ids("удали файлы 1-й спецификации"), [1])
        self.assertEqual(_pre_fix_parse_ids("удали файлы 1-й оферты"), [1])
        self.assertEqual(_pre_fix_parse_ids("удали документы 1-х квитанций"), [1])

    def test_ordinal_payment_is_not_a_document_id(self) -> None:
        self.assertEqual(_parse_ids_like_main("удали документы 1-й квитанции"), [])
        self.assertEqual(_parse_ids_like_main("удали документ 1-е квитанция"), [])
        self.assertEqual(_parse_ids_like_main("удали файлы 1-го чека"), [])
        self.assertEqual(_parse_ids_like_main("удали все документы 1-й спецификации"), [])
        self.assertEqual(_parse_ids_like_main("удали документы 1 квитанции"), [])
        self.assertEqual(_parse_ids_like_main("удали документы 2-я оферта"), [])
        self.assertEqual(_parse_ids_like_main("удали документы 1-й оферты"), [])

    def test_real_ids_still_parse(self) -> None:
        self.assertEqual(_parse_ids_like_main("удали документ 254"), [254])
        self.assertEqual(_parse_ids_like_main("удали документы 1 и 2"), [1, 2])
        self.assertEqual(_parse_ids_like_main("удали документы [12] [18]"), [12, 18])
        self.assertEqual(
            _parse_ids_like_main("удали документ 254 за квитанцию"),
            [254],
        )
        self.assertEqual(
            _parse_ids_like_main("удали документ [18] 1-й квитанции"),
            [18],
        )
        self.assertEqual(
            _parse_ids_like_main("удали документ 12 за чек"),
            [12],
        )

    def test_человек_ordinal_is_not_masked_as_check(self) -> None:
        self.assertFalse(
            looks_like_payment_scoped_document_request("удали документы 1-го человека")
        )
        self.assertEqual(_parse_ids_like_main("удали документы 1-го человека"), [1])


class BulkMutationGuardTests(unittest.TestCase):
    def test_payment_scoped_all_deletes_are_blocked(self) -> None:
        self.assertTrue(
            payment_blocks_bulk_document_mutation(
                "удали все документы за квитанцию в этой папке"
            )
        )
        self.assertTrue(
            payment_blocks_bulk_document_mutation(
                "удали все документы за чек в этой папке"
            )
        )
        self.assertTrue(
            payment_blocks_bulk_document_mutation(
                "удали все документы за спецификацию в этой папке"
            )
        )
        self.assertTrue(
            payment_blocks_bulk_document_mutation(
                "удали все документы за оферту в этой папке"
            )
        )
        self.assertTrue(
            payment_blocks_bulk_document_mutation("удали все документы на квитанции")
        )
        self.assertTrue(
            payment_blocks_bulk_document_mutation("удали все документы во время чека")
        )
        self.assertTrue(
            payment_blocks_bulk_document_mutation("удали документы 1-й квитанции")
        )

    def test_genitive_collocation_deletes_are_blocked(self) -> None:
        self.assertTrue(
            payment_blocks_bulk_document_mutation(
                "удали все документы квитанции в этой папке"
            )
        )
        self.assertTrue(payment_blocks_bulk_document_mutation("удали документы чека"))
        self.assertTrue(
            payment_blocks_bulk_document_mutation(
                "удали чековые документы в этой папке"
            )
        )

    def test_pre_fix_folder_wipe_trigger_is_exactly_the_blocked_shape(self) -> None:
        """Pre-fix: wants_all + open folder hard-deleted every file because «за квитанцию» was ignored."""
        text = "удали все документы за квитанцию в этой папке"
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
        self.assertTrue(payment_blocks_bulk_document_mutation(text))

    def test_check_wipe_trigger_is_the_same_shape(self) -> None:
        text = "удали все документы за чек в этой папке"
        low = text.lower()
        wants_all = "все документ" in low
        uses_open_folder = "этой папк" in low
        self.assertTrue(wants_all)
        self.assertTrue(uses_open_folder)
        self.assertIsNone(parse_calendar_period_ru(text))
        self.assertTrue(payment_blocks_bulk_document_mutation(text))

    def test_specification_wipe_trigger_is_the_same_shape(self) -> None:
        text = "удали все документы за спецификацию в этой папке"
        low = text.lower()
        wants_all = "все документ" in low
        uses_open_folder = "этой папк" in low
        self.assertTrue(wants_all)
        self.assertTrue(uses_open_folder)
        self.assertIsNone(parse_calendar_period_ru(text))
        self.assertTrue(payment_blocks_bulk_document_mutation(text))

    def test_offer_wipe_trigger_is_the_same_shape(self) -> None:
        text = "удали все документы за оферту в этой папке"
        low = text.lower()
        wants_all = "все документ" in low
        uses_open_folder = "этой папк" in low
        self.assertTrue(wants_all)
        self.assertTrue(uses_open_folder)
        self.assertIsNone(parse_calendar_period_ru(text))
        self.assertTrue(payment_blocks_bulk_document_mutation(text))

    def test_current_receipt_uses_active_folder_via_текущ(self) -> None:
        """«текущ» is an open-folder cue, so this wiped the active case without «в этой папке»."""
        text = "удали все документы за текущую квитанцию"
        low = text.lower()
        self.assertIn("все документ", low)
        self.assertIn("текущ", low)
        self.assertIsNone(parse_calendar_period_ru(text))
        self.assertTrue(payment_blocks_bulk_document_mutation(text))

    def test_current_check_uses_active_folder_via_текущ(self) -> None:
        text = "удали все документы за текущий чек"
        low = text.lower()
        self.assertIn("все документ", low)
        self.assertIn("текущ", low)
        self.assertTrue(payment_blocks_bulk_document_mutation(text))

    def test_ordinal_payment_wrong_id_trigger(self) -> None:
        """Pre-fix: «1-й квитанции» parsed as document id 1 and hard-deleted that file."""
        text = "удали документы 1-й квитанции"
        self.assertEqual(_pre_fix_parse_ids(text), [1])
        self.assertEqual(_parse_ids_like_main(text), [])
        self.assertTrue(payment_blocks_bulk_document_mutation(text))

    def test_existing_period_parser_does_not_see_payment(self) -> None:
        """#69–#88 cover dates through agreement/invoice — not квитанция/чек/спецификация/оферта."""
        self.assertIsNone(
            parse_calendar_period_ru("удали все документы за квитанцию в этой папке")
        )
        self.assertIsNone(
            parse_calendar_period_ru("удали все документы за чек в этой папке")
        )
        self.assertIsNone(
            parse_calendar_period_ru("удали все документы за спецификацию в этой папке")
        )
        self.assertIsNone(parse_calendar_period_ru("удали все документы за оферту"))
        self.assertIsNone(parse_calendar_period_ru("удали все документы на квитанции"))
        self.assertIsNone(parse_calendar_period_ru("удали все документы квитанции"))

    def test_named_case_move_dumps_source_folder_pre_fix(self) -> None:
        """«перенеси все документы дела А40-… за квитанцию в папку …» executes move-all."""
        text = "перенеси все документы дела А40-12345/2025 за квитанцию в папку Архив"
        low = text.lower()
        self.assertTrue(any(k in low for k in ["перенеси", "все документы", "в папку"]))
        self.assertIn("папк", low)
        self.assertTrue(payment_blocks_bulk_document_mutation(text))

    def test_explicit_id_still_allowed_even_if_payment_is_mentioned(self) -> None:
        self.assertFalse(
            payment_blocks_bulk_document_mutation(
                "удали документ 254 за квитанцию",
                explicit_document_ids=[254],
            )
        )

    def test_unscoped_folder_wipe_is_not_blocked(self) -> None:
        self.assertFalse(
            payment_blocks_bulk_document_mutation("удали все документы в этой папке")
        )
        self.assertFalse(
            payment_blocks_bulk_document_mutation(
                "удали все документы дела А40-12345/2025"
            )
        )
        self.assertFalse(payment_blocks_bulk_document_mutation("удали документ 254"))
        self.assertFalse(
            payment_blocks_bulk_document_mutation("удали все документы в папке Квитанция")
        )
        self.assertFalse(
            payment_blocks_bulk_document_mutation("удали все документы в папке Чек")
        )
        self.assertFalse(
            payment_blocks_bulk_document_mutation(
                "удали все документы за соглашение в этой папке"
            )
        )
        self.assertFalse(
            payment_blocks_bulk_document_mutation(
                "удали все документы за человека в этой папке"
            )
        )


if __name__ == "__main__":
    unittest.main()
