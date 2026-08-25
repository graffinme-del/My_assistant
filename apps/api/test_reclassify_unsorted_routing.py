"""Routing guards for unsorted auto-sort chat (no Postgres / app.main)."""

from __future__ import annotations

import unittest

from app.reclassify_unsorted_intent import looks_like_reclassify_unsorted_request


class ReclassifyUnsortedRoutingTests(unittest.TestCase):
    def test_move_unsorted_to_named_folder_is_not_autosort(self) -> None:
        self.assertFalse(
            looks_like_reclassify_unsorted_request(
                "перенеси неразобранные документы в папку Банкротство Эмиль"
            )
        )

    def test_move_by_case_number_is_not_autosort(self) -> None:
        self.assertFalse(
            looks_like_reclassify_unsorted_request(
                "перенеси документы по номеру А40-12345/2025 в папку Банкротство Эмиль"
            )
        )

    def test_how_to_sort_question_is_not_autosort(self) -> None:
        self.assertFalse(
            looks_like_reclassify_unsorted_request("как разложить неразобранное?")
        )
        self.assertFalse(
            looks_like_reclassify_unsorted_request(
                "как разложить неразобранные документы по делам"
            )
        )

    def test_analyze_named_case_is_not_autosort(self) -> None:
        self.assertFalse(
            looks_like_reclassify_unsorted_request(
                "разбери документы по номеру А40-12345/2025"
            )
        )

    def test_bind_specific_document_is_not_autosort(self) -> None:
        self.assertFalse(
            looks_like_reclassify_unsorted_request(
                "привяжи документ 4 в дело Банкротство АГМ"
            )
        )

    def test_sort_unsorted_still_matches(self) -> None:
        self.assertTrue(looks_like_reclassify_unsorted_request("разбери неразобранное"))
        self.assertTrue(
            looks_like_reclassify_unsorted_request(
                "разбери неразобранные документы по номерам"
            )
        )
        self.assertTrue(
            looks_like_reclassify_unsorted_request("переразбери unsorted по тегам")
        )
        self.assertTrue(
            looks_like_reclassify_unsorted_request("разложи неразобранное")
        )

    def test_autosort_command_still_matches(self) -> None:
        self.assertTrue(
            looks_like_reclassify_unsorted_request("автосорт неразобранных")
        )
        self.assertTrue(looks_like_reclassify_unsorted_request("запусти автосорт"))
        self.assertFalse(
            looks_like_reclassify_unsorted_request("как включить автосорт неразобранного")
        )


if __name__ == "__main__":
    unittest.main()
