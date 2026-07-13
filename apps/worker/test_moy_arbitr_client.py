import sys
import types
import unittest
from unittest.mock import patch


playwright_mod = types.ModuleType("playwright")
sync_api_mod = types.ModuleType("playwright.sync_api")
sync_api_mod.TimeoutError = TimeoutError
sync_api_mod.sync_playwright = lambda: None
sys.modules.setdefault("playwright", playwright_mod)
sys.modules.setdefault("playwright.sync_api", sync_api_mod)

import moy_arbitr_client


class FakePage:
    def __init__(self) -> None:
        self.url = "https://kad.arbitr.ru/Card/12345678-1234-1234-1234-123456789abc"

    def goto(self, *_args, **_kwargs) -> None:
        return None

    def wait_for_timeout(self, *_args, **_kwargs) -> None:
        return None


class FakeContext:
    def __init__(self) -> None:
        self.page = FakePage()

    def new_page(self) -> FakePage:
        return self.page


class FakeBrowser:
    def __init__(self) -> None:
        self.context = FakeContext()

    def new_context(self, **_kwargs) -> FakeContext:
        return self.context

    def close(self) -> None:
        return None


class FakeChromium:
    def __init__(self) -> None:
        self.browser = FakeBrowser()

    def launch(self, **_kwargs) -> FakeBrowser:
        return self.browser


class FakePlaywright:
    def __init__(self) -> None:
        self.chromium = FakeChromium()

    def stop(self) -> None:
        return None


class FakeSyncPlaywright:
    def __init__(self) -> None:
        self.driver = FakePlaywright()

    def start(self) -> FakePlaywright:
        return self.driver


class MoyArbitrDocumentDiscoveryTests(unittest.TestCase):
    def test_parser_documents_are_merged_with_browser_discovery(self) -> None:
        calls: list[str] = []

        def open_kad_card_and_collect_docs(*_args, **_kwargs) -> list[dict]:
            calls.append("kad")
            return [
                {"title": "duplicate", "file_url": "https://kad.arbitr.ru/shared.pdf"},
                {"title": "kad only", "file_url": "https://kad.arbitr.ru/kad-only.pdf"},
            ]

        def collect_hub_docs(*_args, **_kwargs) -> list[dict]:
            calls.append("hub")
            return [{"title": "hub only", "file_url": "https://kad.arbitr.ru/hub-only.pdf"}]

        fake_worker = types.SimpleNamespace(
            open_kad_card_and_collect_docs=open_kad_card_and_collect_docs,
            collect_kad_documents_from_linked_cards=lambda *_args, **_kwargs: [],
        )
        parser_docs = [
            {"title": "parser only", "file_url": "https://kad.arbitr.ru/parser-only.pdf"},
            {"title": "parser duplicate", "file_url": "https://kad.arbitr.ru/shared.pdf"},
        ]
        case_data = {
            "case_number": "A40-1/2026",
            "card_url": "https://kad.arbitr.ru/Card/12345678-1234-1234-1234-123456789abc",
        }

        with patch.object(moy_arbitr_client, "sync_playwright", return_value=FakeSyncPlaywright()), patch.object(
            moy_arbitr_client, "ensure_authorized", return_value=None
        ), patch.object(moy_arbitr_client, "_collect_documents_via_my_arbitr_hub", side_effect=collect_hub_docs), patch.dict(
            sys.modules, {"worker": fake_worker}
        ):
            _context, _browser, _pw, docs = moy_arbitr_client.open_case_and_download_documents(
                case_data,
                prebuilt_documents=parser_docs,
            )

        self.assertEqual(calls, ["kad", "hub"])
        self.assertEqual(
            [doc["file_url"] for doc in docs],
            [
                "https://kad.arbitr.ru/parser-only.pdf",
                "https://kad.arbitr.ru/shared.pdf",
                "https://kad.arbitr.ru/kad-only.pdf",
                "https://kad.arbitr.ru/hub-only.pdf",
            ],
        )


if __name__ == "__main__":
    unittest.main()
