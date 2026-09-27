"""«Контракт» chat must not wipe a folder or delete the wrong document.

«удали все документы за контракт в этой папке» matched wants_all and hard-deleted
every file in the open case because the document-type phrase was ignored.
«удали документы 1-го контракта» took the leading digit as document id 1.

«Договор» is a different noun. The work-act guard treats «контракт» as a lookalike
of «акт» and does not match it.
"""

from __future__ import annotations

import re
import unittest
from pathlib import Path

from app.calendar_state_contract import (
    looks_like_state_contract_scoped_document_request,
    mask_state_contract_ordinals,
    state_contract_blocks_bulk_document_mutation,
)
from app.ru_date_range import parse_calendar_period_ru


def _parse_ids_like_main(text: str) -> list[int]:
    """Mirror apps/api/app/main.py:parse_document_ids_for_delete_command after the fix."""
    raw = text or ""
    ids = [int(x) for x in re.findall(r"\[(\d+)\]", raw)]
    ids.extend(int(x) for x in re.findall(r"(?i)\bdoc[.:]?\s*(\d+)\b", raw))
    if ids:
        return sorted(set(ids))
    safe = mask_state_contract_ordinals(raw)
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
    """Document-id parser on main before this fix."""
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


class StateContractScopeTests(unittest.TestCase):
    def test_contract_phrases_are_detected(self) -> None:
        for phrase in (
            "удали все документы за контракт в этой папке",
            "удали все документы за контракт",
            "удали все документы по контракту",
            "удали все документы на контракте",
            "удали все документы в контракте",
            "удали все документы за госконтракт в этой папке",
            "удали все документы по госконтракту",
            "удали все документы за гос-контракт",
            "удали все документы за гос контракт",
            "удали все документы за гос. контракт",
            "удали все документы за государственный контракт в этой папке",
            "удали все документы за муниципальный контракт",
            "удали все документы за гражданско-правовой контракт",
            "удали все документы во время контракта",
            "удали все документы за КОНТРАКТ в этой папке",
            "удали все файлы за контракт в этой папке",
        ):
            self.assertTrue(
                looks_like_state_contract_scoped_document_request(phrase),
                phrase,
            )

    def test_demonstrative_and_current_contract_are_detected(self) -> None:
        self.assertTrue(
            looks_like_state_contract_scoped_document_request(
                "удали все документы за текущий контракт"
            )
        )
        self.assertTrue(
            looks_like_state_contract_scoped_document_request(
                "удали все документы за открытый контракт"
            )
        )
        self.assertTrue(
            looks_like_state_contract_scoped_document_request(
                "удали документы этого контракта"
            )
        )
        self.assertTrue(
            looks_like_state_contract_scoped_document_request(
                "удали файлы этого госконтракта"
            )
        )

    def test_ordinal_contract_is_detected(self) -> None:
        for phrase in (
            "удали документы 1-го контракта",
            "удали документы 1-го госконтракта",
            "удали документы 1-й контракт",
            "удали документы 1 контракта",
            "удали документы первого контракта",
            "удали документы 2-го государственного контракта",
        ):
            self.assertTrue(
                looks_like_state_contract_scoped_document_request(phrase),
                phrase,
            )

    def test_genitive_and_adjective_collocations_are_detected(self) -> None:
        for phrase in (
            "удали все документы контракта в этой папке",
            "удали документы госконтракта",
            "удали документы государственного контракта",
            "удали контрактные документы в этой папке",
            "удали все документы контрактные в этой папке",
        ):
            self.assertTrue(
                looks_like_state_contract_scoped_document_request(phrase),
                phrase,
            )

    def test_unscoped_and_lookalike_phrases_are_not_detected(self) -> None:
        for phrase in (
            "удали все документы в этой папке",
            "удали документ 254",
            "удали документы 214",
            "удали документы 1 и 2",
            "удали все документы дела А40-12345/2025",
            "удали все документы в папке Контракт",
            "удали все документы по делу Контракт",
            "удали все документы за договор в этой папке",
            "удали все документы за акт в этой папке",
            "удали все документы за акт сверки в этой папке",
            "удали все актуальные документы в этой папке",
            "удали все документы за контрактацию",
            "удали все документы за контрактника",
            "удали документы 1-го человека",
            "удали документы 1-го договора",
            "удали все документы за поручение в этой папке",
        ):
            self.assertFalse(
                looks_like_state_contract_scoped_document_request(phrase),
                phrase,
            )


class StateContractOrdinalIdTests(unittest.TestCase):
    def test_pre_fix_parser_took_ordinal_as_document_id(self) -> None:
        self.assertEqual(_pre_fix_parse_ids("удали документы 1-го контракта"), [1])
        self.assertEqual(_pre_fix_parse_ids("удали документы 1-го госконтракта"), [1])
        self.assertEqual(_pre_fix_parse_ids("удали документы 1-й контракт"), [1])
        self.assertEqual(_pre_fix_parse_ids("удали документы 1 контракта"), [1])

    def test_ordinal_contract_is_not_a_document_id(self) -> None:
        self.assertEqual(_parse_ids_like_main("удали документы 1-го контракта"), [])
        self.assertEqual(_parse_ids_like_main("удали документы 1-го госконтракта"), [])
        self.assertEqual(_parse_ids_like_main("удали документы 1-й контракт"), [])
        self.assertEqual(_parse_ids_like_main("удали документы 1 контракта"), [])
        self.assertEqual(_parse_ids_like_main("удали документы 2-го контракта"), [])
        self.assertEqual(
            _parse_ids_like_main("удали документы 1-го государственного контракта"),
            [],
        )

    def test_real_ids_still_parse(self) -> None:
        self.assertEqual(_parse_ids_like_main("удали документ 254"), [254])
        self.assertEqual(_parse_ids_like_main("удали документы 1 и 2"), [1, 2])
        self.assertEqual(_parse_ids_like_main("удали документы [12] [18]"), [12, 18])
        self.assertEqual(_parse_ids_like_main("удали документ 254 за контракт"), [254])
        self.assertEqual(_parse_ids_like_main("удали документ [18] 1-го контракта"), [18])
        self.assertEqual(_parse_ids_like_main("удали документы 214 контракта"), [214])
        # «Договор» ordinals stay on the pre-fix parser; this guard must not mask them.
        self.assertEqual(_parse_ids_like_main("удали документы 1-го договора"), [1])

    def test_human_ordinal_is_not_masked(self) -> None:
        self.assertFalse(
            looks_like_state_contract_scoped_document_request("удали документы 1-го человека")
        )
        self.assertEqual(_parse_ids_like_main("удали документы 1-го человека"), [1])


class BulkMutationGuardTests(unittest.TestCase):
    def test_pre_fix_folder_wipe_trigger_is_exactly_the_blocked_shape(self) -> None:
        """Pre-fix: wants_all + open folder hard-deleted every file."""
        for text in (
            "удали все документы за контракт в этой папке",
            "удали все документы за госконтракт в этой папке",
            "удали все документы за государственный контракт в этой папке",
            "удали все документы за муниципальный контракт в этой папке",
            "удали все документы контракта в этой папке",
            "удали все документы контрактные в этой папке",
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
            self.assertTrue(state_contract_blocks_bulk_document_mutation(text), text)

    def test_current_contract_uses_active_folder_via_текущ(self) -> None:
        """«текущ» is an open-folder cue, so this wiped the active case without «в этой папке»."""
        text = "удали все документы за текущий контракт"
        low = text.lower()
        self.assertIn("все документ", low)
        self.assertIn("текущ", low)
        self.assertIsNone(parse_calendar_period_ru(text))
        self.assertTrue(state_contract_blocks_bulk_document_mutation(text))

    def test_open_contract_uses_active_folder_via_открыт(self) -> None:
        """«открыт» is an open-folder cue inside «открытый контракт»."""
        text = "удали все документы за открытый контракт"
        low = text.lower()
        self.assertIn("все документ", low)
        self.assertIn("открыт", low)
        self.assertIsNone(parse_calendar_period_ru(text))
        self.assertTrue(state_contract_blocks_bulk_document_mutation(text))

    def test_ordinal_contract_wrong_id_trigger(self) -> None:
        """Pre-fix: «1-го контракта» parsed as document id 1 and hard-deleted that file."""
        text = "удали документы 1-го контракта"
        self.assertEqual(_pre_fix_parse_ids(text), [1])
        self.assertEqual(_parse_ids_like_main(text), [])
        self.assertTrue(state_contract_blocks_bulk_document_mutation(text))

    def test_existing_period_parser_does_not_see_contract_scope(self) -> None:
        for phrase in (
            "удали все документы за контракт в этой папке",
            "удали все документы за госконтракт",
            "удали все документы по контракту",
            "удали документы 1-го контракта",
        ):
            self.assertIsNone(parse_calendar_period_ru(phrase), phrase)

    def test_named_case_move_dumps_source_folder_pre_fix(self) -> None:
        """«перенеси все документы дела А40-… за контракт в папку …» executes move-all."""
        text = "перенеси все документы дела А40-12345/2025 за контракт в папку Архив"
        low = text.lower()
        self.assertTrue(any(k in low for k in ["перенеси", "все документы", "в папку"]))
        self.assertIn("папк", low)
        self.assertTrue(state_contract_blocks_bulk_document_mutation(text))
        state = "перенеси все документы дела А40-12345/2025 за госконтракт в папку Архив"
        self.assertTrue(state_contract_blocks_bulk_document_mutation(state))

    def test_explicit_id_still_allowed_even_if_contract_is_mentioned(self) -> None:
        self.assertFalse(
            state_contract_blocks_bulk_document_mutation(
                "удали документ 254 за контракт",
                explicit_document_ids=[254],
            )
        )

    def test_unscoped_folder_wipe_is_not_blocked(self) -> None:
        for phrase in (
            "удали все документы в этой папке",
            "удали все документы дела А40-12345/2025",
            "удали документ 254",
            "удали все документы в папке Контракт",
            "удали все документы за договор в этой папке",
            "удали все документы за акт в этой папке",
            "удали все документы за человека в этой папке",
        ):
            self.assertFalse(state_contract_blocks_bulk_document_mutation(phrase), phrase)

    def test_main_wires_the_guard(self) -> None:
        source = (Path(__file__).resolve().parent / "app" / "main.py").read_text(encoding="utf-8")
        self.assertIn("state_contract_blocks_bulk_document_mutation", source)
        self.assertIn("mask_state_contract_ordinals", source)
        self.assertIn("DELETE_REFUSED_STATE_CONTRACT", source)
        self.assertIn("MOVE_REFUSED_STATE_CONTRACT", source)


if __name__ == "__main__":
    unittest.main()
