"""Regression checks for web XSS hardening in index.html (no browser required)."""

from __future__ import annotations

import re
import unittest
from pathlib import Path

INDEX = Path(__file__).resolve().parent / "index.html"


class WebXssHardeningTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.src = INDEX.read_text(encoding="utf-8")

    def test_iframe_preview_excludes_executable_types(self) -> None:
        m = re.search(
            r"const iframeOk = \[([\s\S]*?)\]\.includes\(ext\)",
            self.src,
        )
        self.assertIsNotNone(m, "iframeOk allowlist missing")
        allow = {
            s.strip().strip("\"'")
            for s in m.group(1).split(",")
            if s.strip().strip("\"'")
        }
        self.assertFalse({"svg", "htm", "html"} & allow)
        self.assertIn("pdf", allow)
        self.assertIn("png", allow)

    def test_preview_forces_safe_mime_helper(self) -> None:
        self.assertIn("function previewBlobWithSafeType", self.src)
        self.assertIn("previewBlobWithSafeType(blob, ext)", self.src)
        self.assertNotIn("text/html", self.src.split("function previewBlobWithSafeType", 1)[1].split("function ", 1)[0])
        self.assertNotIn("image/svg", self.src.split("function previewBlobWithSafeType", 1)[1].split("function ", 1)[0])

    def test_event_task_doc_lists_escape_html(self) -> None:
        self.assertRegex(
            self.src,
            r"loadEvents\(\)[\s\S]*?escapeHtml\(e\.event_type\)[\s\S]*?escapeHtml\(e\.body\)",
        )
        self.assertRegex(
            self.src,
            r"loadTasks\(\)[\s\S]*?escapeHtml\(t\.title\)[\s\S]*?escapeHtml\(t\.priority\)",
        )
        self.assertRegex(
            self.src,
            r"loadDocs\(\)[\s\S]*?escapeHtml\(d\.filename\)[\s\S]*?escapeHtml\(d\.s3_key\)",
        )

    def test_mammoth_html_is_sanitized(self) -> None:
        self.assertIn("function sanitizeMammothHtml", self.src)
        self.assertIn("sanitizeMammothHtml(result.value)", self.src)


if __name__ == "__main__":
    unittest.main()
