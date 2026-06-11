import importlib
import os
import sys
import types
import unittest


def _load_worker():
    if "playwright.sync_api" not in sys.modules:
        playwright = types.ModuleType("playwright")
        sync_api = types.ModuleType("playwright.sync_api")
        sync_api.TimeoutError = TimeoutError
        sync_api.sync_playwright = lambda: None
        sys.modules["playwright"] = playwright
        sys.modules["playwright.sync_api"] = sync_api
    os.environ["PARSER_API_KEY"] = "test-key"
    os.environ["MOY_ARBITR_PARSER_FALLBACK"] = "true"
    sys.modules.pop("worker", None)
    return importlib.import_module("worker")


class MoyArbitrParserFallbackTest(unittest.TestCase):
    def test_unsuccessful_parser_details_do_not_seed_documents(self) -> None:
        worker = _load_worker()
        old_by_id = worker.parser_details_by_id
        old_extract = worker.extract_kad_pdf_url_entries_with_dates
        try:
            worker.parser_details_by_id = lambda _case_id: {"Success": 0, "Cases": []}

            def fail_if_called(_data):
                raise AssertionError("unsuccessful Parser-API payload should not be extracted")

            worker.extract_kad_pdf_url_entries_with_dates = fail_if_called
            docs, diag = worker.moy_arbitr_docs_from_parser_fallback(
                {
                    "card_url": "https://kad.arbitr.ru/Card/11111111-1111-1111-1111-111111111111",
                },
                "",
            )

            self.assertEqual(docs, [])
            self.assertIn("Success=0", diag)
            self.assertIn("urls=0", diag)
        finally:
            worker.parser_details_by_id = old_by_id
            worker.extract_kad_pdf_url_entries_with_dates = old_extract


if __name__ == "__main__":
    unittest.main()
