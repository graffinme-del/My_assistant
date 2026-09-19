"""Contract / power-of-attorney / pre-trial claim / certificate chat must not wipe a folder or delete the wrong document.

«удали все документы за договор в этой папке» used to match wants_all and hard-delete
every file in the open case because the contract phrase was ignored.
«удали документы 1-го договора» took the leading digit as a document id.
"""

from __future__ import annotations

import re
import unittest

from app.calendar_contract import (
    contract_blocks_bulk_document_mutation,
    looks_like_contract_scoped_document_request,
    mask_contract_ordinals,
)
from app.ru_date_range import parse_calendar_period_ru


def _parse_ids_like_main(text: str) -> list[int]:
    """Mirror apps/api/app/main.py:parse_document_ids_for_delete_command after the fix."""
    raw = text or ""
    ids = [int(x) for x in re.findall(r"\[(\d+)\]", raw)]
    ids.extend(int(x) for x in re.findall(r"(?i)\bdoc[.:]?\s*(\d+)\b", raw))
    if ids:
        return sorted(set(ids))
    safe = mask_contract_ordinals(raw)
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
    """Document-id parser on main before this fix — digits of «1-го договора» become an id."""
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


class ContractScopeTests(unittest.TestCase):
    def test_contract_phrases_are_detected(self) -> None:
        self.assertTrue(
            looks_like_contract_scoped_document_request(
                "удали все документы за договор в этой папке"
            )
        )
        self.assertTrue(
            looks_like_contract_scoped_document_request(
                "удали все документы за доверенность в этой папке"
            )
        )
        self.assertTrue(
            looks_like_contract_scoped_document_request(
                "удали все документы за претензию в этой папке"
            )
        )
        self.assertTrue(
            looks_like_contract_scoped_document_request(
                "удали все документы за справку в этой папке"
            )
        )
        self.assertTrue(
            looks_like_contract_scoped_document_request(
                "удали все документы за трудовой договор в этой папке"
            )
        )
        self.assertTrue(
            looks_like_contract_scoped_document_request(
                "удали все документы за нотариальную доверенность в этой папке"
            )
        )
        self.assertTrue(
            looks_like_contract_scoped_document_request(
                "удали все документы за досудебную претензию в этой папке"
            )
        )
        self.assertTrue(
            looks_like_contract_scoped_document_request("удали все документы на договоре")
        )
        self.assertTrue(
            looks_like_contract_scoped_document_request(
                "удали все документы по доверенности"
            )
        )
        self.assertTrue(
            looks_like_contract_scoped_document_request(
                "удали все документы во время претензии"
            )
        )
        self.assertTrue(
            looks_like_contract_scoped_document_request(
                "перенеси все документы за договор в папку Банкротство"
            )
        )
        self.assertTrue(
            looks_like_contract_scoped_document_request(
                "удали все документы за договор дела А40-12345/2025"
            )
        )
        self.assertTrue(
            looks_like_contract_scoped_document_request("удали документы первого договора")
        )
        self.assertTrue(
            looks_like_contract_scoped_document_request(
                "удали документы первой доверенности"
            )
        )

    def test_genitive_collocation_phrases_are_detected(self) -> None:
        self.assertTrue(
            looks_like_contract_scoped_document_request(
                "удали все документы договора в этой папке"
            )
        )
        self.assertTrue(
            looks_like_contract_scoped_document_request("удали документы доверенности")
        )
        self.assertTrue(
            looks_like_contract_scoped_document_request("удали документы претензии")
        )
        self.assertTrue(
            looks_like_contract_scoped_document_request("удали документы справки")
        )
        self.assertTrue(
            looks_like_contract_scoped_document_request(
                "удали договорные документы в этой папке"
            )
        )
        self.assertTrue(
            looks_like_contract_scoped_document_request(
                "удали претензионные документы в этой папке"
            )
        )
        self.assertTrue(
            looks_like_contract_scoped_document_request(
                "удали справочные документы в этой папке"
            )
        )

    def test_plain_wipe_or_id_commands_are_not_contract_scoped(self) -> None:
        self.assertFalse(
            looks_like_contract_scoped_document_request("удали все документы в этой папке")
        )
        self.assertFalse(looks_like_contract_scoped_document_request("удали документ 254"))
        self.assertFalse(
            looks_like_contract_scoped_document_request(
                "удали все документы дела А40-12345/2025"
            )
        )
        self.assertFalse(
            looks_like_contract_scoped_document_request(
                "перенеси все документы в папку Банкротство"
            )
        )
        self.assertFalse(
            looks_like_contract_scoped_document_request(
                "удали все документы за жалобу в этой папке"
            )
        )
        self.assertFalse(
            looks_like_contract_scoped_document_request(
                "удали все документы за иск в этой папке"
            )
        )
        self.assertFalse(
            looks_like_contract_scoped_document_request(
                "удали все документы за ходатайство в этой папке"
            )
        )
        self.assertFalse(
            looks_like_contract_scoped_document_request(
                "удали все документы в папке Договор"
            )
        )
        self.assertFalse(
            looks_like_contract_scoped_document_request(
                "удали все документы в папке Доверенность"
            )
        )
        self.assertFalse(
            looks_like_contract_scoped_document_request(
                "удали все документы в папке Претензия"
            )
        )
        self.assertFalse(
            looks_like_contract_scoped_document_request(
                "удали все документы в папке Справка"
            )
        )
        self.assertFalse(
            looks_like_contract_scoped_document_request(
                "удали все документы по договорённости сторон в этой папке"
            )
        )
        self.assertFalse(
            looks_like_contract_scoped_document_request(
                "удали все документы претендента в этой папке"
            )
        )


class ContractOrdinalIdTests(unittest.TestCase):
    def test_pre_fix_parser_took_ordinal_as_document_id(self) -> None:
        self.assertEqual(_pre_fix_parse_ids("удали документы 1-го договора"), [1])
        self.assertEqual(_pre_fix_parse_ids("удали документы 1-й доверенности"), [1])
        self.assertEqual(_pre_fix_parse_ids("удали файлы 1-й претензии"), [1])
        self.assertEqual(_pre_fix_parse_ids("удали файлы 1-й справки"), [1])
        self.assertEqual(_pre_fix_parse_ids("удали документы 1-х договоров"), [1])

    def test_ordinal_contract_is_not_a_document_id(self) -> None:
        self.assertEqual(_parse_ids_like_main("удали документы 1-го договора"), [])
        self.assertEqual(_parse_ids_like_main("удали документ 1-й договор"), [])
        self.assertEqual(_parse_ids_like_main("удали файлы 1-й доверенности"), [])
        self.assertEqual(_parse_ids_like_main("удали все документы 1-й претензии"), [])
        self.assertEqual(_parse_ids_like_main("удали документы 1 договора"), [])
        self.assertEqual(_parse_ids_like_main("удали документы 2-я справка"), [])
        self.assertEqual(_parse_ids_like_main("удали документы 1-й справки"), [])

    def test_real_ids_still_parse(self) -> None:
        self.assertEqual(_parse_ids_like_main("удали документ 254"), [254])
        self.assertEqual(_parse_ids_like_main("удали документы 1 и 2"), [1, 2])
        self.assertEqual(_parse_ids_like_main("удали документы [12] [18]"), [12, 18])
        self.assertEqual(
            _parse_ids_like_main("удали документ 254 за договор"),
            [254],
        )
        self.assertEqual(
            _parse_ids_like_main("удали документ [18] 1-го договора"),
            [18],
        )


class BulkMutationGuardTests(unittest.TestCase):
    def test_contract_scoped_all_deletes_are_blocked(self) -> None:
        self.assertTrue(
            contract_blocks_bulk_document_mutation(
                "удали все документы за договор в этой папке"
            )
        )
        self.assertTrue(
            contract_blocks_bulk_document_mutation(
                "удали все документы за доверенность в этой папке"
            )
        )
        self.assertTrue(
            contract_blocks_bulk_document_mutation(
                "удали все документы за претензию в этой папке"
            )
        )
        self.assertTrue(
            contract_blocks_bulk_document_mutation(
                "удали все документы за справку в этой папке"
            )
        )
        self.assertTrue(
            contract_blocks_bulk_document_mutation("удали все документы на договоре")
        )
        self.assertTrue(
            contract_blocks_bulk_document_mutation(
                "удали все документы во время доверенности"
            )
        )
        self.assertTrue(
            contract_blocks_bulk_document_mutation("удали документы 1-го договора")
        )

    def test_genitive_collocation_deletes_are_blocked(self) -> None:
        self.assertTrue(
            contract_blocks_bulk_document_mutation(
                "удали все документы договора в этой папке"
            )
        )
        self.assertTrue(
            contract_blocks_bulk_document_mutation("удали документы доверенности")
        )
        self.assertTrue(
            contract_blocks_bulk_document_mutation(
                "удали договорные документы в этой папке"
            )
        )

    def test_pre_fix_folder_wipe_trigger_is_exactly_the_blocked_shape(self) -> None:
        """Pre-fix: wants_all + open folder hard-deleted every file because «за договор» was ignored."""
        text = "удали все документы за договор в этой папке"
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
        self.assertTrue(contract_blocks_bulk_document_mutation(text))

    def test_power_of_attorney_wipe_trigger_is_the_same_shape(self) -> None:
        text = "удали все документы за доверенность в этой папке"
        low = text.lower()
        wants_all = "все документ" in low
        uses_open_folder = "этой папк" in low
        self.assertTrue(wants_all)
        self.assertTrue(uses_open_folder)
        self.assertIsNone(parse_calendar_period_ru(text))
        self.assertTrue(contract_blocks_bulk_document_mutation(text))

    def test_pretrial_claim_wipe_trigger_is_the_same_shape(self) -> None:
        text = "удали все документы за претензию в этой папке"
        low = text.lower()
        wants_all = "все документ" in low
        uses_open_folder = "этой папк" in low
        self.assertTrue(wants_all)
        self.assertTrue(uses_open_folder)
        self.assertIsNone(parse_calendar_period_ru(text))
        self.assertTrue(contract_blocks_bulk_document_mutation(text))

    def test_certificate_wipe_trigger_is_the_same_shape(self) -> None:
        text = "удали все документы за справку в этой папке"
        low = text.lower()
        wants_all = "все документ" in low
        uses_open_folder = "этой папк" in low
        self.assertTrue(wants_all)
        self.assertTrue(uses_open_folder)
        self.assertIsNone(parse_calendar_period_ru(text))
        self.assertTrue(contract_blocks_bulk_document_mutation(text))

    def test_current_contract_uses_active_folder_via_текущ(self) -> None:
        """«текущ» is an open-folder cue, so this wiped the active case without «в этой папке»."""
        text = "удали все документы за текущий договор"
        low = text.lower()
        self.assertIn("все документ", low)
        self.assertIn("текущ", low)
        self.assertIsNone(parse_calendar_period_ru(text))
        self.assertTrue(contract_blocks_bulk_document_mutation(text))

    def test_current_power_of_attorney_uses_active_folder_via_текущ(self) -> None:
        text = "удали все документы за текущую доверенность"
        low = text.lower()
        self.assertIn("все документ", low)
        self.assertIn("текущ", low)
        self.assertTrue(contract_blocks_bulk_document_mutation(text))

    def test_ordinal_contract_wrong_id_trigger(self) -> None:
        """Pre-fix: «1-го договора» parsed as document id 1 and hard-deleted that file."""
        text = "удали документы 1-го договора"
        self.assertEqual(_pre_fix_parse_ids(text), [1])
        self.assertEqual(_parse_ids_like_main(text), [])
        self.assertTrue(contract_blocks_bulk_document_mutation(text))

    def test_existing_period_parser_does_not_see_contract(self) -> None:
        """#69–#86 cover dates through complaint/petition — not договор/доверенность/претензия/справка."""
        self.assertIsNone(
            parse_calendar_period_ru("удали все документы за договор в этой папке")
        )
        self.assertIsNone(
            parse_calendar_period_ru("удали все документы за доверенность в этой папке")
        )
        self.assertIsNone(
            parse_calendar_period_ru("удали все документы за претензию в этой папке")
        )
        self.assertIsNone(parse_calendar_period_ru("удали все документы за справку"))
        self.assertIsNone(parse_calendar_period_ru("удали все документы на договоре"))
        self.assertIsNone(parse_calendar_period_ru("удали все документы договора"))

    def test_explicit_id_still_allowed_even_if_contract_is_mentioned(self) -> None:
        self.assertFalse(
            contract_blocks_bulk_document_mutation(
                "удали документ 254 за договор",
                explicit_document_ids=[254],
            )
        )

    def test_unscoped_folder_wipe_is_not_blocked(self) -> None:
        self.assertFalse(
            contract_blocks_bulk_document_mutation("удали все документы в этой папке")
        )
        self.assertFalse(
            contract_blocks_bulk_document_mutation(
                "удали все документы дела А40-12345/2025"
            )
        )
        self.assertFalse(contract_blocks_bulk_document_mutation("удали документ 254"))
        self.assertFalse(
            contract_blocks_bulk_document_mutation("удали все документы в папке Договор")
        )
        self.assertFalse(
            contract_blocks_bulk_document_mutation(
                "удали все документы в папке Доверенность"
            )
        )
        self.assertFalse(
            contract_blocks_bulk_document_mutation(
                "удали все документы за жалобу в этой папке"
            )
        )


if __name__ == "__main__":
    unittest.main()
