import importlib
import sys
import types
import unittest
from pathlib import Path
from unittest.mock import patch


def _install_playwright_stub_if_needed() -> None:
    try:
        import playwright.sync_api  # noqa: F401
        return
    except ModuleNotFoundError:
        pass

    playwright_pkg = types.ModuleType("playwright")
    sync_api = types.ModuleType("playwright.sync_api")

    class PlaywrightTimeoutError(Exception):
        pass

    def sync_playwright():
        raise AssertionError("sync_playwright must be patched in tests")

    sync_api.TimeoutError = PlaywrightTimeoutError
    sync_api.sync_playwright = sync_playwright
    playwright_pkg.sync_api = sync_api
    sys.modules["playwright"] = playwright_pkg
    sys.modules["playwright.sync_api"] = sync_api


class _FakePage:
    url = "https://kad.arbitr.ru/Card/aaaaaaaa-1111-2222-3333-bbbbbbbbbbbb"

    def goto(self, *_args, **_kwargs):
        return None

    def wait_for_timeout(self, *_args, **_kwargs):
        return None


class _FakeContext:
    def __init__(self):
        self.page = _FakePage()

    def new_page(self):
        return self.page


class _FakeBrowser:
    def __init__(self):
        self.context = _FakeContext()
        self.closed = False

    def new_context(self, **_kwargs):
        return self.context

    def close(self):
        self.closed = True


class _FakeChromium:
    def __init__(self):
        self.browser = _FakeBrowser()

    def launch(self, **_kwargs):
        return self.browser


class _FakePlaywright:
    def __init__(self):
        self.chromium = _FakeChromium()
        self.stopped = False

    def stop(self):
        self.stopped = True


class _FakePlaywrightStarter:
    def __init__(self, playwright):
        self.playwright = playwright

    def start(self):
        return self.playwright


class MoyArbitrClientTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        _install_playwright_stub_if_needed()
        worker_dir = Path(__file__).resolve().parent
        if str(worker_dir) not in sys.path:
            sys.path.insert(0, str(worker_dir))
        cls.client = importlib.import_module("moy_arbitr_client")

    def test_prebuilt_parser_documents_are_merged_with_my_arbitr_hub(self) -> None:
        parser_doc = {
            "remote_document_id": "parser-fallback:https://kad.arbitr.ru/api/doc/parser.pdf",
            "title": "parser.pdf",
            "filename": "",
            "file_url": "https://kad.arbitr.ru/api/doc/parser.pdf",
        }
        hub_doc = {
            "remote_document_id": "moy-arbitr:https://my.arbitr.ru/files/hub.pdf",
            "title": "hub.pdf",
            "filename": "",
            "file_url": "https://my.arbitr.ru/files/hub.pdf",
        }
        case_data = {
            "case_number": "А40-12345/2026",
            "card_url": "https://kad.arbitr.ru/Card/aaaaaaaa-1111-2222-3333-bbbbbbbbbbbb",
        }
        fake_playwright = _FakePlaywright()
        progress_events: list[tuple[int, str, str]] = []
        kad_calls: list[str] = []
        worker_stub = types.SimpleNamespace(
            open_kad_card_and_collect_docs=lambda *_args, **_kwargs: kad_calls.append("called") or [],
            collect_kad_documents_from_linked_cards=lambda *_args, **_kwargs: [],
        )
        old_worker = sys.modules.get("worker")
        sys.modules["worker"] = worker_stub
        try:
            with (
                patch.object(
                    self.client,
                    "sync_playwright",
                    return_value=_FakePlaywrightStarter(fake_playwright),
                ),
                patch.object(self.client, "ensure_authorized", return_value=None),
                patch.object(self.client, "state_file_exists", return_value=False),
                patch.object(self.client, "MOY_ARBITR_MAX_DOCS_PER_CASE", 10),
                patch.object(
                    self.client,
                    "_collect_documents_via_my_arbitr_hub",
                    return_value=[hub_doc],
                ),
            ):
                _context, _browser, _pw, docs = self.client.open_case_and_download_documents(
                    case_data,
                    job_id=7,
                    progress=lambda *args: progress_events.append(args),
                    prebuilt_documents=[parser_doc],
                )
        finally:
            if old_worker is None:
                sys.modules.pop("worker", None)
            else:
                sys.modules["worker"] = old_worker

        self.assertEqual(
            [doc["file_url"] for doc in docs],
            [parser_doc["file_url"], hub_doc["file_url"]],
        )
        self.assertEqual(kad_calls, [])
        self.assertIn("проверяю хаб дела", progress_events[0][2])


if __name__ == "__main__":
    unittest.main()
