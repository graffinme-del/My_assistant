"""Statement / register / appendix / schedule chat must not wipe a folder or delete the wrong document.

«удали все документы за выписку в этой папке» used to match wants_all and hard-delete
every file in the open case because the statement phrase was ignored.
«удали документы 1-го приложения» took the leading digit as a document id.
"""

from __future__ import annotations

import re
import unittest

from app.calendar_record import (
    looks_like_record_scoped_document_request,
    mask_record_ordinals,
    record_blocks_bulk_document_mutation,
)
from app.ru_date_range import parse_calendar_period_ru


def _parse_ids_like_main(text: str) -> list[int]:
    """Mirror apps/api/app/main.py:parse_document_ids_for_delete_command after the fix."""
    raw = text or ""
    ids = [int(x) for x in re.findall(r"\[(\d+)\]", raw)]
    ids.extend(int(x) for x in re.findall(r"(?i)\bdoc[.:]?\s*(\d+)\b", raw))
    if ids:
        return sorted(set(ids))
    safe = mask_record_ordinals(raw)
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
    """Document-id parser on main before this fix — digits of «1-го приложения» become an id."""
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


class RecordScopeTests(unittest.TestCase):
    def test_record_phrases_are_detected(self) -> None:
        for phrase in (
            "удали все документы за выписку в этой папке",
            "удали все документы за реестр в этой папке",
            "удали все документы за приложение в этой папке",
            "удали все документы за график в этой папке",
            "удали все документы на выписке",
            "удали все документы по реестру",
            "удали все документы в приложении",
            "удали все документы во время графика",
            "удали все документы за банковскую выписку в этой папке",
            "удали все документы за платёжный график",
            "удали все документы за платежный график",
            "удали все документы за календарный график",
            "удали все документы за дополнительное приложение",
            "удали все документы за рабочий график",
        ):
            self.assertTrue(
                looks_like_record_scoped_document_request(phrase),
                phrase,
            )

    def test_demonstrative_and_current_record_are_detected(self) -> None:
        self.assertTrue(
            looks_like_record_scoped_document_request(
                "удали все документы за текущую выписку"
            )
        )
        self.assertTrue(
            looks_like_record_scoped_document_request("удали документы этого реестра")
        )
        self.assertTrue(
            looks_like_record_scoped_document_request("удали файлы текущего графика")
        )
        self.assertTrue(
            looks_like_record_scoped_document_request("удали все документы по этому графику")
        )

    def test_ordinal_record_is_detected(self) -> None:
        self.assertTrue(
            looks_like_record_scoped_document_request("удали документы 1-й выписки")
        )
        self.assertTrue(
            looks_like_record_scoped_document_request("удали документы 1-го реестра")
        )
        self.assertTrue(
            looks_like_record_scoped_document_request("удали документы 1-го приложения")
        )
        self.assertTrue(
            looks_like_record_scoped_document_request("удали файлы 1-го графика")
        )
        self.assertTrue(
            looks_like_record_scoped_document_request("удали документы первого приложения")
        )

    def test_genitive_collocation_is_detected(self) -> None:
        self.assertTrue(
            looks_like_record_scoped_document_request(
                "удали все документы выписки в этой папке"
            )
        )
        self.assertTrue(looks_like_record_scoped_document_request("удали документы реестра"))
        self.assertTrue(
            looks_like_record_scoped_document_request("удали документы приложения")
        )
        self.assertTrue(looks_like_record_scoped_document_request("удали документы графика"))
        self.assertTrue(
            looks_like_record_scoped_document_request(
                "удали выписочные документы в этой папке"
            )
        )
        self.assertTrue(
            looks_like_record_scoped_document_request("удали реестровые документы")
        )

    def test_unscoped_and_lookalike_phrases_are_not_detected(self) -> None:
        for phrase in (
            "удали все документы в этой папке",
            "удали документ 254",
            "удали все документы дела А40-12345/2025",
            "удали все документы в папке Выписка",
            "удали все документы в папке Реестр",
            "удали все документы в папке Приложение",
            "удали все документы в папке График",
            "удали все документы за человека в этой папке",
            "удали все документы за квитанцию в этой папке",
            "удали все документы за соглашение в этой папке",
            "удали приложенные документы в этой папке",
            "удали все документы за графический дизайн",
            "удали все документы по выписыванию",
        ):
            self.assertFalse(
                looks_like_record_scoped_document_request(phrase),
                phrase,
            )


class RecordOrdinalIdTests(unittest.TestCase):
    def test_pre_fix_parser_took_ordinal_as_document_id(self) -> None:
        self.assertEqual(_pre_fix_parse_ids("удали документы 1-й выписки"), [1])
        self.assertEqual(_pre_fix_parse_ids("удали документы 1-го реестра"), [1])
        self.assertEqual(_pre_fix_parse_ids("удали документы 1-го приложения"), [1])
        self.assertEqual(_pre_fix_parse_ids("удали файлы 1-го графика"), [1])
        self.assertEqual(_pre_fix_parse_ids("удали документы 1-х выписок"), [1])

    def test_ordinal_record_is_not_a_document_id(self) -> None:
        self.assertEqual(_parse_ids_like_main("удали документы 1-й выписки"), [])
        self.assertEqual(_parse_ids_like_main("удали документы 1-го реестра"), [])
        self.assertEqual(_parse_ids_like_main("удали документы 1-го приложения"), [])
        self.assertEqual(_parse_ids_like_main("удали файлы 1-го графика"), [])
        self.assertEqual(_parse_ids_like_main("удали все документы 1-е приложение"), [])
        self.assertEqual(_parse_ids_like_main("удали документы 1 выписки"), [])
        self.assertEqual(_parse_ids_like_main("удали документы 2-е приложение"), [])

    def test_real_ids_still_parse(self) -> None:
        self.assertEqual(_parse_ids_like_main("удали документ 254"), [254])
        self.assertEqual(_parse_ids_like_main("удали документы 1 и 2"), [1, 2])
        self.assertEqual(_parse_ids_like_main("удали документы [12] [18]"), [12, 18])
        self.assertEqual(
            _parse_ids_like_main("удали документ 254 за выписку"),
            [254],
        )
        self.assertEqual(
            _parse_ids_like_main("удали документ [18] 1-го приложения"),
            [18],
        )
        self.assertEqual(
            _parse_ids_like_main("удали документ 12 за реестр"),
            [12],
        )

    def test_человек_ordinal_is_not_masked_as_appendix(self) -> None:
        self.assertFalse(
            looks_like_record_scoped_document_request("удали документы 1-го человека")
        )
        self.assertEqual(_parse_ids_like_main("удали документы 1-го человека"), [1])


class BulkMutationGuardTests(unittest.TestCase):
    def test_record_scoped_all_deletes_are_blocked(self) -> None:
        for phrase in (
            "удали все документы за выписку в этой папке",
            "удали все документы за реестр в этой папке",
            "удали все документы за приложение в этой папке",
            "удали все документы за график в этой папке",
            "удали все документы на выписке",
            "удали все документы во время графика",
            "удали документы 1-го приложения",
        ):
            self.assertTrue(record_blocks_bulk_document_mutation(phrase), phrase)

    def test_genitive_collocation_deletes_are_blocked(self) -> None:
        self.assertTrue(
            record_blocks_bulk_document_mutation(
                "удали все документы выписки в этой папке"
            )
        )
        self.assertTrue(record_blocks_bulk_document_mutation("удали документы приложения"))
        self.assertTrue(
            record_blocks_bulk_document_mutation(
                "удали реестровые документы в этой папке"
            )
        )

    def test_pre_fix_folder_wipe_trigger_is_exactly_the_blocked_shape(self) -> None:
        """Pre-fix: wants_all + open folder hard-deleted every file because «за выписку» was ignored."""
        for text in (
            "удали все документы за выписку в этой папке",
            "удали все документы за реестр в этой папке",
            "удали все документы за приложение в этой папке",
            "удали все документы за график в этой папке",
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
            self.assertEqual(_parse_ids_like_main(text), [])
            self.assertTrue(record_blocks_bulk_document_mutation(text), text)

    def test_current_statement_uses_active_folder_via_текущ(self) -> None:
        """«текущ» is an open-folder cue, so this wiped the active case without «в этой папке»."""
        text = "удали все документы за текущую выписку"
        low = text.lower()
        self.assertIn("все документ", low)
        self.assertIn("текущ", low)
        self.assertIsNone(parse_calendar_period_ru(text))
        self.assertTrue(record_blocks_bulk_document_mutation(text))

    def test_ordinal_appendix_wrong_id_trigger(self) -> None:
        """Pre-fix: «1-го приложения» parsed as document id 1 and hard-deleted that file."""
        text = "удали документы 1-го приложения"
        self.assertEqual(_pre_fix_parse_ids(text), [1])
        self.assertEqual(_parse_ids_like_main(text), [])
        self.assertTrue(record_blocks_bulk_document_mutation(text))

    def test_existing_period_parser_does_not_see_record_scope(self) -> None:
        """Calendar-period parsing does not see выписка / реестр / приложение / график."""
        for phrase in (
            "удали все документы за выписку в этой папке",
            "удали все документы за реестр в этой папке",
            "удали все документы за приложение в этой папке",
            "удали все документы за график",
            "удали все документы на выписке",
            "удали все документы приложения",
        ):
            self.assertIsNone(parse_calendar_period_ru(phrase), phrase)

    def test_named_case_move_dumps_source_folder_pre_fix(self) -> None:
        """«перенеси все документы дела А40-… за приложение в папку …» executes move-all."""
        text = "перенеси все документы дела А40-12345/2025 за приложение в папку Архив"
        low = text.lower()
        self.assertTrue(any(k in low for k in ["перенеси", "все документы", "в папку"]))
        self.assertIn("папк", low)
        self.assertTrue(record_blocks_bulk_document_mutation(text))

    def test_explicit_id_still_allowed_even_if_record_is_mentioned(self) -> None:
        self.assertFalse(
            record_blocks_bulk_document_mutation(
                "удали документ 254 за выписку",
                explicit_document_ids=[254],
            )
        )

    def test_unscoped_folder_wipe_is_not_blocked(self) -> None:
        for phrase in (
            "удали все документы в этой папке",
            "удали все документы дела А40-12345/2025",
            "удали документ 254",
            "удали все документы в папке Выписка",
            "удали все документы в папке Приложение",
            "удали все документы за квитанцию в этой папке",
            "удали все документы за человека в этой папке",
            "удали приложенные документы в этой папке",
        ):
            self.assertFalse(record_blocks_bulk_document_mutation(phrase), phrase)


if __name__ == "__main__":
    unittest.main()
