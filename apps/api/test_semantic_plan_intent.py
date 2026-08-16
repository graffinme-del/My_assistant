"""Semantic-plan chat confirm must not fire on casual Russian follow-ups."""

from __future__ import annotations

import unittest

from app.semantic_plan_intent import (
    looks_like_semantic_plan_cancel,
    looks_like_semantic_plan_confirm,
)


class SemanticPlanConfirmTests(unittest.TestCase):
    def test_preview_phrases_confirm(self) -> None:
        self.assertTrue(looks_like_semantic_plan_confirm("да, объединить по смыслу"))
        self.assertTrue(looks_like_semantic_plan_confirm("Подтверждаю смысловое объединение."))
        self.assertTrue(looks_like_semantic_plan_confirm("Выполни смысловое объединение"))
        self.assertTrue(looks_like_semantic_plan_confirm("примени смысловой план"))

    def test_casual_confirm_does_not_merge(self) -> None:
        accidental = (
            "Подтверждаю, в этом есть смысл — судья отложил заседание.",
            "подтверждаю по сути",
            "Согласен, по сути так и есть.",
            "не согласен по сути",
            "Подтверждаю получение. Смысл определения такой-то.",
            "да ок",
            "подтверждаю",
            "объедини по сути",
            "проанализируй папки по смыслу",
        )
        for text in accidental:
            with self.subTest(text=text):
                self.assertFalse(looks_like_semantic_plan_confirm(text), text)

    def test_cancel_still_matches(self) -> None:
        self.assertTrue(looks_like_semantic_plan_cancel("отмени смысловой план"))
        self.assertFalse(looks_like_semantic_plan_cancel("подтверждаю смысловое объединение"))
        self.assertFalse(looks_like_semantic_plan_confirm("отмени смысловое объединение"))


if __name__ == "__main__":
    unittest.main()
