import unittest

from moy_arbitr_client import _extract_case_results


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


class MoyArbitrCaseExtractionTests(unittest.TestCase):
    def test_html_only_case_numbers_do_not_create_fake_case_results(self) -> None:
        self.assertEqual(_extract_case_results(HtmlOnlySearchPage()), [])


if __name__ == "__main__":
    unittest.main()
