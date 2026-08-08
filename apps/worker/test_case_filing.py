"""Regression: court ingest must not prefer unrelated HTML case numbers."""

from __future__ import annotations

import unittest

from case_filing import pick_case_number_for_filing


class PickCaseNumberForFilingTests(unittest.TestCase):
    def test_prefers_search_result_over_page_hint(self) -> None:
        self.assertEqual(
            pick_case_number_for_filing("A40-111/2024", "A40-999/2023"),
            "A40-111/2024",
        )

    def test_falls_back_to_page_hint_when_search_empty(self) -> None:
        self.assertEqual(
            pick_case_number_for_filing("", "A40-999/2023"),
            "A40-999/2023",
        )

    def test_none_when_both_missing(self) -> None:
        self.assertIsNone(pick_case_number_for_filing(None, None))
        self.assertIsNone(pick_case_number_for_filing("  ", ""))


if __name__ == "__main__":
    unittest.main()
