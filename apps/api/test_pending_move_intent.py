"""Regression: pending bulk-move must not apply on casual Russian phrases."""

from __future__ import annotations

import unittest

from app.pending_move_intent import (
    looks_like_pending_move_cancel,
    looks_like_pending_move_confirmation,
    looks_like_pending_move_rejection,
)


class PendingMoveIntentTests(unittest.TestCase):
    def test_confirmation_requires_transfer_wording(self) -> None:
        self.assertTrue(looks_like_pending_move_confirmation("Да, перенеси все"))
        self.assertTrue(looks_like_pending_move_confirmation("Да, перенеси все, кроме 3, 7"))
        self.assertTrue(looks_like_pending_move_confirmation("ок, перенеси"))
        self.assertTrue(looks_like_pending_move_confirmation("подтверждаю перенос"))
        self.assertFalse(looks_like_pending_move_confirmation("подтверждаю, заседание в пятницу"))
        self.assertFalse(looks_like_pending_move_confirmation("Кроме того, когда заседание?"))

    def test_casual_rejection_words_do_not_apply_move(self) -> None:
        # Historical bug: these matched looks_like_pending_move_rejection and applied the plan.
        accidental = [
            "Кроме того, когда заседание?",
            "Это не относится к делу",
            "Убери из ответа лишнее",
            "А кроме А40-111 есть ещё дела?",
            "исключи из отчёта даты",
        ]
        for text in accidental:
            with self.subTest(text=text):
                self.assertFalse(looks_like_pending_move_confirmation(text))
                self.assertFalse(looks_like_pending_move_rejection(text))
                self.assertFalse(looks_like_pending_move_cancel(text))

    def test_explicit_cancel(self) -> None:
        self.assertTrue(looks_like_pending_move_cancel("отмени перенос"))
        self.assertTrue(looks_like_pending_move_cancel("не переноси"))
        self.assertTrue(looks_like_pending_move_rejection("сбрось список переноса"))


if __name__ == "__main__":
    unittest.main()
