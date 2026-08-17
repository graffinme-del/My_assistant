"""Duplicate-cleanup chat must not treat preview phrasing as an execute command."""

from __future__ import annotations

import unittest

from app.duplicate_cleanup_intent import (
    has_duplicate_cleanup_execute_intent,
    is_duplicate_cleanup_dry_run,
    without_preview_phrases,
)


def _legacy_dry_run(text: str) -> bool:
    """Pre-fix substring logic copied from handle_cross_folder_duplicate_cleanup_chat."""
    t = (text or "").lower()
    return (
        any(
            k in t
            for k in (
                "только список",
                "без удаления",
                "не удаляй",
                "превью",
                "покажи план",
                "что удалишь",
                "что удалится",
            )
        )
        and not any(k in t for k in ("удали", "убери", "почисти", "выполни удаление", "да, удали"))
    ) or ("покажи" in t and not any(k in t for k in ("удали", "убери", "почисти")))


class DuplicateCleanupPreviewIntentTests(unittest.TestCase):
    def test_preview_phrase_chto_udalish_is_dry_run(self) -> None:
        text = "Что удалишь с дубликатами между папками?"
        self.assertTrue(is_duplicate_cleanup_dry_run(text))
        self.assertFalse(has_duplicate_cleanup_execute_intent(text))
        self.assertFalse(_legacy_dry_run(text), "legacy substring logic must fail this case")

    def test_preview_phrase_chto_udalitsya_is_dry_run(self) -> None:
        text = "что удалится среди дубликатов"
        self.assertTrue(is_duplicate_cleanup_dry_run(text))
        self.assertFalse(has_duplicate_cleanup_execute_intent(text))
        self.assertFalse(_legacy_dry_run(text), "legacy substring logic must fail this case")

    def test_vyvedi_duplicates_is_dry_run(self) -> None:
        text = "выведи дубликаты между папками"
        self.assertTrue(is_duplicate_cleanup_dry_run(text))
        self.assertFalse(has_duplicate_cleanup_execute_intent(text))
        self.assertFalse(_legacy_dry_run(text), "legacy logic ignored «выведи»")

    def test_pokazhi_duplicates_is_dry_run(self) -> None:
        self.assertTrue(is_duplicate_cleanup_dry_run("покажи дубликаты между папками"))

    def test_explicit_delete_is_not_dry_run(self) -> None:
        text = "Удали дубликаты между папками"
        self.assertFalse(is_duplicate_cleanup_dry_run(text))
        self.assertTrue(has_duplicate_cleanup_execute_intent(text))

    def test_uberi_duplicates_is_not_dry_run(self) -> None:
        self.assertFalse(is_duplicate_cleanup_dry_run("убери дубликаты, оставь по одному"))
        self.assertTrue(has_duplicate_cleanup_execute_intent("убери дубликаты, оставь по одному"))

    def test_keep_one_without_preview_is_execute(self) -> None:
        text = "оставь один экземпляр дубликатов между папками"
        self.assertFalse(is_duplicate_cleanup_dry_run(text))
        self.assertTrue(has_duplicate_cleanup_execute_intent(text))

    def test_preview_plus_explicit_delete_executes(self) -> None:
        text = "покажи план и удали дубликаты между папками"
        self.assertFalse(is_duplicate_cleanup_dry_run(text))
        self.assertTrue(has_duplicate_cleanup_execute_intent(text))

    def test_ne_udalyay_is_dry_run(self) -> None:
        self.assertTrue(is_duplicate_cleanup_dry_run("не удаляй дубликаты"))

    def test_tolko_spisok_is_dry_run(self) -> None:
        self.assertTrue(is_duplicate_cleanup_dry_run("дубликаты, только список"))

    def test_tool_router_dry_run_prefix_with_udalish_user_text(self) -> None:
        text = "Покажи план удаления дубликатов без удаления. что удалишь с дубликатами"
        self.assertTrue(is_duplicate_cleanup_dry_run(text))
        self.assertFalse(has_duplicate_cleanup_execute_intent(text))
        self.assertFalse(_legacy_dry_run(text))

    def test_tool_router_execute_prefix_still_executes(self) -> None:
        text = "Удали дубликаты между папками, оставь по одному файлу. что удалишь"
        self.assertFalse(is_duplicate_cleanup_dry_run(text))
        self.assertTrue(has_duplicate_cleanup_execute_intent(text))

    def test_without_preview_phrases_strips_udalish(self) -> None:
        remainder = without_preview_phrases("что удалишь с дубликатами")
        self.assertNotIn("удали", remainder)
        self.assertIn("дубликатами", remainder)


if __name__ == "__main__":
    unittest.main()
