from __future__ import annotations

import sys
import types
import unittest
from unittest.mock import patch

import moy_arbitr_client


class _FakePage:
    def __init__(self) -> None:
        self.url = ""

    def goto(self, url: str, **_kwargs) -> None:
        self.url = url

    def wait_for_timeout(self, _ms: int) -> None:
        return None


class _FakeContext:
    def __init__(self, page: _FakePage) -> None:
        self._page = page

    def new_page(self) -> _FakePage:
        return self._page


class _FakeBrowser:
    def __init__(self, page: _FakePage) -> None:
        self._page = page
        self.closed = False

    def new_context(self, **_kwargs) -> _FakeContext:
        return _FakeContext(self._page)

    def close(self) -> None:
        self.closed = True


class _FakeChromium:
    def __init__(self, page: _FakePage) -> None:
        self._page = page

    def launch(self, **_kwargs) -> _FakeBrowser:
        return _FakeBrowser(self._page)


class _FakePlaywright:
    def __init__(self, page: _FakePage) -> None:
        self.chromium = _FakeChromium(page)
        self.stopped = False

    def stop(self) -> None:
        self.stopped = True


class _FakeSyncPlaywright:
    def __init__(self, page: _FakePage) -> None:
        self._page = page

    def start(self) -> _FakePlaywright:
        return _FakePlaywright(self._page)


class MoyArbitrClientTests(unittest.TestCase):
    def test_append_unique_documents_dedupes_and_respects_existing_cap(self) -> None:
        target = [{"file_url": "https://kad.arbitr.ru/doc/1"}]
        seen = {"https://kad.arbitr.ru/doc/1"}
        rows = [
            {"file_url": "https://kad.arbitr.ru/doc/1", "title": "duplicate"},
            {"file_url": "https://kad.arbitr.ru/doc/2", "title": "second"},
            {"file_url": "https://kad.arbitr.ru/doc/3", "title": "third"},
        ]

        with patch.object(moy_arbitr_client, "MOY_ARBITR_MAX_DOCS_PER_CASE", 2):
            added = moy_arbitr_client._append_unique_documents(target, seen, rows)

        self.assertEqual(added, 1)
        self.assertEqual(
            [doc["file_url"] for doc in target],
            ["https://kad.arbitr.ru/doc/1", "https://kad.arbitr.ru/doc/2"],
        )
        self.assertEqual(seen, {"https://kad.arbitr.ru/doc/1", "https://kad.arbitr.ru/doc/2"})

    def test_prebuilt_parser_documents_are_merged_with_browser_discovery(self) -> None:
        page = _FakePage()
        progress_events: list[tuple[int, str, str]] = []
        kad_called = {"value": False}

        def fake_kad_discovery(*_args, **_kwargs) -> list[dict]:
            kad_called["value"] = True
            return [
                {"file_url": "https://kad.arbitr.ru/doc/parser-only", "title": "duplicate"},
                {"file_url": "https://kad.arbitr.ru/doc/kad-extra", "title": "kad"},
            ]

        fake_worker = types.SimpleNamespace(
            open_kad_card_and_collect_docs=fake_kad_discovery,
            collect_kad_documents_from_linked_cards=lambda *_args, **_kwargs: [],
        )
        previous_worker = sys.modules.get("worker")
        sys.modules["worker"] = fake_worker
        try:
            with (
                patch.object(moy_arbitr_client, "sync_playwright", return_value=_FakeSyncPlaywright(page)),
                patch.object(moy_arbitr_client, "ensure_authorized", lambda _page: None),
                patch.object(
                    moy_arbitr_client,
                    "_collect_documents_via_my_arbitr_hub",
                    return_value=[
                        {"file_url": "https://kad.arbitr.ru/doc/kad-extra", "title": "duplicate"},
                        {"file_url": "https://my.arbitr.ru/doc/hub-extra", "title": "hub"},
                    ],
                ),
            ):
                _context, _browser, _pw, docs = moy_arbitr_client.open_case_and_download_documents(
                    {
                        "case_number": "А40-123/2024",
                        "card_url": "https://kad.arbitr.ru/Card/123e4567-e89b-12d3-a456-426614174000",
                    },
                    job_id=42,
                    progress=lambda *args: progress_events.append(args),
                    prebuilt_documents=[
                        {"file_url": "https://kad.arbitr.ru/doc/parser-only", "title": "parser"}
                    ],
                )
        finally:
            if previous_worker is None:
                sys.modules.pop("worker", None)
            else:
                sys.modules["worker"] = previous_worker

        self.assertTrue(kad_called["value"])
        self.assertEqual(
            [doc["file_url"] for doc in docs],
            [
                "https://kad.arbitr.ru/doc/parser-only",
                "https://kad.arbitr.ru/doc/kad-extra",
                "https://my.arbitr.ru/doc/hub-extra",
            ],
        )
        self.assertTrue(any("дополняю обходом КАД" in event[2] for event in progress_events))


if __name__ == "__main__":
    unittest.main()
