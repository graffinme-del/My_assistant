"""Routing: named-document relocate must not execute a whole-folder dump."""

from __future__ import annotations

import unittest

from app.document_move_intent import (
    looks_like_bulk_folder_move_request,
    looks_like_manual_move_request,
    looks_like_named_document_move,
    parse_explicit_move_document_ids,
    parse_manual_move_destination_hint,
)


class DocumentMoveIntentTests(unittest.TestCase):
    CRITICAL = "перенеси документ 254 из дела A40-12345/2025 в папку Банкротство"
    DOCUMENTED = "перенеси документ 4 в дело Банкротство АГМ"
    BRACKET = "перенеси документы [213] [214] из дела A40-12345/2025 в папку Банкротство"
    BULK = "перенеси все документы из дела A40-12345/2025 в папку Банкротство"
    COLLECT = "собери все документы в папку Банкротство"

    def test_critical_named_source_case_is_not_bulk(self) -> None:
        self.assertEqual(parse_explicit_move_document_ids(self.CRITICAL), [254])
        self.assertTrue(looks_like_named_document_move(self.CRITICAL))
        self.assertFalse(looks_like_bulk_folder_move_request(self.CRITICAL))
        self.assertTrue(looks_like_manual_move_request(self.CRITICAL))
        self.assertEqual(parse_manual_move_destination_hint(self.CRITICAL), "Банкротство")

    def test_documented_single_id_to_case_is_manual(self) -> None:
        self.assertEqual(parse_explicit_move_document_ids(self.DOCUMENTED), [4])
        self.assertFalse(looks_like_bulk_folder_move_request(self.DOCUMENTED))
        self.assertTrue(looks_like_manual_move_request(self.DOCUMENTED))
        self.assertEqual(parse_manual_move_destination_hint(self.DOCUMENTED), "Банкротство АГМ")

    def test_bracket_ids_with_source_case_are_manual(self) -> None:
        self.assertEqual(parse_explicit_move_document_ids(self.BRACKET), [213, 214])
        self.assertFalse(looks_like_bulk_folder_move_request(self.BRACKET))
        self.assertTrue(looks_like_manual_move_request(self.BRACKET))

    def test_real_bulk_all_from_named_case_still_matches(self) -> None:
        self.assertEqual(parse_explicit_move_document_ids(self.BULK), [])
        self.assertFalse(looks_like_named_document_move(self.BULK))
        self.assertTrue(looks_like_bulk_folder_move_request(self.BULK))

    def test_collect_all_into_folder_still_matches(self) -> None:
        self.assertFalse(looks_like_named_document_move(self.COLLECT))
        self.assertTrue(looks_like_bulk_folder_move_request(self.COLLECT))

    def test_legacy_substring_would_have_treated_named_id_as_bulk(self) -> None:
        """Pre-fix looks_like_move_all matched any «перенеси» + папка + документ."""
        t = self.CRITICAL.lower()
        legacy = (
            ("папк" in t or "дело" in t)
            and any(k in t for k in ("документ", "файл", "материал"))
            and any(k in t for k in ("перенеси", "собери", "все документы"))
        )
        self.assertTrue(legacy)
        self.assertFalse(looks_like_bulk_folder_move_request(self.CRITICAL))


if __name__ == "__main__":
    unittest.main()
