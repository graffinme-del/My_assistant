import unittest

from moy_arbitr_client import merge_prebuilt_documents
from worker import exact_case_number_matches


class WorkerRegressionTests(unittest.TestCase):
    def test_exact_case_number_matches_excludes_non_matching_results(self) -> None:
        results = [
            {"case_number": "А40-111/2024", "card_url": "https://kad.arbitr.ru/Card/wrong"},
            {"case_number": "A40-222/2024", "card_url": "https://kad.arbitr.ru/Card/right"},
            {"case_number": "", "card_url": "https://kad.arbitr.ru/Card/empty"},
        ]

        self.assertEqual(
            exact_case_number_matches(results, "А40-222/2024"),
            [{"case_number": "A40-222/2024", "card_url": "https://kad.arbitr.ru/Card/right"}],
        )
        self.assertEqual(exact_case_number_matches(results, "А40-333/2024"), [])

    def test_merge_prebuilt_documents_preserves_discovered_and_deduplicates(self) -> None:
        discovered = [
            {"title": "KAD discovered", "file_url": "https://kad.arbitr.ru/doc/1"},
        ]
        prebuilt = [
            {"title": "Duplicate parser doc", "file_url": "https://kad.arbitr.ru/doc/1"},
            {"title": "Parser-only doc", "file_url": "https://kad.arbitr.ru/doc/2"},
        ]

        merged = merge_prebuilt_documents(discovered, prebuilt, cap=10)

        self.assertEqual([row["title"] for row in merged], ["KAD discovered", "Parser-only doc"])


if __name__ == "__main__":
    unittest.main()
