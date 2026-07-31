"""Regression: hard-delete must not unlink files before a successful DB commit."""

from __future__ import annotations

import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest.mock import MagicMock

from app.document_delete import delete_documents_hard, unlink_local_path


class FakePath:
    def __init__(self, tmp: Path, name: str = "doc.pdf") -> None:
        self.path = tmp / name
        self.path.write_bytes(b"%PDF-1.4 fake")

    def is_file(self) -> bool:
        return self.path.is_file()

    def unlink(self) -> None:
        self.path.unlink()

    @property
    def exists_on_disk(self) -> bool:
        return self.path.exists()


class DeleteDocumentsHardOrderTests(unittest.TestCase):
    def test_failed_commit_keeps_file_on_disk(self) -> None:
        with TemporaryDirectory() as tmp:
            fake = FakePath(Path(tmp))
            doc = SimpleNamespace(id=7, case_id=3, filename="Решение.pdf")
            db = MagicMock()
            db.commit.side_effect = RuntimeError("database unavailable")

            with self.assertRaises(RuntimeError):
                delete_documents_hard(
                    db,
                    [doc],  # type: ignore[list-item]
                    resolve_local_path=lambda _d: fake.path,
                )

            self.assertTrue(fake.exists_on_disk, "file must survive when commit fails")
            db.delete.assert_called_once_with(doc)
            db.add.assert_called_once()

    def test_successful_commit_unlinks_file(self) -> None:
        with TemporaryDirectory() as tmp:
            fake = FakePath(Path(tmp))
            doc = SimpleNamespace(id=8, case_id=4, filename="Определение.pdf")
            db = MagicMock()

            removed = delete_documents_hard(
                db,
                [doc],  # type: ignore[list-item]
                resolve_local_path=lambda _d: fake.path,
            )

            db.commit.assert_called_once()
            self.assertFalse(fake.exists_on_disk, "file must be removed after commit")
            self.assertEqual(removed, ["[8] Определение.pdf"])

    def test_unlink_local_path_ignores_missing(self) -> None:
        with TemporaryDirectory() as tmp:
            missing = Path(tmp) / "gone.pdf"
            unlink_local_path(missing)  # must not raise
            unlink_local_path(None)


if __name__ == "__main__":
    unittest.main()
