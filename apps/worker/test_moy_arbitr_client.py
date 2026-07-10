import unittest
from unittest.mock import patch

from moy_arbitr_client import _extract_case_results, open_case_and_download_documents


class EmptyLocator:
    def count(self) -> int:
        return 0


class EmptyFrame:
    def locator(self, selector: str) -> EmptyLocator:
        return EmptyLocator()


class HtmlOnlySearchPage:
    url = "https://my.arbitr.ru/#/cases/my"
    frames = [EmptyFrame()]

    def content(self) -> str:
        return """
        <html>
          <body>
            <span>A40-111/2026</span>
            <span>A40-222/2026</span>
          </body>
        </html>
        """


class FakePage:
    def goto(self, *args, **kwargs) -> None:
        return None

    def wait_for_timeout(self, *args, **kwargs) -> None:
        return None


class FakeContext:
    def __init__(self) -> None:
        self.page = FakePage()

    def new_page(self) -> FakePage:
        return self.page


class FakeBrowser:
    pass


class FakeChromium:
    def __init__(self, browser: FakeBrowser) -> None:
        self.browser = browser

    def launch(self, *args, **kwargs) -> FakeBrowser:
        return self.browser


class FakePlaywright:
    def __init__(self, browser: FakeBrowser) -> None:
        self.chromium = FakeChromium(browser)


class FakeSyncPlaywright:
    def __init__(self, playwright: FakePlaywright) -> None:
        self.playwright = playwright

    def start(self) -> FakePlaywright:
        return self.playwright


class MoyArbitrCaseExtractionTests(unittest.TestCase):
    def test_html_only_case_numbers_do_not_create_fake_case_results(self) -> None:
        self.assertEqual(_extract_case_results(HtmlOnlySearchPage()), [])

    def test_prebuilt_parser_documents_are_merged_with_hub_documents(self) -> None:
        context = FakeContext()
        browser = FakeBrowser()
        playwright = FakePlaywright(browser)
        parser_doc = {"file_url": "https://kad.arbitr.ru/document/parser.pdf", "title": "parser"}
        hub_docs = [
            {"file_url": "https://kad.arbitr.ru/document/parser.pdf", "title": "duplicate"},
            {"file_url": "https://my.arbitr.ru/document/hub.pdf", "title": "hub"},
        ]

        with patch("moy_arbitr_client.sync_playwright", return_value=FakeSyncPlaywright(playwright)), patch(
            "moy_arbitr_client._new_context", return_value=context
        ), patch("moy_arbitr_client.ensure_authorized"), patch(
            "moy_arbitr_client._collect_documents_via_my_arbitr_hub", return_value=hub_docs
        ) as collect_hub:
            returned_context, returned_browser, returned_playwright, docs = open_case_and_download_documents(
                {
                    "card_url": "https://kad.arbitr.ru/Card/00000000-0000-0000-0000-000000000000",
                    "case_number": "A40-111/2026",
                },
                prebuilt_documents=[parser_doc],
            )

        self.assertIs(returned_context, context)
        self.assertIs(returned_browser, browser)
        self.assertIs(returned_playwright, playwright)
        self.assertEqual([doc["file_url"] for doc in docs], [parser_doc["file_url"], hub_docs[1]["file_url"]])
        collect_hub.assert_called_once()


if __name__ == "__main__":
    unittest.main()
