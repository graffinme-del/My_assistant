import unittest

from app.case_number import (
    arbitr_case_number_lookup_keys,
    find_matching_stored_case_number,
    normalize_arbitr_case_number,
)


class YearVariantLookupTests(unittest.TestCase):
    def test_two_digit_year_also_looks_up_four_digit(self) -> None:
        keys = arbitr_case_number_lookup_keys("А40-12345/25")
        self.assertIn("A40-12345/25", keys)
        self.assertIn("A40-12345/2025", keys)

    def test_four_digit_year_also_looks_up_two_digit(self) -> None:
        keys = arbitr_case_number_lookup_keys("A40-12345/2025")
        self.assertIn("A40-12345/2025", keys)
        self.assertIn("A40-12345/25", keys)

    def test_ensure_case_reuses_existing_four_digit_folder(self) -> None:
        existing = ["UNSORTED", "A40-12345/2025", "A41-9/2024"]
        self.assertEqual(
            find_matching_stored_case_number("А40-12345/25", existing),
            "A40-12345/2025",
        )

    def test_ensure_case_reuses_existing_two_digit_folder(self) -> None:
        existing = ["A40-12345/25"]
        self.assertEqual(
            find_matching_stored_case_number("A40-12345/2025", existing),
            "A40-12345/25",
        )

    def test_unrelated_number_does_not_match(self) -> None:
        self.assertIsNone(
            find_matching_stored_case_number("A40-999/25", ["A40-12345/2025"])
        )

    def test_cyrillic_a_normalizes_before_match(self) -> None:
        self.assertEqual(normalize_arbitr_case_number("А40-1/25"), "A40-1/25")
        self.assertEqual(
            find_matching_stored_case_number("А40-1/2025", ["A40-1/25"]),
            "A40-1/25",
        )


if __name__ == "__main__":
    unittest.main()
