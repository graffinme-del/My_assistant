"""Regression: «просмотри папку» must not auto-collect/move documents."""

from __future__ import annotations

import unittest

from app.semantic_collect_match import (
    is_review_folder_without_collect_destination,
    looks_like_semantic_matter_collect_request,
    wants_semantic_collect_preview_only,
)


class SemanticCollectReviewGuardTests(unittest.TestCase):
    def test_review_folder_question_is_not_collect(self) -> None:
        phrases = (
            "просмотри папку Банкротство Эмиль, какие там документы?",
            "просмотри папку А40-12345/2025 какие документы",
            "просмотрите папку Дело А40-1/2025 — какие там файлы",
            "просмотри всю папку с документами",
        )
        for text in phrases:
            with self.subTest(text=text):
                self.assertTrue(is_review_folder_without_collect_destination(text), text)
                self.assertFalse(looks_like_semantic_matter_collect_request(text), text)
                self.assertTrue(wants_semantic_collect_preview_only(text), text)

    def test_legacy_substring_would_have_matched_review_as_collect(self) -> None:
        """Pre-fix matcher: «просмотри папку» + «документ» was enough to execute collect."""
        text = "просмотри папку Банкротство Эмиль, какие там документы?"
        t = text.lower()
        self.assertIn("просмотри папку", t)
        self.assertIn("документ", t)

    def test_review_plus_destination_still_collects(self) -> None:
        phrases = (
            "просмотри папку Источник в папку Банкротство Эмиль и перенеси документы",
            "просмотри папку А40-111/2024 в папку А40-222/2025 — документы",
            "просмотри папку А и перенеси подходящие документы в папку Б",
        )
        for text in phrases:
            with self.subTest(text=text):
                self.assertFalse(is_review_folder_without_collect_destination(text), text)
                self.assertTrue(looks_like_semantic_matter_collect_request(text), text)
                self.assertFalse(wants_semantic_collect_preview_only(text), text)

    def test_explicit_sort_commands_unchanged(self) -> None:
        phrases = (
            "отсортируй документы по смыслу в папку Банкротство Эмиль",
            "собери все документы относящиеся к делу А40-12345/2025",
            "перенеси подходящие документы в папку Банкротство",
        )
        for text in phrases:
            with self.subTest(text=text):
                self.assertTrue(looks_like_semantic_matter_collect_request(text), text)


if __name__ == "__main__":
    unittest.main()
