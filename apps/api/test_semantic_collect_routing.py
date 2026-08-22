"""Routing guards for semantic matter collect (no Postgres / app.main)."""

from __future__ import annotations

import unittest

from app.semantic_collect_intent import (
    looks_like_semantic_matter_collect_request,
    wants_semantic_collect_preview_only,
)


class SemanticCollectRoutingTests(unittest.TestCase):
    def test_show_by_case_number_is_not_collect(self) -> None:
        self.assertFalse(
            looks_like_semantic_matter_collect_request(
                "покажи документы по номеру дела А40-12345/2025"
            )
        )

    def test_delete_by_case_number_is_not_collect(self) -> None:
        self.assertFalse(
            looks_like_semantic_matter_collect_request(
                "удали все документы по номеру дела А40-12345/2025"
            )
        )

    def test_count_by_case_number_is_not_collect(self) -> None:
        self.assertFalse(
            looks_like_semantic_matter_collect_request(
                "сколько документов по номеру дела А40-12345/2025"
            )
        )

    def test_delete_unrelated_docs_is_not_collect(self) -> None:
        self.assertFalse(
            looks_like_semantic_matter_collect_request(
                "удали все документы не относящиеся к делу Банкротство Эмиль"
            )
        )
        self.assertFalse(
            looks_like_semantic_matter_collect_request(
                "убери все документы не относящиеся к делу А40-12345/2025"
            )
        )

    def test_show_related_docs_is_not_collect(self) -> None:
        self.assertFalse(
            looks_like_semantic_matter_collect_request(
                "покажи документы относящиеся к делу Банкротство Эмиль"
            )
        )

    def test_sort_by_meaning_still_collects(self) -> None:
        self.assertTrue(
            looks_like_semantic_matter_collect_request(
                "отсортируй документы по смыслу в папку А40-12345/2025"
            )
        )

    def test_collect_related_still_collects(self) -> None:
        self.assertTrue(
            looks_like_semantic_matter_collect_request(
                "собери все документы относящиеся к делу Банкротство Эмиль"
            )
        )

    def test_keep_only_related_still_collects(self) -> None:
        self.assertTrue(
            looks_like_semantic_matter_collect_request(
                "оставь только документы относящиеся к делу А40-12345/2025"
            )
        )

    def test_review_folder_and_sort_still_collects(self) -> None:
        self.assertTrue(
            looks_like_semantic_matter_collect_request(
                "просмотри папку А40-111/2024, отсортируй по смыслу документы в папку А40-222/2025"
            )
        )

    def test_keyword_folder_create_is_not_collect(self) -> None:
        self.assertFalse(
            looks_like_semantic_matter_collect_request(
                "создай папку Банкротство и перенеси документы, содержащие: договор"
            )
        )

    def test_preview_phrases(self) -> None:
        self.assertTrue(
            wants_semantic_collect_preview_only("отсортируй документы по смыслу, только список")
        )
        self.assertFalse(
            wants_semantic_collect_preview_only("отсортируй документы по смыслу в папку А40-1/2025")
        )
        self.assertTrue(
            wants_semantic_collect_preview_only("покажи документы по смыслу в папку А40-1/2025")
        )


if __name__ == "__main__":
    unittest.main()
