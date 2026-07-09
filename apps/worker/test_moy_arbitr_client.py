import unittest

from moy_arbitr_client import merge_prebuilt_documents


class MoyArbitrClientRegressionTests(unittest.TestCase):
    def test_merge_prebuilt_documents_preserves_browser_docs_and_deduplicates(self) -> None:
        discovered = [
            {"title": "Browser doc", "file_url": "https://kad.arbitr.ru/doc/1"},
        ]
        prebuilt = [
            {"title": "Duplicate parser doc", "file_url": "https://kad.arbitr.ru/doc/1"},
            {"title": "Parser-only doc", "file_url": "https://kad.arbitr.ru/doc/2"},
        ]

        merged = merge_prebuilt_documents(discovered, prebuilt, cap=10)

        self.assertEqual([row["title"] for row in merged], ["Browser doc", "Parser-only doc"])

    def test_merge_prebuilt_documents_respects_cap(self) -> None:
        merged = merge_prebuilt_documents(
            [{"title": "Browser doc", "file_url": "https://kad.arbitr.ru/doc/1"}],
            [{"title": "Parser doc", "file_url": "https://kad.arbitr.ru/doc/2"}],
            cap=1,
        )

        self.assertEqual([row["title"] for row in merged], ["Browser doc"])


if __name__ == "__main__":
    unittest.main()
