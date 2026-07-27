"""Regression: local:// document keys must stay under STORAGE_ROOT."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from app.local_storage import resolve_local_s3_key


class ResolveLocalS3KeyTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name).resolve()
        (self.root / "safe.pdf").write_bytes(b"%PDF")
        (self.root / "nested").mkdir()
        (self.root / "nested" / "doc.pdf").write_bytes(b"%PDF")

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_accepts_relative_key_under_root(self) -> None:
        path = resolve_local_s3_key("local://safe.pdf", self.root)
        self.assertEqual(path, self.root / "safe.pdf")

    def test_accepts_nested_relative_key(self) -> None:
        path = resolve_local_s3_key("local://nested/doc.pdf", self.root)
        self.assertEqual(path, self.root / "nested" / "doc.pdf")

    def test_rejects_parent_directory_traversal(self) -> None:
        outside = self.root.parent / "secret.txt"
        outside.write_text("SECRET", encoding="utf-8")
        self.addCleanup(lambda: outside.unlink(missing_ok=True))
        self.assertIsNone(resolve_local_s3_key("local://../secret.txt", self.root))
        self.assertIsNone(resolve_local_s3_key("local://nested/../../secret.txt", self.root))

    def test_rejects_absolute_unix_path_via_local_scheme(self) -> None:
        # pathlib replaces when the right-hand side is absolute.
        self.assertIsNone(resolve_local_s3_key("local:///etc/passwd", self.root))

    def test_rejects_empty_and_dot_only_keys(self) -> None:
        self.assertIsNone(resolve_local_s3_key("local://", self.root))
        self.assertIsNone(resolve_local_s3_key("local://.", self.root))
        # "./safe.pdf" normalizes to a safe relative path under root — allowed.
        self.assertEqual(
            resolve_local_s3_key("local://./safe.pdf", self.root),
            self.root / "safe.pdf",
        )

    def test_rejects_non_local_scheme(self) -> None:
        self.assertIsNone(resolve_local_s3_key("s3://bucket/key", self.root))
        self.assertIsNone(resolve_local_s3_key("safe.pdf", self.root))


if __name__ == "__main__":
    unittest.main()
