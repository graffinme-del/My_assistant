import sys
import types
import unittest


if "playwright.sync_api" not in sys.modules:
    playwright_mod = types.ModuleType("playwright")
    sync_api_mod = types.ModuleType("playwright.sync_api")

    class _PlaywrightTimeoutError(Exception):
        pass

    def _sync_playwright():
        raise AssertionError("sync_playwright should not be used by these unit tests")

    sync_api_mod.TimeoutError = _PlaywrightTimeoutError
    sync_api_mod.sync_playwright = _sync_playwright
    sys.modules.setdefault("playwright", playwright_mod)
    sys.modules.setdefault("playwright.sync_api", sync_api_mod)

from moy_arbitr_client import _append_unique_documents


class MoyArbitrDocumentMergeTest(unittest.TestCase):
    def test_appends_only_new_file_urls_until_cap(self) -> None:
        docs = [{"file_url": "https://kad.arbitr.ru/doc/1", "title": "parser"}]
        seen = {"https://kad.arbitr.ru/doc/1"}

        added = _append_unique_documents(
            docs,
            [
                {"file_url": "https://kad.arbitr.ru/doc/1", "title": "duplicate"},
                {"file_url": "https://kad.arbitr.ru/doc/2", "title": "browser"},
                {"file_url": "https://kad.arbitr.ru/doc/3", "title": "hub"},
            ],
            seen,
            cap=2,
        )

        self.assertEqual(added, 1)
        self.assertEqual([d["file_url"] for d in docs], ["https://kad.arbitr.ru/doc/1", "https://kad.arbitr.ru/doc/2"])
        self.assertEqual(seen, {"https://kad.arbitr.ru/doc/1", "https://kad.arbitr.ru/doc/2"})

    def test_ignores_rows_without_file_url(self) -> None:
        docs: list[dict] = []
        seen: set[str] = set()

        added = _append_unique_documents(docs, [{"title": "missing url"}], seen, cap=10)

        self.assertEqual(added, 0)
        self.assertEqual(docs, [])
        self.assertEqual(seen, set())


if __name__ == "__main__":
    unittest.main()
