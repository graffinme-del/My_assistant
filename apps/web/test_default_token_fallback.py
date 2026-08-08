"""Ensure the web UI does not hardcode the public owner-dev-token fallback."""

from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parent
INDEX = ROOT / "index.html"


class WebDefaultTokenFallbackTests(unittest.TestCase):
    def test_no_owner_dev_token_fallback_in_index(self) -> None:
        text = INDEX.read_text(encoding="utf-8")
        self.assertNotIn('|| "owner-dev-token"', text)
        self.assertNotIn("|| 'owner-dev-token'", text)
        # Storage getter must prefer empty over a public default.
        self.assertIn('return localStorage.getItem("apiToken") || ""', text)


if __name__ == "__main__":
    unittest.main()
