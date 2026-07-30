"""Regression: source-folder semantic heuristic must not mass-move source docs."""

from __future__ import annotations

import unittest
from types import SimpleNamespace

from app.semantic_matter_collect import _doc_matches_case_numbers, _heuristic_semantic_move


def _case(*, case_id: int, case_number: str, title: str = "") -> SimpleNamespace:
    return SimpleNamespace(id=case_id, case_number=case_number, title=title or case_number)


def _doc(*, filename: str, extracted_text: str = "") -> SimpleNamespace:
    return SimpleNamespace(filename=filename, extracted_text=extracted_text)


class SemanticSourceHeuristicTests(unittest.TestCase):
    def test_source_case_number_match_does_not_force_move(self) -> None:
        """Docs that correctly cite the source case number must stay put."""
        source = _case(case_id=1, case_number="A40-111/2024")
        target = _case(case_id=2, case_number="A40-222/2025")
        doc = _doc(
            filename="opredelenie.pdf",
            extracted_text="Определение Арбитражного суда по делу A40-111/2024",
        )
        self.assertTrue(
            _doc_matches_case_numbers(doc, source),
            "precondition: extracted text must match the source case number",
        )

        move, reason = _heuristic_semantic_move(doc, target, source, [])

        self.assertFalse(move)
        self.assertEqual(reason, "")

    def test_short_year_source_variant_also_blocked(self) -> None:
        source = _case(case_id=1, case_number="A40-111/2024")
        target = _case(case_id=2, case_number="A40-222/2025")
        doc = _doc(
            filename="petition.pdf",
            extracted_text="Ходатайство по делу № A40-111/24",
        )
        self.assertTrue(_doc_matches_case_numbers(doc, source))

        move, _reason = _heuristic_semantic_move(doc, target, source, [])
        self.assertFalse(move)

    def test_target_case_number_match_still_moves(self) -> None:
        source = _case(case_id=1, case_number="A40-111/2024")
        target = _case(case_id=2, case_number="A40-222/2025")
        doc = _doc(
            filename="misfiled.pdf",
            extracted_text="Материалы по делу A40-222/2025 ошибочно лежат в другой папке",
        )
        self.assertTrue(_doc_matches_case_numbers(doc, target))

        move, reason = _heuristic_semantic_move(doc, target, source, [])

        self.assertTrue(move)
        self.assertIn("целевой", reason)

    def test_unrelated_doc_without_numbers_does_not_move(self) -> None:
        source = _case(case_id=1, case_number="A40-111/2024")
        target = _case(case_id=2, case_number="A40-222/2025")
        doc = _doc(filename="scan_misc.pdf", extracted_text="Общий скан без номера дела")

        move, reason = _heuristic_semantic_move(doc, target, source, [])

        self.assertFalse(move)
        self.assertEqual(reason, "")


if __name__ == "__main__":
    unittest.main()
