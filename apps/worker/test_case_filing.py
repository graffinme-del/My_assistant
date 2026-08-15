import unittest

from case_filing import ingest_case_number_from_search_result


class SearchResultCaseNumberTests(unittest.TestCase):
    def test_prefers_search_result_over_first_html_match(self) -> None:
        self.assertEqual(
            ingest_case_number_from_search_result(
                {"case_number": "A40-200/2024", "card_url": "https://kad.arbitr.ru/Card/abc"},
                page_extracted="A40-1/2020",
            ),
            "A40-200/2024",
        )

    def test_falls_back_to_page_hint_when_search_has_no_number(self) -> None:
        self.assertEqual(
            ingest_case_number_from_search_result(
                {"case_number": "  ", "card_url": "https://kad.arbitr.ru/Card/abc"},
                page_extracted="A40-200/2024",
            ),
            "A40-200/2024",
        )

    def test_empty_when_neither_source_has_a_number(self) -> None:
        self.assertEqual(ingest_case_number_from_search_result({}, None), "")
        self.assertEqual(ingest_case_number_from_search_result(None, "  "), "")


if __name__ == "__main__":
    unittest.main()
