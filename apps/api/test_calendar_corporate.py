"""Reconciliation / balance / charter / order chat must not wipe a folder or delete the wrong document.

«удали все документы за акт сверки в этой папке» used to match wants_all and hard-delete
every file in the open case because the document-type phrase was ignored.
«удали документы 1-го приказа» took the leading digit as a document id.
"""

from __future__ import annotations

import re
import unittest

from app.calendar_corporate import (
    corporate_blocks_bulk_document_mutation,
    looks_like_corporate_scoped_document_request,
    mask_corporate_ordinals,
)
from app.ru_date_range import parse_calendar_period_ru


def _parse_ids_like_main(text: str) -> list[int]:
    """Mirror apps/api/app/main.py:parse_document_ids_for_delete_command after the fix."""
    raw = text or ""
    ids = [int(x) for x in re.findall(r"\[(\d+)\]", raw)]
    ids.extend(int(x) for x in re.findall(r"(?i)\bdoc[.:]?\s*(\d+)\b", raw))
    if ids:
        return sorted(set(ids))
    safe = mask_corporate_ordinals(raw)
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
    """Document-id parser on main before this fix — digits of «1-го приказа» become an id."""
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


class CorporateScopeTests(unittest.TestCase):
    def test_corporate_phrases_are_detected(self) -> None:
        for phrase in (
            "удали все документы за акт сверки в этой папке",
            "удали все документы за баланс в этой папке",
            "удали все документы за устав в этой папке",
            "удали все документы за приказ в этой папке",
            "удали все документы за сверку в этой папке",
            "удали все документы на балансе",
            "удали все документы по уставу",
            "удали все документы в приказе",
            "удали все документы по приказу",
            "удали все документы во время акта сверки",
            "удали все документы за бухгалтерский баланс в этой папке",
            "удали все документы за учредительный устав",
            "удали все документы за годовой акт сверки",
            "удали все документы за последний годовой баланс",
        ):
            self.assertTrue(
                looks_like_corporate_scoped_document_request(phrase),
                phrase,
            )

    def test_demonstrative_and_current_corporate_are_detected(self) -> None:
        self.assertTrue(
            looks_like_corporate_scoped_document_request(
                "удали все документы за текущий приказ"
            )
        )
        self.assertTrue(
            looks_like_corporate_scoped_document_request("удали документы этого баланса")
        )
        self.assertTrue(
            looks_like_corporate_scoped_document_request("удали файлы текущего устава")
        )
        self.assertTrue(
            looks_like_corporate_scoped_document_request(
                "удали все документы по этому акту сверки"
            )
        )

    def test_ordinal_corporate_is_detected(self) -> None:
        self.assertTrue(
            looks_like_corporate_scoped_document_request("удали документы 1-го приказа")
        )
        self.assertTrue(
            looks_like_corporate_scoped_document_request("удали документы 1-го баланса")
        )
        self.assertTrue(
            looks_like_corporate_scoped_document_request("удали документы 1-го устава")
        )
        self.assertTrue(
            looks_like_corporate_scoped_document_request("удали документы 1-го акта сверки")
        )
        self.assertTrue(
            looks_like_corporate_scoped_document_request("удали документы первого приказа")
        )

    def test_genitive_collocation_is_detected(self) -> None:
        self.assertTrue(
            looks_like_corporate_scoped_document_request(
                "удали все документы приказа в этой папке"
            )
        )
        self.assertTrue(looks_like_corporate_scoped_document_request("удали документы баланса"))
        self.assertTrue(looks_like_corporate_scoped_document_request("удали документы устава"))
        self.assertTrue(
            looks_like_corporate_scoped_document_request("удали документы акта сверки")
        )
        self.assertTrue(
            looks_like_corporate_scoped_document_request(
                "удали балансовые документы в этой папке"
            )
        )
        self.assertTrue(
            looks_like_corporate_scoped_document_request("удали уставные документы")
        )
        self.assertTrue(
            looks_like_corporate_scoped_document_request("удали приказные документы")
        )

    def test_unscoped_and_lookalike_phrases_are_not_detected(self) -> None:
        for phrase in (
            "удали все документы в этой папке",
            "удали документ 254",
            "удали все документы дела А40-12345/2025",
            "удали все документы в папке Приказ",
            "удали все документы в папке Баланс",
            "удали все документы в папке Устав",
            "удали все документы в папке Сверка",
            "удали все документы за человека в этой папке",
            "удали все документы за выписку в этой папке",
            "удали все документы за квитанцию в этой папке",
            "удали приложенные документы в этой папке",
            "удали все документы за уставший сервер",
            "удали все документы по приказанию",
            "удали все документы за актуальный отчёт",
            "удали все документы за балансир",
        ):
            self.assertFalse(
                looks_like_corporate_scoped_document_request(phrase),
                phrase,
            )


class CorporateOrdinalIdTests(unittest.TestCase):
    def test_pre_fix_parser_took_ordinal_as_document_id(self) -> None:
        self.assertEqual(_pre_fix_parse_ids("удали документы 1-го приказа"), [1])
        self.assertEqual(_pre_fix_parse_ids("удали документы 1-го баланса"), [1])
        self.assertEqual(_pre_fix_parse_ids("удали документы 1-го устава"), [1])
        self.assertEqual(_pre_fix_parse_ids("удали документы 1-го акта сверки"), [1])
        self.assertEqual(_pre_fix_parse_ids("удали документы 1-й сверки"), [1])

    def test_ordinal_corporate_is_not_a_document_id(self) -> None:
        self.assertEqual(_parse_ids_like_main("удали документы 1-го приказа"), [])
        self.assertEqual(_parse_ids_like_main("удали документы 1-го баланса"), [])
        self.assertEqual(_parse_ids_like_main("удали документы 1-го устава"), [])
        self.assertEqual(_parse_ids_like_main("удали документы 1-го акта сверки"), [])
        self.assertEqual(_parse_ids_like_main("удали все документы 1-й приказ"), [])
        self.assertEqual(_parse_ids_like_main("удали документы 1 приказа"), [])
        self.assertEqual(_parse_ids_like_main("удали документы 2-й баланс"), [])

    def test_real_ids_still_parse(self) -> None:
        self.assertEqual(_parse_ids_like_main("удали документ 254"), [254])
        self.assertEqual(_parse_ids_like_main("удали документы 1 и 2"), [1, 2])
        self.assertEqual(_parse_ids_like_main("удали документы [12] [18]"), [12, 18])
        self.assertEqual(
            _parse_ids_like_main("удали документ 254 за приказ"),
            [254],
        )
        self.assertEqual(
            _parse_ids_like_main("удали документ [18] 1-го баланса"),
            [18],
        )
        self.assertEqual(
            _parse_ids_like_main("удали документ 12 за устав"),
            [12],
        )

    def test_human_ordinal_is_not_masked_as_order(self) -> None:
        self.assertFalse(
            looks_like_corporate_scoped_document_request("удали документы 1-го человека")
        )
        self.assertEqual(_parse_ids_like_main("удали документы 1-го человека"), [1])


class BulkMutationGuardTests(unittest.TestCase):
    def test_corporate_scoped_all_deletes_are_blocked(self) -> None:
        for phrase in (
            "удали все документы за акт сверки в этой папке",
            "удали все документы за баланс в этой папке",
            "удали все документы за устав в этой папке",
            "удали все документы за приказ в этой папке",
            "удали все документы на балансе",
            "удали все документы во время акта сверки",
            "удали документы 1-го приказа",
        ):
            self.assertTrue(corporate_blocks_bulk_document_mutation(phrase), phrase)

    def test_genitive_collocation_deletes_are_blocked(self) -> None:
        self.assertTrue(
            corporate_blocks_bulk_document_mutation(
                "удали все документы приказа в этой папке"
            )
        )
        self.assertTrue(corporate_blocks_bulk_document_mutation("удали документы баланса"))
        self.assertTrue(
            corporate_blocks_bulk_document_mutation(
                "удали уставные документы в этой папке"
            )
        )

    def test_pre_fix_folder_wipe_trigger_is_exactly_the_blocked_shape(self) -> None:
        """Pre-fix: wants_all + open folder hard-deleted every file because «за приказ» was ignored."""
        for text in (
            "удали все документы за акт сверки в этой папке",
            "удали все документы за баланс в этой папке",
            "удали все документы за устав в этой папке",
            "удали все документы за приказ в этой папке",
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
            self.assertTrue(corporate_blocks_bulk_document_mutation(text), text)

    def test_current_order_uses_active_folder_via_текущ(self) -> None:
        """«текущ» is an open-folder cue, so this wiped the active case without «в этой папке»."""
        text = "удали все документы за текущий приказ"
        low = text.lower()
        self.assertIn("все документ", low)
        self.assertIn("текущ", low)
        self.assertIsNone(parse_calendar_period_ru(text))
        self.assertTrue(corporate_blocks_bulk_document_mutation(text))

    def test_ordinal_order_wrong_id_trigger(self) -> None:
        """Pre-fix: «1-го приказа» parsed as document id 1 and hard-deleted that file."""
        text = "удали документы 1-го приказа"
        self.assertEqual(_pre_fix_parse_ids(text), [1])
        self.assertEqual(_parse_ids_like_main(text), [])
        self.assertTrue(corporate_blocks_bulk_document_mutation(text))

    def test_existing_period_parser_does_not_see_corporate_scope(self) -> None:
        for phrase in (
            "удали все документы за акт сверки в этой папке",
            "удали все документы за баланс в этой папке",
            "удали все документы за устав в этой папке",
            "удали все документы за приказ",
            "удали все документы на балансе",
            "удали все документы приказа",
        ):
            self.assertIsNone(parse_calendar_period_ru(phrase), phrase)

    def test_named_case_move_dumps_source_folder_pre_fix(self) -> None:
        """«перенеси все документы дела А40-… за приказ в папку …» executes move-all."""
        text = "перенеси все документы дела А40-12345/2025 за приказ в папку Архив"
        low = text.lower()
        self.assertTrue(any(k in low for k in ["перенеси", "все документы", "в папку"]))
        self.assertIn("папк", low)
        self.assertTrue(corporate_blocks_bulk_document_mutation(text))

    def test_explicit_id_still_allowed_even_if_corporate_is_mentioned(self) -> None:
        self.assertFalse(
            corporate_blocks_bulk_document_mutation(
                "удали документ 254 за приказ",
                explicit_document_ids=[254],
            )
        )

    def test_unscoped_folder_wipe_is_not_blocked(self) -> None:
        for phrase in (
            "удали все документы в этой папке",
            "удали все документы дела А40-12345/2025",
            "удали документ 254",
            "удали все документы в папке Приказ",
            "удали все документы в папке Баланс",
            "удали все документы за выписку в этой папке",
            "удали все документы за человека в этой папке",
            "удали приложенные документы в этой папке",
        ):
            self.assertFalse(corporate_blocks_bulk_document_mutation(phrase), phrase)


if __name__ == "__main__":
    unittest.main()
